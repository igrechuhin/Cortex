"""
Comprehensive tests for Phase 3: Validation and Quality Checks

This test suite covers:
- SchemaValidator: File validation against schemas
- DuplicationDetector: Finding duplicate content
- QualityMetrics: Calculating quality scores
- ValidationConfig: Configuration management
"""

from pathlib import Path
from typing import cast

import pytest

from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig

# ============================================================================
# Schema Validator Tests
# ============================================================================


class TestSchemaValidator:
    """Tests for SchemaValidator."""

    @pytest.mark.asyncio
    async def test_validate_valid_file(self):
        """Test validation of a valid file."""
        validator = SchemaValidator()

        content = """
## Project Overview
This is the overview.

## Goals
These are the goals.

## Core Requirements
These are the requirements.

## Success Criteria
These are the criteria.
"""

        from typing import cast

        result_raw = await validator.validate_file("projectBrief.md", content)
        result: dict[str, object] = cast(dict[str, object], result_raw)

        assert result.get("valid") is True
        errors_raw = result.get("errors", [])
        errors = cast(list[object], errors_raw) if isinstance(errors_raw, list) else []
        assert len(errors) == 0
        score = result.get("score", 0)
        assert isinstance(score, (int, float)) and score >= 90

    @pytest.mark.asyncio
    async def test_validate_missing_sections(self):
        """Test validation detects missing required sections."""
        validator = SchemaValidator()

        content = """
## Project Overview
This is the overview.

## Goals
These are the goals.
"""

        from typing import cast

        result_raw = await validator.validate_file("projectBrief.md", content)
        result: dict[str, object] = cast(dict[str, object], result_raw)

        assert result.get("valid") is False
        errors_raw = result.get("errors", [])
        errors = cast(list[object], errors_raw) if isinstance(errors_raw, list) else []
        assert len(errors) == 2  # Missing Core Requirements and Success Criteria
        error_messages = [
            (
                str(cast(dict[str, object], e).get("message", ""))
                if isinstance(e, dict)
                else str(e)
            )
            for e in errors
        ]
        assert any("Core Requirements" in msg for msg in error_messages)
        assert any("Success Criteria" in msg for msg in error_messages)

    @pytest.mark.asyncio
    async def test_validate_heading_level_skip(self):
        """Test validation detects heading level skips."""
        validator = SchemaValidator()

        content = """
## Project Overview
Content

#### Subsection (skipped level 3)
More content
"""

        result_raw = await validator.validate_file("projectBrief.md", content)
        result = cast(dict[str, object], result_raw)

        # Should have warning/error about heading level skip
        errors_raw = result.get("errors", [])
        warnings_raw = result.get("warnings", [])
        errors = cast(list[object], errors_raw) if isinstance(errors_raw, list) else []
        warnings = (
            cast(list[object], warnings_raw) if isinstance(warnings_raw, list) else []
        )
        all_issues: list[object] = errors + warnings
        # Check if any error mentions heading or level
        has_heading_issue = any(
            "heading" in str(issue).lower() or "level" in str(issue).lower()
            for issue in all_issues
        )
        assert has_heading_issue or len(errors) > 0  # At least should fail validation

    @pytest.mark.asyncio
    async def test_no_schema_for_file(self):
        """Test validation handles files without schemas."""
        validator = SchemaValidator()

        content = "# Some content"

        result_raw = await validator.validate_file("unknown.md", content)
        result = cast(dict[str, object], result_raw)

        assert result.get("valid") is True
        warnings_raw = result.get("warnings", [])
        warnings = (
            cast(list[object], warnings_raw) if isinstance(warnings_raw, list) else []
        )
        assert len(warnings) == 1
        warning = warnings[0]
        warning_type = (
            str(cast(dict[str, object], warning).get("type", ""))
            if isinstance(warning, dict)
            else str(warning)
        )
        assert "no_schema" in warning_type.lower()

    def test_get_schema(self):
        """Test getting schema definition."""
        validator = SchemaValidator()

        schema = validator.get_schema("projectBrief.md")

        assert schema is not None
        assert isinstance(schema, dict)
        assert "required_sections" in schema
        required_sections_raw = schema.get("required_sections")
        assert isinstance(required_sections_raw, (list, dict, str))
        if isinstance(required_sections_raw, list):
            required_sections_list = cast(list[str], required_sections_raw)
            assert "Project Overview" in required_sections_list
        elif isinstance(required_sections_raw, dict):
            required_sections_dict = cast(dict[str, object], required_sections_raw)
            assert "Project Overview" in required_sections_dict
        else:
            # Must be str at this point
            assert "Project Overview" in required_sections_raw


