"""
Tests for schema_validator.py - Schema validation for Memory Bank files.

Tests cover:
- Validator initialization with default and custom schemas
- File validation with required and recommended sections
- Heading level validation and nesting checks
- Section extraction from markdown content
- Score calculation based on errors and warnings
- Custom schema loading from configuration files
"""

import json
from pathlib import Path

import pytest

from cortex.validation.models import FileSchemaModel, ValidationError
from cortex.validation.schema_validator import DEFAULT_SCHEMAS, SchemaValidator


@pytest.mark.unit
class TestSchemaValidatorInitialization:
    """Tests for SchemaValidator initialization."""

    @pytest.mark.asyncio
    async def test_initialization_with_default_schemas(self, tmp_path: Path) -> None:
        """Test validator initializes with default schemas."""
        validator = SchemaValidator()

        # Should have all default schemas
        assert len(validator.schemas) == len(DEFAULT_SCHEMAS)
        assert "memorybankinstructions.md" in validator.schemas
        assert "projectBrief.md" in validator.schemas
        assert "activeContext.md" in validator.schemas

        # Check schema structure
        schema = validator.schemas["projectBrief.md"]
        assert hasattr(schema, "required_sections")
        assert hasattr(schema, "recommended_sections")
        assert hasattr(schema, "heading_level")
        assert hasattr(schema, "max_nesting")

    @pytest.mark.asyncio
    async def test_initialization_with_custom_schemas(self, tmp_path: Path) -> None:
        """Test validator loads custom schemas from config file."""
        # Create custom schema config
        config_path = tmp_path / "custom-schemas.json"
        custom_schemas = {
            "custom_schemas": {
                "custom.md": {
                    "required_sections": ["Custom Section"],
                    "recommended_sections": ["Optional Section"],
                    "heading_level": 2,
                    "max_nesting": 2,
                }
            }
        }
        _ = config_path.write_text(json.dumps(custom_schemas))

        validator = SchemaValidator(config_path=config_path)

        # Should have both default and custom schemas
        assert "memorybankinstructions.md" in validator.schemas
        assert "custom.md" in validator.schemas
        assert validator.schemas["custom.md"].required_sections == ["Custom Section"]

    @pytest.mark.asyncio
    async def test_initialization_with_nonexistent_config(self, tmp_path: Path) -> None:
        """Test validator handles nonexistent config file gracefully."""
        config_path = tmp_path / "nonexistent.json"
        validator = SchemaValidator(config_path=config_path)

        # Should only have default schemas
        assert len(validator.schemas) == len(DEFAULT_SCHEMAS)


