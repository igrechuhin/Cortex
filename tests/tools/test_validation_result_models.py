"""Tests for validation result models (enum coercion and result types)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.tools.validation_result_models import (
    LinkGraphFormat,
    ValidateCheckType,
    ValidateDuplicationsResult,
    ValidateLinksMode,
    ValidateSchemaSingleResult,
)


class TestValidationResultModelsEnumCoercion:
    """Test that result models accept string enum values (coercion)."""

    def test_validate_schema_single_result_accepts_string_check_type(self) -> None:
        """model_validate with string 'schema' coerces to ValidateCheckType.SCHEMA."""
        data: dict[str, object] = {
            "status": "success",
            "check_type": "schema",
            "file_name": "projectBrief.md",
            "validation": {"valid": True, "errors": [], "warnings": []},
        }
        result = ValidateSchemaSingleResult.model_validate(data)
        assert result.check_type == ValidateCheckType.SCHEMA
        assert result.file_name == "projectBrief.md"

    def test_validate_duplications_result_accepts_string_check_type(self) -> None:
        """model_validate with string 'duplications' coerces to enum."""
        data: dict[str, object] = {
            "status": "success",
            "check_type": "duplications",
            "threshold": 0.8,
            "duplicates_found": 0,
            "exact_duplicates": [],
            "similar_content": [],
            "suggested_fixes": [],
        }
        result = ValidateDuplicationsResult.model_validate(data)
        assert result.check_type == ValidateCheckType.DUPLICATIONS

    def test_validate_links_mode_string_coercion(self) -> None:
        """ValidateLinksMode accepts string in model context."""
        assert ValidateLinksMode("single_file") == ValidateLinksMode.SINGLE_FILE
        assert ValidateLinksMode("all_files") == ValidateLinksMode.ALL_FILES

    def test_link_graph_format_string_coercion(self) -> None:
        """LinkGraphFormat accepts string in model context."""
        assert LinkGraphFormat("json") == LinkGraphFormat.JSON
        assert LinkGraphFormat("mermaid") == LinkGraphFormat.MERMAID

    def test_invalid_check_type_raises(self) -> None:
        """Invalid check_type string raises ValidationError."""
        data: dict[str, object] = {
            "status": "success",
            "check_type": "invalid_check",
            "file_name": "x.md",
            "validation": {"valid": True, "errors": [], "warnings": []},
        }
        with pytest.raises(ValidationError):
            _ = ValidateSchemaSingleResult.model_validate(data)