# ============================================================================
# Duplication Detector Tests
# ============================================================================


class TestDuplicationDetector:
    """Tests for DuplicationDetector."""

    @pytest.mark.asyncio
    async def test_find_exact_duplicates(self):
        """Test finding exact duplicate content."""
        detector = DuplicationDetector(similarity_threshold=0.85, min_content_length=20)

        files_content = {
            "file1.md": """
## Section A
This is some content that will be duplicated exactly.
It has multiple lines to meet the minimum length requirement.

## Section B
Different content here.
""",
            "file2.md": """
## Section X
This is some content that will be duplicated exactly.
It has multiple lines to meet the minimum length requirement.

## Section Y
Other content.
""",
        }

        result = await detector.scan_all_files(files_content)

        assert isinstance(result, dict)
        duplicates_found = result.get("duplicates_found", 0)
        assert isinstance(duplicates_found, (int, float))
        assert duplicates_found > 0
        exact_duplicates_raw = result.get("exact_duplicates", [])
        assert isinstance(exact_duplicates_raw, list)
        exact_duplicates = cast(list[dict[str, object]], exact_duplicates_raw)
        assert len(exact_duplicates) > 0

        # Check that the duplicate was found
        dup = exact_duplicates[0]
        assert cast(float, dup.get("similarity")) == 1.0
        assert cast(str, dup.get("type")) == "exact"

    @pytest.mark.asyncio
    async def test_find_similar_content(self):
        """Test finding similar (not exact) content."""
        detector = DuplicationDetector(similarity_threshold=0.70, min_content_length=20)

        files_content = {
            "file1.md": """
## Goals
The primary goal is to build a robust and reliable system.
It should be scalable, maintainable, and easy to use.
This will require careful planning and implementation.
""",
            "file2.md": """
## Objectives
The primary goal is to build a robust and reliable system.
It should be scalable, maintainable, and simple to use.
This will need careful planning and execution.
""",
        }

        result = await detector.scan_all_files(files_content)

        # Should find similar content (not exact) OR exact duplicates
        # Since the content is very similar, it might be detected
        similar_content_raw = result.get("similar_content", [])
        exact_duplicates_raw = result.get("exact_duplicates", [])
        similar_content = (
            cast(list[object], similar_content_raw)
            if isinstance(similar_content_raw, list)
            else []
        )
        exact_duplicates = (
            cast(list[object], exact_duplicates_raw)
            if isinstance(exact_duplicates_raw, list)
            else []
        )
        total_found = len(similar_content) + len(exact_duplicates)
        assert total_found > 0, f"Expected to find similar content, but found {result}"

    @pytest.mark.asyncio
    async def test_no_duplicates(self):
        """Test with completely different content."""
        detector = DuplicationDetector(similarity_threshold=0.85, min_content_length=20)

        files_content = {
            "file1.md": """
## Technical Stack
We use Python and FastMCP for the backend.
""",
            "file2.md": """
## User Interface
The frontend is built with React and TypeScript.
""",
        }

        result = await detector.scan_all_files(files_content)

        assert result["duplicates_found"] == 0
        exact_duplicates_raw = result.get("exact_duplicates", [])
        similar_content_raw = result.get("similar_content", [])
        exact_duplicates = (
            cast(list[object], exact_duplicates_raw)
            if isinstance(exact_duplicates_raw, list)
            else []
        )
        similar_content = (
            cast(list[object], similar_content_raw)
            if isinstance(similar_content_raw, list)
            else []
        )
        assert len(exact_duplicates) == 0
        assert len(similar_content) == 0

    def test_compare_sections(self):
        """Test section comparison."""
        detector = DuplicationDetector(min_content_length=10)

        content1 = "This is a test section with some content."
        content2 = "This is a test section with some content."

        similarity = detector.compare_sections(content1, content2)

        assert similarity == 1.0

    def test_compare_similar_sections(self):
        """Test comparison of similar sections."""
        detector = DuplicationDetector(min_content_length=10)

        content1 = "This is a test section with some content."
        content2 = "This is a test section with different content."

        similarity = detector.compare_sections(content1, content2)

        assert 0.5 < similarity < 1.0