@pytest.mark.unit
class TestValidateFile:
    """Tests for validate_file method."""

    @pytest.mark.asyncio
    async def test_validate_file_with_valid_content(self):
        """Test validation passes for file with all required sections."""
        validator = SchemaValidator()
        content = """
# Memory Bank Instructions

## Purpose
This is the purpose section.

## Guidelines
These are the guidelines.

## Structure
This is the structure.
"""
        result = await validator.validate_file("memorybankinstructions.md", content)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.score >= 85  # May have warnings for recommended sections

    @pytest.mark.asyncio
    async def test_validate_file_with_missing_required_sections(self):
        """Test validation fails for file missing required sections."""
        validator = SchemaValidator()
        content = """
# Memory Bank Instructions

## Purpose
This is the purpose section.
"""
        result = await validator.validate_file("memorybankinstructions.md", content)

        assert result.valid is False
        assert len(result.errors) >= 2  # Missing Guidelines and Structure

        # Check error messages
        error_messages = [e.message for e in result.errors]
        assert any("Guidelines" in msg for msg in error_messages)
        assert any("Structure" in msg for msg in error_messages)

    @pytest.mark.asyncio
    async def test_validate_file_with_missing_recommended_sections(self):
        """Test validation warns for missing recommended sections."""
        validator = SchemaValidator()
        content = """
# Memory Bank Instructions

## Purpose
This is the purpose section.

## Guidelines
These are the guidelines.

## Structure
This is the structure.
"""
        result = await validator.validate_file("memorybankinstructions.md", content)

        assert result.valid is True  # Still valid
        assert len(result.warnings) >= 2  # Missing recommended sections

        # Check warning messages
        warning_messages = [w.message for w in result.warnings]
        assert any("Best Practices" in msg for msg in warning_messages)
        assert any("Examples" in msg for msg in warning_messages)

    @pytest.mark.asyncio
    async def test_validate_file_with_heading_level_skip(self):
        """Test validation catches heading level skips."""
        validator = SchemaValidator()
        content = """
# Memory Bank Instructions

## Purpose
This is the purpose section.

#### Subsection
This skips level 3.

## Guidelines
These are the guidelines.

## Structure
This is the structure.
"""
        result = await validator.validate_file("memorybankinstructions.md", content)

        assert result.valid is False

        # Check for heading level skip error
        heading_errors = [
            e
            for e in result.errors
            if hasattr(e, "type") and e.type == "heading_level_skip"
        ]
        if not heading_errors:
            # Fallback: check message content
            heading_errors = [e for e in result.errors if "skip" in e.message.lower()]
        assert len(heading_errors) >= 1
        assert heading_errors[0].message.lower().find("skip") != -1

    @pytest.mark.asyncio
    async def test_validate_file_with_excessive_nesting(self):
        """Test validation warns about excessive heading nesting."""
        validator = SchemaValidator()
        content = """
# Memory Bank Instructions

## Purpose
This is the purpose section.

### Subsection
This is fine.

#### Another level
This is fine.

##### Too deep
This exceeds max_nesting of 3.

## Guidelines
These are the guidelines.

## Structure
This is the structure.
"""
        result = await validator.validate_file("memorybankinstructions.md", content)

        # Check for deep nesting warning
        nesting_errors = [
            e
            for e in result.errors
            if hasattr(e, "type") and e.type == "heading_too_deep"
        ]
        if not nesting_errors:
            # Fallback: check message content
            nesting_errors = [e for e in result.errors if "Too deep" in e.message]
        assert len(nesting_errors) >= 1
        assert nesting_errors[0].message.find("Too deep") != -1

    @pytest.mark.asyncio
    async def test_validate_file_without_schema(self):
        """Test validation for file with no defined schema."""
        validator = SchemaValidator()
        content = "# Custom File\n\nSome content."

        result = await validator.validate_file("custom.md", content)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert (
            hasattr(result.warnings[0], "type")
            and result.warnings[0].type == "no_schema"
        )
        assert result.score == 100

    @pytest.mark.asyncio
    async def test_validate_file_with_file_type_override(self):
        """Test validation with file_type parameter override."""
        validator = SchemaValidator()
        content = """
# Project Brief

## Project Overview
Overview section.

## Goals
Goals section.

## Core Requirements
Requirements section.

## Success Criteria
Success criteria section.
"""
        # Validate with file_type override
        result = await validator.validate_file(
            "different-name.md", content, file_type="projectBrief.md"
        )

        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_file_score_calculation(self):
        """Test score calculation based on errors and warnings."""
        validator = SchemaValidator()

        # File with all required sections (no errors, may have warnings)
        perfect_content = """
# Memory Bank Instructions

## Purpose
Purpose content.

## Guidelines
Guidelines content.

## Structure
Structure content.

## Best Practices
Best practices content.

## Examples
Examples content.
"""
        result = await validator.validate_file(
            "memorybankinstructions.md", perfect_content
        )
        assert result.score == 100

        # File with missing required sections (errors)
        error_content = """
# Memory Bank Instructions

## Purpose
Purpose content.
"""
        result = await validator.validate_file(
            "memorybankinstructions.md", error_content
        )
        assert result.score < 80  # Should be significantly penalized


