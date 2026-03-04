"""Tests for result_links_models (validate_links and get_link_graph result types)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.tools.models_base import ToolResultStatus
from cortex.tools.validation.result_links_models import (
    GetLinkGraphErrorResult,
    GetLinkGraphJsonResult,
    GetLinkGraphMermaidResult,
    LinkGraphEdge,
    LinkGraphNode,
    LinkGraphSummary,
    LinkValidationError,
    LinkValidationWarning,
    ValidateLinksAllFilesResult,
    ValidateLinksErrorResult,
    ValidateLinksSingleFileResult,
)
from cortex.tools.validation.result_models import (
    LinkGraphFormat,
    ValidateLinksMode,
)


class TestLinkValidationError:
    """Tests for LinkValidationError model."""

    def test_minimal_valid(self) -> None:
        """Minimal required fields create valid model."""
        data = {
            "file": "foo.md",
            "line": 1,
            "link_type": "ref",
            "target": "bar.md",
            "error": "not found",
            "suggestion": "fix path",
        }
        obj = LinkValidationError.model_validate(data)
        assert obj.file == "foo.md"
        assert obj.line == 1
        assert obj.section is None

    def test_with_optional_section(self) -> None:
        """Optional section is accepted."""
        data = {
            "file": "a.md",
            "line": 2,
            "link_type": "transclusion",
            "target": "b.md",
            "error": "missing",
            "suggestion": "add file",
            "section": "## Intro",
        }
        obj = LinkValidationError.model_validate(data)
        assert obj.section == "## Intro"

    def test_extra_fields_forbidden(self) -> None:
        """StrictBaseModel forbids extra fields."""
        data = {
            "file": "x.md",
            "line": 1,
            "link_type": "ref",
            "target": "y.md",
            "error": "e",
            "suggestion": "s",
            "unknown": "bad",
        }
        with pytest.raises(ValidationError):
            _ = LinkValidationError.model_validate(data)


class TestLinkValidationWarning:
    """Tests for LinkValidationWarning model."""

    def test_minimal_valid(self) -> None:
        """Minimal required fields."""
        data = {
            "file": "f.md",
            "line": 3,
            "link_type": "ref",
            "target": "t.md",
            "warning": "w",
            "suggestion": "s",
        }
        obj = LinkValidationWarning.model_validate(data)
        assert obj.file == "f.md"
        assert obj.available_sections is None

    def test_with_available_sections(self) -> None:
        """Optional available_sections is accepted."""
        data = {
            "file": "f.md",
            "line": 1,
            "link_type": "ref",
            "target": "t.md",
            "warning": "w",
            "suggestion": "s",
            "available_sections": ["## A", "## B"],
        }
        obj = LinkValidationWarning.model_validate(data)
        assert obj.available_sections == ["## A", "## B"]


class TestValidateLinksSingleFileResult:
    """Tests for ValidateLinksSingleFileResult."""

    def test_success_with_string_status_and_mode(self) -> None:
        """Status and mode accept string (coerced to enum)."""
        data: dict[str, object] = {
            "status": "success",
            "mode": "single_file",
            "file": "x.md",
            "total_links": 2,
            "valid_links": 1,
            "broken_links": 1,
            "warnings": 0,
            "validation_errors": [],
            "validation_warnings": [],
        }
        obj = ValidateLinksSingleFileResult.model_validate(data)
        assert obj.status == ToolResultStatus.SUCCESS
        assert obj.mode == ValidateLinksMode.SINGLE_FILE
        assert obj.files_checked == 1

    def test_with_errors_and_warnings(self) -> None:
        """Validation errors and warnings lists are accepted."""
        err = {
            "file": "a.md",
            "line": 1,
            "link_type": "ref",
            "target": "b.md",
            "error": "e",
            "suggestion": "s",
        }
        data = {
            "status": "success",
            "mode": "single_file",
            "file": "a.md",
            "total_links": 1,
            "valid_links": 0,
            "broken_links": 1,
            "warnings": 0,
            "validation_errors": [err],
            "validation_warnings": [],
        }
        obj = ValidateLinksSingleFileResult.model_validate(data)
        assert len(obj.validation_errors) == 1
        assert obj.validation_errors[0].target == "b.md"


class TestValidateLinksAllFilesResult:
    """Tests for ValidateLinksAllFilesResult."""

    def test_success_with_report(self) -> None:
        """All-files result with report string."""
        data: dict[str, object] = {
            "status": "success",
            "mode": "all_files",
            "files_checked": 5,
            "total_links": 10,
            "valid_links": 8,
            "broken_links": 2,
            "warnings": 0,
            "validation_errors": [],
            "validation_warnings": [],
            "report": "Summary report text",
        }
        obj = ValidateLinksAllFilesResult.model_validate(data)
        assert obj.mode == ValidateLinksMode.ALL_FILES
        assert obj.report == "Summary report text"


class TestValidateLinksErrorResult:
    """Tests for ValidateLinksErrorResult."""

    def test_error_result(self) -> None:
        """Error result with optional mode and files_checked."""
        data = {
            "status": ToolResultStatus.ERROR,
            "error": "Something failed",
            "mode": "single_file",
            "files_checked": 0,
        }
        obj = ValidateLinksErrorResult.model_validate(data)
        assert obj.status == ToolResultStatus.ERROR
        assert obj.error == "Something failed"


class TestLinkGraphNode:
    """Tests for LinkGraphNode."""

    def test_minimal(self) -> None:
        """Required id, type default, exists."""
        data = {"id": "foo.md", "exists": True}
        obj = LinkGraphNode.model_validate(data)
        assert obj.type == "file"
        assert obj.exists is True

    def test_explicit_type(self) -> None:
        """Custom type accepted."""
        data = {"id": "x", "type": "section", "exists": False}
        obj = LinkGraphNode.model_validate(data)
        assert obj.type == "section"


class TestLinkGraphEdge:
    """Tests for LinkGraphEdge."""

    def test_valid(self) -> None:
        """All required fields."""
        data = {"source": "a.md", "target": "b.md", "type": "ref", "line": 10}
        obj = LinkGraphEdge.model_validate(data)
        assert obj.source == "a.md"
        assert obj.line == 10


class TestLinkGraphSummary:
    """Tests for LinkGraphSummary."""

    def test_valid(self) -> None:
        """All required summary fields."""
        data = {
            "total_files": 3,
            "total_links": 5,
            "reference_links": 4,
            "transclusion_links": 1,
            "has_cycles": False,
            "cycle_count": 0,
        }
        obj = LinkGraphSummary.model_validate(data)
        assert obj.has_cycles is False
        assert obj.cycle_count == 0


class TestGetLinkGraphJsonResult:
    """Tests for GetLinkGraphJsonResult."""

    def test_success_with_string_format(self) -> None:
        """Format and status accept string (coerced to enum)."""
        data: dict[str, object] = {
            "status": "success",
            "format": "json",
            "nodes": [{"id": "a.md", "exists": True}],
            "edges": [],
            "cycles": [],
            "summary": {
                "total_files": 1,
                "total_links": 0,
                "reference_links": 0,
                "transclusion_links": 0,
                "has_cycles": False,
                "cycle_count": 0,
            },
        }
        obj = GetLinkGraphJsonResult.model_validate(data)
        assert obj.format == LinkGraphFormat.JSON
        assert len(obj.nodes) == 1


class TestGetLinkGraphMermaidResult:
    """Tests for GetLinkGraphMermaidResult."""

    def test_success(self) -> None:
        """Mermaid result with diagram string."""
        data: dict[str, object] = {
            "status": "success",
            "format": "mermaid",
            "diagram": "graph TD; A-->B",
            "cycles": [],
        }
        obj = GetLinkGraphMermaidResult.model_validate(data)
        assert obj.format == LinkGraphFormat.MERMAID
        assert "graph" in obj.diagram


class TestGetLinkGraphErrorResult:
    """Tests for GetLinkGraphErrorResult."""

    def test_error_with_format(self) -> None:
        """Error result with optional format."""
        data = {
            "status": ToolResultStatus.ERROR,
            "error": "Failed",
            "format": "json",
        }
        obj = GetLinkGraphErrorResult.model_validate(data)
        assert obj.format == "json"


class TestInvalidEnumCoercion:
    """Edge case: invalid enum values raise ValidationError."""

    def test_invalid_validate_links_mode_raises(self) -> None:
        """Invalid mode string raises."""
        data: dict[str, object] = {
            "status": "success",
            "mode": "invalid_mode",
            "file": "x.md",
            "total_links": 0,
            "valid_links": 0,
            "broken_links": 0,
            "warnings": 0,
            "validation_errors": [],
            "validation_warnings": [],
        }
        with pytest.raises(ValidationError):
            _ = ValidateLinksSingleFileResult.model_validate(data)

    def test_invalid_link_graph_format_raises(self) -> None:
        """Invalid format string raises."""
        data: dict[str, object] = {
            "status": "success",
            "format": "xml",
            "nodes": [],
            "edges": [],
            "cycles": [],
            "summary": {
                "total_files": 0,
                "total_links": 0,
                "reference_links": 0,
                "transclusion_links": 0,
                "has_cycles": False,
                "cycle_count": 0,
            },
        }
        with pytest.raises(ValidationError):
            _ = GetLinkGraphJsonResult.model_validate(data)
