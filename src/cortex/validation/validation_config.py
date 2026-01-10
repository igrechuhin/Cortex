"""
Validation configuration management.

This module manages user-configurable validation rules and settings
for Memory Bank validation.
"""

import copy
import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.constants import (
    DEFAULT_TOKEN_BUDGET,
    MIN_SECTION_LENGTH_CHARS,
    QUALITY_WEIGHT_COMPLETENESS,
    QUALITY_WEIGHT_CONSISTENCY,
    QUALITY_WEIGHT_EFFICIENCY,
    QUALITY_WEIGHT_FRESHNESS,
    QUALITY_WEIGHT_STRUCTURE,
    SIMILARITY_THRESHOLD_DUPLICATE,
)

DEFAULT_CONFIG: dict[str, object] = {
    "enabled": True,
    "auto_validate_on_write": True,
    "strict_mode": False,
    "token_budget": {
        "max_total_tokens": DEFAULT_TOKEN_BUDGET,
        "warn_at_percentage": 80,
        "per_file_max": 15000,
        "per_file_warn": 12000,
    },
    "duplication": {
        "enabled": True,
        "threshold": SIMILARITY_THRESHOLD_DUPLICATE,
        "min_length": MIN_SECTION_LENGTH_CHARS,
        "suggest_transclusion": True,
    },
    "schemas": {
        "enforce_required_sections": True,
        "enforce_section_order": False,
        "custom_schemas": {},
    },
    "quality": {
        "minimum_score": 70,
        "fail_below": 50,
        "weights": {
            "completeness": QUALITY_WEIGHT_COMPLETENESS,
            "consistency": QUALITY_WEIGHT_CONSISTENCY,
            "freshness": QUALITY_WEIGHT_FRESHNESS,
            "structure": QUALITY_WEIGHT_STRUCTURE,
            "token_efficiency": QUALITY_WEIGHT_EFFICIENCY,
        },
    },
}