@pytest.mark.unit
class TestGetSchema:
    """Tests for get_schema method."""

    @pytest.mark.asyncio
    async def test_get_schema_for_known_file(self):
        """Test getting schema for known file type."""
        validator = SchemaValidator()

        schema = validator.get_schema("projectBrief.md")

        assert schema is not None
        assert hasattr(schema, "required_sections")
        required_sections = schema.required_sections
        assert isinstance(required_sections, list)
        assert "Project Overview" in required_sections
        assert "Goals" in required_sections

    @pytest.mark.asyncio
    async def test_get_schema_for_unknown_file(self):
        """Test getting schema for unknown file type."""
        validator = SchemaValidator()

        schema = validator.get_schema("unknown.md")

        assert schema is None


@pytest.mark.unit
class TestExtractSections:
    """Tests for _extract_sections method."""

    @pytest.mark.asyncio
    async def test_extract_sections_from_content(self):
        """Test extracting sections from markdown content."""
        validator = SchemaValidator()
        content = """
# Main Title

## Section One
Content here.

## Section Two
More content.

### Subsection
This should not be extracted as a main section.

## Section Three
Final section.
"""
        sections = validator.extract_sections(content)

        assert len(sections) == 3
        assert "Section One" in sections
        assert "Section Two" in sections
        assert "Section Three" in sections
        assert "Subsection" not in sections  # Level 3 heading

    @pytest.mark.asyncio
    async def test_extract_sections_with_no_sections(self):
        """Test extracting sections from content with no level 2 headings."""
        validator = SchemaValidator()
        content = """
# Main Title

Some content without level 2 headings.

### Subsection
Only deeper headings.
"""
        sections = validator.extract_sections(content)

        assert len(sections) == 0

    @pytest.mark.asyncio
    async def test_extract_sections_with_extra_whitespace(self):
        """Test extracting sections handles extra whitespace."""
        validator = SchemaValidator()
        content = """
##   Section With Spaces

##Section Without Space

## Normal Section
"""
        sections = validator.extract_sections(content)

        assert len(sections) == 2  # Should handle both formats
        assert "Section With Spaces" in sections
        assert "Normal Section" in sections


@pytest.mark.unit
class TestCheckRequiredSections:
    """Tests for _check_required_sections method."""

    @pytest.mark.asyncio
    async def test_check_required_sections_all_present(self):
        """Test checking required sections when all are present."""
        validator = SchemaValidator()
        sections = ["Purpose", "Guidelines", "Structure"]
        required = ["Purpose", "Guidelines", "Structure"]

        errors = validator.check_required_sections(sections, required)

        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_check_required_sections_some_missing(self):
        """Test checking required sections when some are missing."""
        validator = SchemaValidator()
        sections = ["Purpose"]
        required = ["Purpose", "Guidelines", "Structure"]

        errors = validator.check_required_sections(sections, required)

        assert len(errors) == 2
        assert all(e.type == "missing_section" for e in errors)
        assert all(e.severity == "error" for e in errors)

        # Check error messages mention missing sections
        error_messages = [e.message for e in errors]
        assert any("Guidelines" in msg for msg in error_messages)
        assert any("Structure" in msg for msg in error_messages)

    @pytest.mark.asyncio
    async def test_check_required_sections_with_empty_required(self):
        """Test checking required sections with empty required list."""
        validator = SchemaValidator()
        sections = ["Purpose", "Guidelines"]
        required: list[str] = []

        errors = validator.check_required_sections(sections, required)

        assert len(errors) == 0


@pytest.mark.unit
class TestCheckRecommendedSections:
    """Tests for _check_recommended_sections method."""

    @pytest.mark.asyncio
    async def test_check_recommended_sections_all_present(self):
        """Test checking recommended sections when all are present."""
        validator = SchemaValidator()
        sections = ["Purpose", "Best Practices", "Examples"]
        recommended = ["Best Practices", "Examples"]

        warnings = validator.check_recommended_sections(sections, recommended)

        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_check_recommended_sections_some_missing(self):
        """Test checking recommended sections when some are missing."""
        validator = SchemaValidator()
        sections = ["Purpose"]
        recommended = ["Best Practices", "Examples"]

        warnings = validator.check_recommended_sections(sections, recommended)

        assert len(warnings) == 2
        assert all(w.type == "missing_recommended_section" for w in warnings)
        assert all(w.severity == "warning" for w in warnings)

        # Check warning messages mention missing sections
        warning_messages = [w.message for w in warnings]
        assert any("Best Practices" in msg for msg in warning_messages)
        assert any("Examples" in msg for msg in warning_messages)


