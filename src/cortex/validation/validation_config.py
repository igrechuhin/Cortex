"""
Validation configuration management.

This module manages user-configurable validation rules and settings
for Memory Bank validation.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.models import JsonValue, ModelDict
from cortex.validation.models import ValidationConfigModel


class ValidationConfig:
    """Manage validation configuration."""

    def __init__(self, project_root: Path):
        """
        Initialize with project root.

        Args:
            project_root: Path to project root
        """
        self.project_root: Path = project_root
        self.config_path: Path = project_root / ".cortex" / "validation.json"
        self.config: ValidationConfigModel = self._load_config()

    def _load_config(self) -> ValidationConfigModel:
        """
        Load validation config from file or use defaults.

        Returns:
            ValidationConfigModel with configuration

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        # Early return if config file doesn't exist - use defaults
        if not self.config_path.exists():
            return ValidationConfigModel()

        user_config_raw = self._read_config_file()
        if user_config_raw is None:
            return ValidationConfigModel()

        # Validate config type and parse with Pydantic
        if not isinstance(user_config_raw, dict):
            return ValidationConfigModel()

        return self._parse_and_merge_config(cast(dict[str, object], user_config_raw))

    def _read_config_file(self) -> JsonValue | None:
        """Read config file, handling errors gracefully."""
        try:
            with open(self.config_path) as f:
                return cast(JsonValue, json.load(f))
        except Exception as e:
            from cortex.core.logging_config import logger

            error_detail = str(e)
            error_type = type(e).__name__
            logger.warning(
                (
                    (
                        f"Failed to load validation config from "
                        f"{self.config_path}: {error_type}: {error_detail}. "
                        "Cause: Invalid JSON format or file read error. "
                        "Try: Fix JSON syntax errors, check file permissions, "
                    )
                    + ("or delete config file to use default values.")
                )
            )
            return None

    def _parse_and_merge_config(
        self, user_config_raw: dict[str, object]
    ) -> ValidationConfigModel:
        """Parse and merge user config with defaults."""
        try:
            # Parse user config, merging with defaults
            default_dict = cast(
                ModelDict, ValidationConfigModel().model_dump(mode="python")
            )
            merged_dict = self._merge_dicts(
                default_dict, cast(ModelDict, user_config_raw)
            )
            return ValidationConfigModel.model_validate(merged_dict)
        except Exception:
            # If validation fails, return defaults
            return ValidationConfigModel()

    def _merge_dicts(self, default: ModelDict, user: ModelDict) -> ModelDict:
        """
        Recursively merge user config dict with defaults.

        Args:
            default: Default configuration dict
            user: User configuration dict

        Returns:
            Merged configuration dict
        """
        result = default.copy()

        for key, value in user.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_dicts(
                    cast(ModelDict, result[key]),
                    cast(ModelDict, value),
                )
            else:
                result[key] = value

        return result

    def get(self, key: str, default: JsonValue | None = None) -> JsonValue | None:
        """
        Get config value with dot notation support.

        Args:
            key: Config key (supports dot notation like "token_budget.max_total_tokens")
            default: Default value if key not found

        Returns:
            Config value or default
        """
        keys = key.split(".")
        config_dict = cast(ModelDict, self.config.model_dump(mode="python"))
        value: JsonValue = config_dict

        for k in keys:
            if not isinstance(value, dict):
                return default
            if k not in value:
                return default
            value_dict = cast(dict[str, JsonValue], value)
            value = value_dict[k]

        if value is None:
            return None
        return value

    def set(self, key: str, value: JsonValue) -> None:
        """
        Set config value with dot notation support.

        Args:
            key: Config key (supports dot notation)
            value: Value to set
        """
        # Convert model to dict, modify, then recreate model
        config_dict = cast(ModelDict, self.config.model_dump(mode="python"))
        keys = key.split(".")

        # Navigate to the parent dict
        current: ModelDict = config_dict
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            if not isinstance(current[k], dict):
                current[k] = {}
            current = cast(ModelDict, current[k])

        # Set the value
        current[keys[-1]] = value

        # Recreate model from modified dict
        self.config = ValidationConfigModel.model_validate(config_dict)

    async def save(self) -> None:
        """
        Save configuration to file.

        Raises:
            IOError: If save fails
        """
        try:
            async with open_async_text_file(self.config_path, "w", "utf-8") as f:
                config_dict = self.config.model_dump(mode="json")
                _ = await f.write(json.dumps(config_dict, indent=2))
        except Exception as e:
            raise OSError(
                (
                    f"Failed to save validation config to "
                    f"{self.config_path}: {type(e).__name__}: {e}. "
                    "Cause: File write error or permission denied. "
                    "Try: Check directory exists and has write permissions, "
                    "or verify disk space is available."
                )
            ) from e

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.config = ValidationConfigModel()

    def validate_config(self) -> list[str]:
        """
        Validate configuration structure and values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Pydantic already validates structure, but we can add business logic validation
        self._validate_enabled_type(errors)
        self._validate_quality_weights_sum(errors)

        return errors

    def _validate_enabled_type(self, errors: list[str]) -> None:
        enabled = self.config.enabled
        if not isinstance(enabled, bool):
            errors.append(
                (
                    "Invalid 'enabled' value: 'enabled' must be a boolean "
                    "(true/false). "
                    f"Got {type(enabled).__name__}. "
                    "Try: Set 'enabled' to true or false in "
                    "'.cortex/validation.json'."
                )
            )

    def _validate_quality_weights_sum(self, errors: list[str]) -> None:
        """Validate that quality weights sum to 1.0.

        Args:
            errors: List to append validation errors to
        """
        weights = self.config.quality.weights
        weight_sum = (
            weights.completeness
            + weights.consistency
            + weights.freshness
            + weights.structure
            + weights.token_efficiency
        )
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point error
            errors.append(
                (
                    f"Invalid 'quality.weights' sum: Must sum to 1.0, "
                    f"currently {weight_sum}. "
                    "Try: Adjust weight values so they add up to 1.0, "
                    "e.g., {'completeness': 0.3, 'consistency': 0.3, "
                    "'freshness': 0.2, 'structure': 0.1, "
                    "'token_efficiency': 0.1}."
                )
            )

    def is_validation_enabled(self) -> bool:
        """
        Check if validation is enabled.

        Returns:
            True if validation is enabled
        """
        enabled = self.config.enabled
        return enabled if isinstance(enabled, bool) else True

    def is_auto_validate_enabled(self) -> bool:
        """
        Check if auto-validation on write is enabled.

        Returns:
            True if auto-validation is enabled
        """
        return self.config.auto_validate_on_write

    def is_strict_mode(self) -> bool:
        """
        Check if strict mode is enabled.

        Returns:
            True if strict mode is enabled
        """
        return self.config.strict_mode

    def get_token_budget_max(self) -> int:
        """
        Get maximum total tokens allowed.

        Returns:
            Max total tokens
        """
        return self.config.token_budget.max_total_tokens

    def get_token_budget_warn_threshold(self) -> float:
        """
        Get token budget warning threshold percentage.

        Returns:
            Warning threshold (0-100)
        """
        return self.config.token_budget.warn_at_percentage

    def get_duplication_threshold(self) -> float:
        """
        Get duplication similarity threshold.

        Returns:
            Similarity threshold (0.0-1.0)
        """
        return self.config.duplication.threshold

    def get_quality_minimum_score(self) -> float:
        """
        Get minimum acceptable quality score.

        Returns:
            Minimum score (0-100)
        """
        return self.config.quality.minimum_score