class ValidationConfig:
    """Manage validation configuration."""

    def __init__(self, project_root: Path):
        """
        Initialize with project root.

        Args:
            project_root: Path to project root
        """
        self.project_root: Path = project_root
        self.config_path: Path = project_root / ".memory-bank-validation.json"
        self.config: dict[str, object] = self._load_config()

    def _load_config(self) -> dict[str, object]:
        """
        Load validation config from file or use defaults.

        Returns:
            Configuration dictionary

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    user_config_raw = cast(object, json.load(f))
                    if not isinstance(user_config_raw, dict):
                        return copy.deepcopy(DEFAULT_CONFIG)
                    user_config: dict[str, object] = cast(
                        dict[str, object], user_config_raw
                    )
                    # Merge with defaults (user config takes precedence)
                    return self.merge_configs(
                        copy.deepcopy(DEFAULT_CONFIG),
                        user_config,
                    )
            except Exception as e:
                error_detail = str(e)
                error_type = type(e).__name__
                print(
                    f"Failed to load validation config from {self.config_path}: {error_type}: {error_detail}. "
                    + "Cause: Invalid JSON format or file read error. "
                    + "Try: Fix JSON syntax errors, check file permissions, "
                    + "or delete config file to use default values."
                )
                return copy.deepcopy(DEFAULT_CONFIG)
        else:
            return copy.deepcopy(DEFAULT_CONFIG)

    def merge_configs(
        self, default: dict[str, object], user: dict[str, object]
    ) -> dict[str, object]:
        """
        Recursively merge user config with defaults.

        Args:
            default: Default configuration
            user: User configuration

        Returns:
            Merged configuration
        """
        result = default.copy()

        for key, value in user.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_configs(
                    cast(dict[str, object], result[key]), cast(dict[str, object], value)
                )
            else:
                result[key] = value

        return result

    def get(self, key: str, default: object = None) -> object:
        """
        Get config value with dot notation support.

        Args:
            key: Config key (supports dot notation like "token_budget.max_total_tokens")
            default: Default value if key not found

        Returns:
            Config value or default
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: object) -> None:
        """
        Set config value with dot notation support.

        Args:
            key: Config key (supports dot notation)
            value: Value to set
        """
        keys = key.split(".")
        config: dict[str, object] = self.config

        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = cast(dict[str, object], config[k])

        # Set the value
        config[keys[-1]] = value

    async def save(self) -> None:
        """
        Save configuration to file.

        Raises:
            IOError: If save fails
        """
        try:
            async with open_async_text_file(self.config_path, "w", "utf-8") as f:
                _ = await f.write(json.dumps(self.config, indent=2))
        except Exception as e:
            raise OSError(
                f"Failed to save validation config to {self.config_path}: {type(e).__name__}: {e}. "
                + "Cause: File write error or permission denied. "
                + "Try: Check directory exists and has write permissions, "
                + "or verify disk space is available."
            ) from e

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""

        self.config = copy.deepcopy(DEFAULT_CONFIG)

    def validate_config(self) -> list[str]:
        """
        Validate configuration structure and values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        self._validate_enabled_flag(errors)
        self._validate_token_budget(errors)
        self._validate_duplication(errors)
        self._validate_quality(errors)

        return errors

    def _validate_enabled_flag(self, errors: list[str]) -> None:
        """Validate enabled flag.

        Args:
            errors: List to append validation errors to
        """
        if not isinstance(self.config.get("enabled"), bool):
            errors.append(
                "Invalid 'enabled' value: Must be boolean (true or false). "
                + "Try: Set 'enabled': true or 'enabled': false in config."
            )

    def _validate_token_budget(self, errors: list[str]) -> None:
        """Validate token budget configuration.

        Args:
            errors: List to append validation errors to
        """
        token_budget_raw = self.config.get("token_budget", {})
        if not isinstance(token_budget_raw, dict):
            errors.append(
                "Invalid 'token_budget' value: Must be an object with token limits. "
                + "Try: Set 'token_budget': {'max_total_tokens': 100000, 'warn_at_percentage': 80}."
            )
            return

        token_budget = cast(dict[str, object], token_budget_raw)
        max_tokens = token_budget.get("max_total_tokens")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            errors.append(
                f"Invalid 'token_budget.max_total_tokens' value: Must be a positive integer, got {max_tokens}. "
                + "Try: Set a valid value like 100000."
            )

        warn_pct = token_budget.get("warn_at_percentage")
        if not isinstance(warn_pct, (int, float)) or not 0 <= warn_pct <= 100:
            errors.append(
                f"Invalid 'token_budget.warn_at_percentage' value: Must be between 0 and 100, got {warn_pct}. "
                + "Try: Set a value like 80 for 80% warning threshold."
            )

    def _validate_duplication(self, errors: list[str]) -> None:
        """Validate duplication configuration.

        Args:
            errors: List to append validation errors to
        """
        duplication_raw = self.config.get("duplication", {})
        if not isinstance(duplication_raw, dict):
            errors.append(
                "Invalid 'duplication' value: Must be an object with similarity detection settings. "
                + "Try: Set 'duplication': {'enabled': true, 'threshold': 0.85}."
            )
            return

        duplication = cast(dict[str, object], duplication_raw)
        threshold = duplication.get("threshold")
        if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            errors.append(
                f"Invalid 'duplication.threshold' value: Must be between 0.0 and 1.0, got {threshold}. "
                + "Try: Set a value like 0.85 for 85% similarity threshold."
            )

        min_length = duplication.get("min_length")
        if not isinstance(min_length, int) or min_length < 0:
            errors.append(
                f"Invalid 'duplication.min_length' value: Must be a non-negative integer, got {min_length}. "
                + "Try: Set a value like 50 for minimum 50 character sections."
            )

    def _validate_quality(self, errors: list[str]) -> None:
        """Validate quality configuration.

        Args:
            errors: List to append validation errors to
        """
        quality_raw = self.config.get("quality", {})
        if not isinstance(quality_raw, dict):
            errors.append(
                "Invalid 'quality' value: Must be an object with quality score settings. "
                + "Try: Set 'quality': {'minimum_score': 70, 'fail_below': 50}."
            )
            return

        quality = cast(dict[str, object], quality_raw)
        min_score = quality.get("minimum_score")
        if not isinstance(min_score, (int, float)) or not 0 <= min_score <= 100:
            errors.append(
                f"Invalid 'quality.minimum_score' value: Must be between 0 and 100, got {min_score}. "
                + "Try: Set a value like 70 for 70% minimum quality."
            )

        fail_below = quality.get("fail_below")
        if not isinstance(fail_below, (int, float)) or not 0 <= fail_below <= 100:
            errors.append(
                f"Invalid 'quality.fail_below' value: Must be between 0 and 100, got {fail_below}. "
                + "Try: Set a value like 50 for failure below 50% quality."
            )

        self._validate_quality_weights(quality, errors)

    def _validate_quality_weights(
        self, quality: dict[str, object], errors: list[str]
    ) -> None:
        """Validate quality weights configuration.

        Args:
            quality: Quality configuration dictionary
            errors: List to append validation errors to
        """
        weights_raw = quality.get("weights", {})
        if not isinstance(weights_raw, dict):
            return

        weights = cast(dict[str, object], weights_raw)
        weight_values = [v for v in weights.values() if isinstance(v, (int, float))]
        weight_sum = sum(weight_values)
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point error
            errors.append(
                f"Invalid 'quality.weights' sum: Must sum to 1.0, currently {weight_sum}. "
                + "Try: Adjust weight values so they add up to 1.0, "
                + "e.g., {'completeness': 0.3, 'consistency': 0.3, 'freshness': 0.2, 'structure': 0.1, 'token_efficiency': 0.1}."
            )

    def to_dict(self) -> dict[str, object]:
        """
        Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def is_validation_enabled(self) -> bool:
        """
        Check if validation is enabled.

        Returns:
            True if validation is enabled
        """
        return cast(bool, self.config.get("enabled", True))

    def is_auto_validate_enabled(self) -> bool:
        """
        Check if auto-validation on write is enabled.

        Returns:
            True if auto-validation is enabled
        """
        return cast(bool, self.config.get("auto_validate_on_write", True))

    def is_strict_mode(self) -> bool:
        """
        Check if strict mode is enabled.

        Returns:
            True if strict mode is enabled
        """
        return cast(bool, self.config.get("strict_mode", False))

    def get_token_budget_max(self) -> int:
        """
        Get maximum total tokens allowed.

        Returns:
            Max total tokens
        """
        token_budget_raw: object = self.config.get("token_budget", {})
        if isinstance(token_budget_raw, dict):
            token_budget = cast(dict[str, object], token_budget_raw)
            return cast(int, token_budget.get("max_total_tokens", 100000))
        return 100000

    def get_token_budget_warn_threshold(self) -> float:
        """
        Get token budget warning threshold percentage.

        Returns:
            Warning threshold (0-100)
        """
        token_budget_raw: object = self.config.get("token_budget", {})
        if isinstance(token_budget_raw, dict):
            token_budget = cast(dict[str, object], token_budget_raw)
            return cast(float, token_budget.get("warn_at_percentage", 80))
        return 80.0

    def get_duplication_threshold(self) -> float:
        """
        Get duplication similarity threshold.

        Returns:
            Similarity threshold (0.0-1.0)
        """
        duplication_raw: object = self.config.get("duplication", {})
        if isinstance(duplication_raw, dict):
            duplication = cast(dict[str, object], duplication_raw)
            return cast(
                float, duplication.get("threshold", SIMILARITY_THRESHOLD_DUPLICATE)
            )
        return SIMILARITY_THRESHOLD_DUPLICATE

    def get_quality_minimum_score(self) -> float:
        """
        Get minimum acceptable quality score.

        Returns:
            Minimum score (0-100)
        """
        quality_raw: object = self.config.get("quality", {})
        if isinstance(quality_raw, dict):
            quality = cast(dict[str, object], quality_raw)
            return cast(float, quality.get("minimum_score", 70))
        return 70.0
