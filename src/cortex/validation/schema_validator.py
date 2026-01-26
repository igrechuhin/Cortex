"""
Schema validation for Memory Bank files.

This module provides schema validation to ensure Memory Bank files
contain required sections and follow proper structure.
"""

import json
import re
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue
from cortex.validation.models import FileSchemaModel, ValidationError, ValidationResult

# Default schemas for Memory Bank files
SchemaDict = dict[str, list[str] | int]


DEFAULT_SCHEMAS: dict[str, SchemaDict] = {
    "memorybankinstructions.md": {
        "required_sections": ["Purpose", "Guidelines", "Structure"],
        "recommended_sections": ["Best Practices", "Examples"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "projectBrief.md": {
        "required_sections": [
            "Project Overview",
            "Goals",
            "Core Requirements",
            "Success Criteria",
        ],
        "recommended_sections": ["Constraints", "Key Decisions"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "productContext.md": {
        "required_sections": ["Product Overview", "Target Users", "Key Features"],
        "recommended_sections": ["User Stories", "Market Context"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "activeContext.md": {
        "required_sections": ["Current Focus", "Recent Changes", "Next Steps"],
        "recommended_sections": ["Active Decisions", "Important Patterns"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "systemPatterns.md": {
        "required_sections": [
            "Architecture",
            "Design Patterns",
            "Component Relationships",
        ],
        "recommended_sections": ["Critical Paths", "Integration Points"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "techContext.md": {
        "required_sections": ["Technology Stack", "Dependencies", "Development Setup"],
        "recommended_sections": ["Build Process", "Testing Strategy"],
        "heading_level": 2,
        "max_nesting": 3,
    },
    "progress.md": {
        "required_sections": ["What Works", "What's Left"],
        "recommended_sections": ["Known Issues", "Recent Milestones"],
        "heading_level": 2,
        "max_nesting": 3,
    },
}


class SchemaValidator:
    """Validate Memory Bank files against defined schemas."""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize schema validator.

        Args:
            config_path: Optional path to custom schema config
        """
        self.schemas: dict[str, FileSchemaModel] = {
            file_name: FileSchemaModel.model_validate(schema)
            for file_name, schema in DEFAULT_SCHEMAS.items()
        }
        if config_path and config_path.exists():
            custom_schemas = self.load_custom_schemas(config_path)
            if custom_schemas:
                self.schemas.update(custom_schemas)

    async def validate_file(
        self, file_name: str, content: str, file_type: str | None = None
    ) -> ValidationResult:
        """
        Validate file against schema.

        Args:
            file_name: Name of file
            content: File content
            file_type: Optional file type override

        Returns:
            {
                "valid": bool,
                "errors": [...],
                "warnings": [...],
                "score": 0-100
            }
        """
        schema_key = file_type or file_name
        schema = self.schemas.get(schema_key)

        if not schema:
            return _handle_no_schema(file_name)

        sections = self.extract_sections(content)
        errors, warnings = _run_all_validations(self, sections, content, schema)
        score = self.calculate_score(errors, warnings, schema)

        return _build_validation_result(errors, warnings, score)

    def get_schema(self, file_name: str) -> FileSchemaModel | None:
        """
        Get schema definition for file.

        Args:
            file_name: Name of file

        Returns:
            FileSchemaModel or None if no schema defined
        """
        return self.schemas.get(file_name)

    def load_custom_schemas(self, config_path: Path) -> dict[str, FileSchemaModel]:
        """
        Load user-defined schemas.

        Args:
            config_path: Path to custom schema config

        Returns:
            Dictionary of custom schemas as FileSchemaModel instances

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        try:
            with open(config_path) as f:
                config_raw = cast(JsonValue, json.load(f))
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to load custom schemas from {config_path}: {e}")
            return {}

        # Validate config type
        if not isinstance(config_raw, dict):
            return {}

        config = cast(dict[str, JsonValue], config_raw)
        custom_schemas_raw: JsonValue = config.get("custom_schemas", {})
        if not isinstance(custom_schemas_raw, dict):
            return {}

        custom_schemas_dict = cast(dict[str, JsonValue], custom_schemas_raw)
        result: dict[str, FileSchemaModel] = {}
        for file_name, schema_data in custom_schemas_dict.items():
            if isinstance(schema_data, dict):
                result[file_name] = FileSchemaModel.model_validate(schema_data)
            elif isinstance(schema_data, FileSchemaModel):
                result[file_name] = schema_data

        return result

    def extract_sections(self, content: str) -> list[str]:
        """
        Extract section headings from content.

        Args:
            content: File content

        Returns:
            List of section titles (without # prefix)
        """
        sections: list[str] = []
        lines = content.split("\n")

        for line in lines:
            # Match headings (## or more #)
            match = re.match(r"^(#{2,})\s+(.+)$", line)
            if match:
                # Only include level 2 headings (##) as main sections
                if len(match.group(1)) == 2:
                    sections.append(match.group(2).strip())

        return sections

    def check_required_sections(
        self, sections: list[str], required: list[str]
    ) -> list[ValidationError]:
        """
        Check if required sections are present.

        Args:
            sections: Actual sections found
            required: Required sections

        Returns:
            List of error dictionaries
        """
        errors: list[ValidationError] = []

        for req_section in required:
            if req_section not in sections:
                errors.append(
                    ValidationError(
                        type="missing_section",
                        severity="error",
                        message=f"Required section '{req_section}' not found",
                        suggestion=f"Add '## {req_section}' section to the file",
                    )
                )

        return errors

    def check_recommended_sections(
        self, sections: list[str], recommended: list[str]
    ) -> list[ValidationError]:
        """
        Check if recommended sections are present.

        Args:
            sections: Actual sections found
            recommended: Recommended sections

        Returns:
            List of warning dictionaries
        """
        warnings: list[ValidationError] = []

        for rec_section in recommended:
            if rec_section not in sections:
                warnings.append(
                    ValidationError(
                        type="missing_recommended_section",
                        severity="warning",
                        message=f"Recommended section '{rec_section}' not found",
                        suggestion=f"Consider adding '## {rec_section}' section",
                    )
                )

        return warnings

    def check_heading_levels(
        self,
        content: str,
        expected_level: int,  # noqa: ARG002
        max_nesting: int,
    ) -> list[ValidationError]:
        """
        Check for proper heading hierarchy.

        Args:
            content: File content
            expected_level: Expected level for main sections (2 for ##)
            max_nesting: Maximum nesting level allowed

        Returns:
            List of error dictionaries
        """
        errors: list[ValidationError] = []
        lines = content.split("\n")
        prev_level = 0

        for i, line in enumerate(lines, 1):
            match = re.match(r"^(#{1,})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                heading_text = match.group(2).strip()

                self._check_heading_level_skip(errors, i, prev_level, level)
                self._check_heading_too_deep(
                    errors, i, heading_text, level, max_nesting
                )

                prev_level = level

        return errors

    def _check_heading_level_skip(
        self, errors: list[ValidationError], line_num: int, prev_level: int, level: int
    ) -> None:
        """Check if heading level skips."""
        if prev_level > 0 and level > prev_level + 1:
            errors.append(
                ValidationError(
                    type="heading_level_skip",
                    severity="error",
                    message=f"Line {line_num}: Heading level skip detected (level {prev_level} -> {level})",
                    suggestion=f"Use incremental heading levels. After {'#' * prev_level}, use {'#' * (prev_level + 1)}",
                )
            )

    def _check_heading_too_deep(
        self,
        errors: list[ValidationError],
        line_num: int,
        heading_text: str,
        level: int,
        max_nesting: int,
    ) -> None:
        """Check if heading is too deeply nested."""
        if level > max_nesting + 1:  # +1 because we start counting from #
            errors.append(
                ValidationError(
                    type="heading_too_deep",
                    severity="warning",
                    message=f"Line {line_num}: Heading '{heading_text}' is too deeply nested (level {level})",
                    suggestion=f"Consider restructuring to use at most {max_nesting + 1} levels",
                )
            )

    def calculate_score(
        self,
        errors: list[ValidationError],
        warnings: list[ValidationError],
        schema: FileSchemaModel,  # noqa: ARG002
    ) -> int:
        """
        Calculate validation score (0-100).

        Args:
            errors: List of errors
            warnings: List of warnings
            schema: Schema definition

        Returns:
            Score from 0 to 100
        """
        # Start with 100
        score = 100

        # Deduct 15 points per error
        score -= len(errors) * 15

        # Deduct 5 points per warning
        score -= len(warnings) * 5

        # Ensure score doesn't go below 0
        score = max(0, score)

        return score


def _handle_no_schema(file_name: str) -> ValidationResult:
    """Handle case when no schema is defined for file.

    Args:
        file_name: Name of file

    Returns:
        Validation result with info warning
    """
    return ValidationResult(
        valid=True,
        errors=[],
        warnings=[
            ValidationError(
                type="no_schema",
                severity="info",
                message=f"No validation schema defined for '{file_name}'",
                suggestion=None,
            )
        ],
        score=100,
    )


def _run_all_validations(
    validator: SchemaValidator,
    sections: list[str],
    content: str,
    schema: FileSchemaModel,
) -> tuple[list[ValidationError], list[ValidationError]]:
    """Run all validation checks on file.

    Args:
        validator: SchemaValidator instance
        sections: Extracted sections from content
        content: File content
        schema: Schema definition

    Returns:
        Tuple of (errors, warnings)
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    errors.extend(validator.check_required_sections(sections, schema.required_sections))
    warnings.extend(
        validator.check_recommended_sections(sections, schema.recommended_sections)
    )
    errors.extend(
        validator.check_heading_levels(
            content, schema.heading_level, schema.max_nesting
        )
    )

    return errors, warnings


def _build_validation_result(
    errors: list[ValidationError],
    warnings: list[ValidationError],
    score: int,
) -> ValidationResult:
    """Build final validation result.

    Args:
        errors: List of validation errors
        warnings: List of validation warnings
        score: Calculated validation score

    Returns:
        Complete validation result
    """
    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        score=score,
    )