@pytest.mark.unit
class TestCheckHeadingLevels:
    """Tests for _check_heading_levels method."""

    @pytest.mark.asyncio
    async def test_check_heading_levels_valid_hierarchy(self):
        """Test checking heading levels with valid hierarchy."""
        validator = SchemaValidator()
        content = """
# Title

## Section

### Subsection

#### Sub-subsection
"""
        errors = validator.check_heading_levels(
            content, expected_level=2, max_nesting=3
        )

        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_check_heading_levels_with_skip(self):
        """Test checking heading levels with level skip."""
        validator = SchemaValidator()
        content = """
# Title

## Section

#### Skipped Level
"""
        errors = validator.check_heading_levels(
            content, expected_level=2, max_nesting=3
        )

        skip_errors = [e for e in errors if e.type == "heading_level_skip"]
        assert len(skip_errors) >= 1
        assert skip_errors[0].message.lower().find("skip") != -1

    @pytest.mark.asyncio
    async def test_check_heading_levels_excessive_nesting(self):
        """Test checking heading levels with excessive nesting."""
        validator = SchemaValidator()
        content = """
# Title

## Section

### Subsection

#### Sub-subsection

##### Too Deep
"""
        errors = validator.check_heading_levels(
            content, expected_level=2, max_nesting=3
        )

        deep_errors = [e for e in errors if e.type == "heading_too_deep"]
        assert len(deep_errors) >= 1
        assert deep_errors[0].message.lower().find("too deeply nested") != -1


@pytest.mark.unit
class TestCalculateScore:
    """Tests for _calculate_score method."""

    @pytest.mark.asyncio
    async def test_calculate_score_perfect(self):
        """Test score calculation with no errors or warnings."""

        validator = SchemaValidator()
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        schema = FileSchemaModel()

        score = validator.calculate_score(errors, warnings, schema)

        assert score == 100

    @pytest.mark.asyncio
    async def test_calculate_score_with_errors(self):
        """Test score calculation with errors."""

        validator = SchemaValidator()
        errors = [
            ValidationError(
                type="error1", severity="error", message="first", suggestion=None
            ),
            ValidationError(
                type="error2", severity="error", message="second", suggestion=None
            ),
        ]
        warnings: list[ValidationError] = []
        schema = FileSchemaModel()

        score = validator.calculate_score(errors, warnings, schema)

        # 100 - (2 * 15) = 70
        assert score == 70

    @pytest.mark.asyncio
    async def test_calculate_score_with_warnings(self):
        """Test score calculation with warnings."""

        validator = SchemaValidator()
        errors: list[ValidationError] = []
        warnings = [
            ValidationError(
                type="warning1", severity="warning", message="first", suggestion=None
            ),
            ValidationError(
                type="warning2", severity="warning", message="second", suggestion=None
            ),
        ]
        schema = FileSchemaModel()

        score = validator.calculate_score(errors, warnings, schema)

        # 100 - (2 * 5) = 90
        assert score == 90

    @pytest.mark.asyncio
    async def test_calculate_score_with_both(self):
        """Test score calculation with errors and warnings."""

        validator = SchemaValidator()
        errors = [
            ValidationError(
                type="error1", severity="error", message="err", suggestion=None
            )
        ]
        warnings = [
            ValidationError(
                type="warning1", severity="warning", message="first", suggestion=None
            ),
            ValidationError(
                type="warning2", severity="warning", message="second", suggestion=None
            ),
        ]
        schema = FileSchemaModel()

        score = validator.calculate_score(errors, warnings, schema)

        # 100 - 15 - 10 = 75
        assert score == 75

    @pytest.mark.asyncio
    async def test_calculate_score_minimum_zero(self):
        """Test score calculation doesn't go below zero."""

        validator = SchemaValidator()
        errors = [
            ValidationError(
                type=f"error{i}",
                severity="error",
                message=f"err {i}",
                suggestion=None,
            )
            for i in range(10)
        ]
        warnings = [
            ValidationError(
                type=f"warning{i}",
                severity="warning",
                message=f"warn {i}",
                suggestion=None,
            )
            for i in range(10)
        ]
        schema = FileSchemaModel()

        score = validator.calculate_score(errors, warnings, schema)

        # Should be clamped to 0
        assert score == 0


