"""Unit tests for preflight helpers and ensure_dict used by phase A."""

from __future__ import annotations

from typing import cast

from cortex.core.models import JsonDict, ModelDict
from cortex.tools.execution.pre_commit_phase_dispatch import (
    ensure_dict as _ensure_dict,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    append_markdown_summary as _append_markdown_summary,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    build_check_summaries as _build_check_summaries,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    build_execute_check_summaries as _build_execute_check_summaries,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    build_preflight_model as _build_preflight_model,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    compute_preflight_passed as _compute_preflight_passed,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    has_pre_commit_tool_error as _has_pre_commit_tool_error,
)
from cortex.tools.execution.pre_commit_preflight_helpers import (
    markdown_has_tool_error as _markdown_has_tool_error,
)
from cortex.tools.models import PreflightCheckSummary


class TestPreflightHelperFunctions:
    """Unit tests for pure helper functions in pre_commit_preflight_helpers."""

    def test_has_pre_commit_tool_error_true(self) -> None:
        """Detects tool error when status=error and error field present."""
        result: ModelDict = {
            "status": "error",
            "error": "boom",
            "error_type": "RuntimeError",
        }
        assert _has_pre_commit_tool_error(result) is True

    def test_has_pre_commit_tool_error_false_on_success(self) -> None:
        """No tool error when status=success."""
        result: ModelDict = {"status": "success"}
        assert _has_pre_commit_tool_error(result) is False

    def test_has_pre_commit_tool_error_false_without_error_fields(self) -> None:
        """No tool error when status=error but no error/error_type."""
        result: ModelDict = {"status": "error"}
        assert _has_pre_commit_tool_error(result) is False

    def test_markdown_has_tool_error_true(self) -> None:
        """Detects error status in markdown result."""
        md_err = cast(JsonDict, {"status": "error"})
        assert _markdown_has_tool_error(md_err) is True

    def test_markdown_has_tool_error_false(self) -> None:
        """No error when status=success."""
        md_ok = cast(JsonDict, {"status": "success"})
        assert _markdown_has_tool_error(md_ok) is False

    def test_compute_preflight_passed_success_no_markdown(self) -> None:
        """Passes when execute succeeds and markdown was not run."""
        result: ModelDict = {"status": "success"}
        assert _compute_preflight_passed(result, None) is True

    def test_compute_preflight_passed_exec_fails(self) -> None:
        """Fails when execute reports non-success status."""
        result: ModelDict = {"status": "error"}
        assert _compute_preflight_passed(result, None) is False

    def test_compute_preflight_passed_markdown_has_errors(self) -> None:
        """Fails when markdown lint has files_with_errors > 0."""
        exec_ok: ModelDict = {"status": "success"}
        md_bad = cast(
            JsonDict,
            {
                "status": "success",
                "files_with_errors": 2,
                "error_message": None,
            },
        )
        assert _compute_preflight_passed(exec_ok, md_bad) is False

    def test_compute_preflight_passed_markdown_has_error_message(self) -> None:
        """Fails when markdown lint has an error_message."""
        exec_ok: ModelDict = {"status": "success"}
        md_err = cast(
            JsonDict,
            {
                "status": "success",
                "files_with_errors": 0,
                "error_message": "CLI not found",
            },
        )
        assert _compute_preflight_passed(exec_ok, md_err) is False

    def test_compute_preflight_passed_files_with_errors_as_string_zero(self) -> None:
        """Passes when files_with_errors is str '0' (boundary)."""
        exec_ok: ModelDict = {"status": "success"}
        md_ok = cast(
            JsonDict,
            {
                "status": "success",
                "files_with_errors": "0",
                "error_message": None,
            },
        )
        assert _compute_preflight_passed(exec_ok, md_ok) is True

    def test_compute_preflight_passed_files_with_errors_as_string_positive(
        self,
    ) -> None:
        """Fails when files_with_errors is str '3'."""
        exec_ok: ModelDict = {"status": "success"}
        md_bad = cast(
            JsonDict,
            {
                "status": "success",
                "files_with_errors": "3",
                "error_message": None,
            },
        )
        assert _compute_preflight_passed(exec_ok, md_bad) is False

    def test_compute_preflight_passed_markdown_status_error_fails(self) -> None:
        """Fails when markdown status is 'error' even if files_with_errors is 0."""
        exec_ok: ModelDict = {"status": "success"}
        md_err = cast(
            JsonDict,
            {
                "status": "error",
                "files_with_errors": 0,
                "error_message": None,
            },
        )
        assert _compute_preflight_passed(exec_ok, md_err) is False

    def test_build_execute_check_summaries_empty_results(self) -> None:
        """Returns empty list when results dict is empty."""
        result: ModelDict = {"results": {}}
        assert _build_execute_check_summaries(result) == []

    def test_build_execute_check_summaries_non_dict_results(self) -> None:
        """Returns empty list when results is not a dict."""
        result: ModelDict = {"results": "not a dict"}
        assert _build_execute_check_summaries(result) == []

    def test_build_execute_check_summaries_skips_non_dict_entries(self) -> None:
        """Skips entries that are not dicts."""
        result: ModelDict = {"results": {"bad": "string value"}}
        assert _build_execute_check_summaries(result) == []

    def test_append_markdown_summary_none(self) -> None:
        """Does nothing when markdown_result is None."""
        summaries: list[PreflightCheckSummary] = []
        _append_markdown_summary(summaries, None)
        assert len(summaries) == 0

    def test_append_markdown_summary_with_errors(self) -> None:
        """Appends error summary when files_with_errors > 0."""
        summaries: list[PreflightCheckSummary] = []
        md = cast(JsonDict, {"files_with_errors": 5, "error_message": None})
        _append_markdown_summary(summaries, md)
        assert len(summaries) == 1
        assert summaries[0].status == "error"
        assert summaries[0].errors == 5

    def test_build_check_summaries_combines_both(self) -> None:
        """Combines execute and markdown summaries."""
        exec_result: ModelDict = {
            "results": {
                "quality": {
                    "success": True,
                    "errors": [],
                    "warnings": [],
                    "output": "ok",
                },
            },
        }
        md = cast(JsonDict, {"files_with_errors": 0, "error_message": None})
        summaries = _build_check_summaries(exec_result, md)
        names = {s.name for s in summaries}
        assert names == {"quality", "markdown_lint"}

    def test_build_preflight_model_success(self) -> None:
        """Builds success model with correct shape."""
        exec_result: ModelDict = {
            "status": "success",
            "results": {},
        }
        model = _build_preflight_model(exec_result, "python", None, None)
        assert model["status"] == "success"
        assert model["preflight_passed"] is True
        assert model["language"] == "python"

    def test_build_preflight_model_error(self) -> None:
        """Builds error model when tool error detected."""
        exec_result: ModelDict = {
            "status": "error",
            "error": "crash",
            "error_type": "RuntimeError",
            "results": {},
        }
        model = _build_preflight_model(exec_result, "python", None, None)
        assert model["status"] == "error"
        assert model["error_type"] == "PreflightToolError"


class TestEnsureDict:
    """Unit tests for _ensure_dict (handles MCP cancellation/string responses)."""

    def test_ensure_dict_passes_through_dict(self) -> None:
        """Dict input is returned unchanged."""
        d: ModelDict = {"status": "success", "preflight_passed": True}
        assert _ensure_dict(d) is d

    def test_ensure_dict_parses_json_string(self) -> None:
        """JSON string (e.g. CANCELLED_RESPONSE_JSON) is parsed to dict."""
        s = '{"status":"error","error":"CancelledError","message":"Tool call was cancelled"}'
        result = _ensure_dict(s)
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result.get("error") == "CancelledError"

    def test_ensure_dict_invalid_json_returns_error_dict(self) -> None:
        """Invalid JSON string returns error dict."""
        result = _ensure_dict("not valid json")
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "error" in result

    def test_ensure_dict_parsed_non_dict_returns_empty_dict(self) -> None:
        """JSON that parses to non-dict (e.g. array) returns empty dict."""
        result = _ensure_dict("[]")
        assert isinstance(result, dict)
        assert result == {}

    def test_ensure_dict_empty_string_returns_error_dict(self) -> None:
        """Empty string causes JSONDecodeError and returns error dict."""
        result = _ensure_dict("")
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "error" in result