# ============================================================================
# Quality Metrics Tests
# ============================================================================


class TestQualityMetrics:
    """Tests for QualityMetrics."""

    @pytest.mark.asyncio
    async def test_calculate_overall_score_high_quality(self):
        """Test quality score calculation for high-quality content."""
        validator = SchemaValidator()
        metrics = QualityMetrics(validator)

        files_content = {
            "projectBrief.md": """
## Project Overview
Overview content.

## Goals
Goals content.

## Core Requirements
Requirements content.

## Success Criteria
Criteria content.
"""
        }

        files_metadata: dict[str, dict[str, object]] = {
            "projectBrief.md": {
                "token_count": 5000,
                "last_modified": "2025-12-19T10:00:00",
            }
        }

        duplication_data: dict[str, object] = {
            "duplicates_found": 0,
            "exact_duplicates": [],
            "similar_content": [],
        }

        result = await metrics.calculate_overall_score(
            files_content, files_metadata, duplication_data
        )

        overall_score_raw = result.get("overall_score", 0)
        overall_score = (
            overall_score_raw if isinstance(overall_score_raw, (int, float)) else 0
        )
        assert overall_score >= 80
        assert result.get("grade") in ["A", "B"]
        assert result.get("status") in ["healthy", "warning"]

    @pytest.mark.asyncio
    async def test_calculate_overall_score_with_issues(self):
        """Test quality score with various issues."""
        validator = SchemaValidator()
        metrics = QualityMetrics(validator)

        files_content = {
            "projectBrief.md": """
## Project Overview
Just an overview.
"""  # Missing required sections
        }

        files_metadata: dict[str, dict[str, object]] = {
            "projectBrief.md": {
                "token_count": 100,
                "last_modified": "2024-01-01T10:00:00",  # Old
            }
        }

        duplication_data: dict[str, object] = {
            "duplicates_found": 3,
            "exact_duplicates": [{"file1": "a", "file2": "b"}],
            "similar_content": [],
        }

        result = await metrics.calculate_overall_score(
            files_content, files_metadata, duplication_data
        )

        overall_score_raw = result.get("overall_score", 0)
        overall_score = (
            overall_score_raw if isinstance(overall_score_raw, (int, float)) else 0
        )
        assert overall_score < 80
        issues_raw = result.get("issues", [])
        recommendations_raw = result.get("recommendations", [])
        issues = cast(list[object], issues_raw) if isinstance(issues_raw, list) else []
        recommendations = (
            cast(list[object], recommendations_raw)
            if isinstance(recommendations_raw, list)
            else []
        )
        assert len(issues) > 0
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_calculate_file_score(self):
        """Test individual file score calculation."""
        validator = SchemaValidator()
        metrics = QualityMetrics(validator)

        content = """
## Project Overview
Content here.

## Goals
Goals here.

## Core Requirements
Requirements here.

## Success Criteria
Criteria here.
"""

        metadata: dict[str, object] = {
            "token_count": 3000,
            "last_modified": "2025-12-19T10:00:00",
        }

        result = await metrics.calculate_file_score(
            "projectBrief.md", content, metadata
        )

        score_raw = result.get("score", 0)
        score = score_raw if isinstance(score_raw, (int, float)) else 0
        assert score >= 70
        assert result.get("grade") in ["A", "B", "C", "D", "F"]
        assert "validation" in result