@pytest.mark.unit
class TestLoadCustomSchemas:
    """Tests for _load_custom_schemas method."""

    @pytest.mark.asyncio
    async def test_load_custom_schemas_valid_file(self, tmp_path: Path) -> None:
        """Test loading custom schemas from valid JSON file."""
        validator = SchemaValidator()

        config_path = tmp_path / "schemas.json"
        config_data = {
            "custom_schemas": {
                "custom1.md": {"required_sections": ["Section A", "Section B"]},
                "custom2.md": {"required_sections": ["Section X"]},
            }
        }
        _ = config_path.write_text(json.dumps(config_data))

        schemas = validator.load_custom_schemas(config_path)

        assert len(schemas) == 2
        assert "custom1.md" in schemas
        assert "custom2.md" in schemas
        custom1_schema = schemas["custom1.md"]
        required_sections = custom1_schema.required_sections
        assert required_sections == ["Section A", "Section B"]

    @pytest.mark.asyncio
    async def test_load_custom_schemas_invalid_json(self, tmp_path: Path) -> None:
        """Test loading custom schemas from invalid JSON file."""
        validator = SchemaValidator()

        config_path = tmp_path / "invalid.json"
        _ = config_path.write_text("{invalid json")

        schemas = validator.load_custom_schemas(config_path)

        assert schemas == {}

    @pytest.mark.asyncio
    async def test_load_custom_schemas_missing_key(self, tmp_path: Path) -> None:
        """Test loading custom schemas from file missing custom_schemas key."""
        validator = SchemaValidator()

        config_path = tmp_path / "schemas.json"
        config_data = {"other_key": "value"}
        _ = config_path.write_text(json.dumps(config_data))

        schemas = validator.load_custom_schemas(config_path)

        assert schemas == {}


@pytest.mark.unit
class TestSchemaValidatorIntegration:
    """Integration tests for SchemaValidator."""

    @pytest.mark.asyncio
    async def test_validate_all_default_file_types(self):
        """Test validation works for all default file types."""
        validator = SchemaValidator()

        for file_name in DEFAULT_SCHEMAS.keys():
            schema = validator.get_schema(file_name)
            assert schema is not None

            # Create content with all required sections
            content = f"# {file_name}\n\n"
            required_sections = schema.required_sections
            for section in required_sections:
                content += f"## {section}\n\nContent for {section}.\n\n"

            result = await validator.validate_file(file_name, content)

            assert result.valid is True
            assert len(result.errors) == 0
            assert result.score >= 85

    @pytest.mark.asyncio
    async def test_validate_file_complete_workflow(self, tmp_path: Path) -> None:
        """Test complete validation workflow with custom schemas."""
        # Create custom schema
        config_path = tmp_path / "schemas.json"
        config_data = {
            "custom_schemas": {
                "workflow.md": {
                    "required_sections": ["Setup", "Execution", "Cleanup"],
                    "recommended_sections": ["Troubleshooting"],
                    "heading_level": 2,
                    "max_nesting": 3,
                }
            }
        }
        _ = config_path.write_text(json.dumps(config_data))

        validator = SchemaValidator(config_path=config_path)

        # Test valid file
        valid_content = """
# Workflow

## Setup
Setup instructions.

## Execution
Execution steps.

## Cleanup
Cleanup procedures.

## Troubleshooting
Common issues.
"""
        result = await validator.validate_file("workflow.md", valid_content)
        assert result.valid is True
        assert result.score == 100

        # Test invalid file
        invalid_content = """
# Workflow

## Setup
Setup instructions.
"""
        result = await validator.validate_file("workflow.md", invalid_content)
        assert result.valid is False
        assert len(result.errors) >= 2  # Missing Execution and Cleanup
        assert result.score < 80