# ============================================================================
# Validation Config Tests
# ============================================================================


class TestValidationConfig:
    """Tests for ValidationConfig."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            assert config.is_validation_enabled() is True
            assert config.get_token_budget_max() == 100000
            assert config.get_duplication_threshold() == 0.85

    def test_get_with_dot_notation(self):
        """Test getting config values with dot notation."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            value = config.get("token_budget.max_total_tokens")
            assert value == 100000

            value = config.get("duplication.threshold")
            assert value == 0.85

    def test_set_with_dot_notation(self):
        """Test setting config values with dot notation."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            config.set("token_budget.max_total_tokens", 150000)
            assert config.get("token_budget.max_total_tokens") == 150000

            config.set("duplication.threshold", 0.90)
            assert config.get("duplication.threshold") == 0.90

    @pytest.mark.asyncio
    async def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create and modify config
            config1 = ValidationConfig(tmpdir_path)
            config1.set("token_budget.max_total_tokens", 200000)
            await config1.save()

            # Load config in new instance
            config2 = ValidationConfig(tmpdir_path)
            assert config2.get("token_budget.max_total_tokens") == 200000

    def test_validate_config_valid(self):
        """Test config validation with valid config."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            errors = config.validate_config()
            assert len(errors) == 0

    def test_validate_config_invalid(self):
        """Test config validation with invalid values."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            # Set invalid values
            config.set("duplication.threshold", 1.5)  # Should be 0-1
            config.set("token_budget.max_total_tokens", -100)  # Should be positive

            errors = config.validate_config()
            assert len(errors) > 0

    def test_reset_to_defaults(self):
        """Test resetting config to defaults."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ValidationConfig(Path(tmpdir))

            # Modify config
            config.set("token_budget.max_total_tokens", 200000)
            assert config.get("token_budget.max_total_tokens") == 200000

            # Reset
            config.reset_to_defaults()
            assert config.get("token_budget.max_total_tokens") == 100000


# ============================================================================
# Integration Tests
# ============================================================================


class TestPhase3Integration:
    """Integration tests for Phase 3 components."""

    @pytest.mark.asyncio
    async def test_full_validation_workflow(self):
        """Test complete validation workflow."""
        validator = SchemaValidator()
        detector = DuplicationDetector()
        metrics = QualityMetrics(validator)

        # Sample content
        files_content = {
            "projectBrief.md": """
## Project Overview
This is a test project.

## Goals
Build a great system.

## Core Requirements
Must be fast and reliable.

## Success Criteria
All tests pass.
""",
            "activeContext.md": """
## Current Focus
Working on Phase 3.

## Recent Changes
Added validation features.

## Next Steps
Test everything.
""",
        }

        files_metadata: dict[str, dict[str, object]] = {
            "projectBrief.md": {
                "token_count": 3000,
                "last_modified": "2025-12-19T10:00:00",
            },
            "activeContext.md": {
                "token_count": 2000,
                "last_modified": "2025-12-19T09:00:00",
            },
        }

        # Validate all files
        validation_results: dict[str, dict[str, object]] = {}
        for fname, content in files_content.items():
            result_raw = await validator.validate_file(fname, content)
            result = cast(dict[str, object], result_raw)
            validation_results[fname] = result

        # Check duplications
        duplication_data = await detector.scan_all_files(files_content)

        # Calculate quality score
        quality_data = await metrics.calculate_overall_score(
            files_content, files_metadata, duplication_data
        )

        # Assertions
        assert all(
            cast(bool, r.get("valid", False)) for r in validation_results.values()
        )
        overall_score_raw = quality_data.get("overall_score", 0)
        overall_score = (
            overall_score_raw if isinstance(overall_score_raw, (int, float)) else 0
        )
        assert overall_score >= 70
        assert quality_data.get("grade") in ["A", "B", "C", "D", "F"]


if __name__ == "__main__":
    _ = pytest.main([__file__, "-v"])
