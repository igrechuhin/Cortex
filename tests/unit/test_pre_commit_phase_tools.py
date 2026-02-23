"""Tests for phase-level pre-commit helper tools.

Covers Phase A (run_preflight_checks) and Phase B (run_docs_and_memory_bank_sync)
MCP tools and their underlying helper implementations with success, failure,
tool-error, and edge-case scenarios.
"""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import JsonDict, ModelDict
from cortex.tools.models import PreflightCheckSummary
from cortex.tools.pre_commit_docs_memory_helpers import (
    _build_docs_memory_bank_model,  # pyright: ignore[reportPrivateUsage]
    _build_docs_memory_bank_summaries,  # pyright: ignore[reportPrivateUsage]
    _build_roadmap_sync_summary,  # pyright: ignore[reportPrivateUsage]
    _build_timestamps_summary,  # pyright: ignore[reportPrivateUsage]
    _compute_docs_memory_bank_passed,  # pyright: ignore[reportPrivateUsage]
)
from cortex.tools.pre_commit_phase_tools import (
    run_docs_and_memory_bank_sync,
    run_preflight_checks,
)
from cortex.tools.pre_commit_preflight_helpers import (
    _append_markdown_summary,  # pyright: ignore[reportPrivateUsage]
    _build_check_summaries,  # pyright: ignore[reportPrivateUsage]
    _build_execute_check_summaries,  # pyright: ignore[reportPrivateUsage]
    _build_preflight_model,  # pyright: ignore[reportPrivateUsage]
    _compute_preflight_passed,  # pyright: ignore[reportPrivateUsage]
    _has_pre_commit_tool_error,  # pyright: ignore[reportPrivateUsage]
    _markdown_has_tool_error,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_pre_commit_result(
    status: str,
    language: str = "python",
    tests_success: bool = True,
    error_payload: bool = False,
) -> ModelDict:
    """Helper to build minimal execute_pre_commit_checks-like result."""
    base: ModelDict = {
        "status": status,
        "language": language,
        "results": {
            "tests": {
                "check_type": "tests",
                "success": tests_success,
                "output": "ok" if tests_success else "tests failed",
                "errors": [] if tests_success else ["failure"],
                "warnings": [],
            },
        },
        "total_errors": 0 if tests_success and status == "success" else 1,
        "total_warnings": 0,
        "files_modified": [],
    }
    if error_payload:
        base["error"] = "tool error"
        base["error_type"] = "RuntimeError"
    return base


def _make_markdown_result(
    files_with_errors: int = 0,
    error_message: str | None = None,
    *,
    tool_error: bool = False,
) -> str:
    """Helper to build minimal fix_markdown_lint JSON string.

    ``tool_error=True`` sets status to ``"error"`` to simulate CLI-level
    failures.  Otherwise status is always ``"success"`` (even when
    ``files_with_errors > 0``), matching ``fix_markdown_lint`` behaviour
    where lint findings do not trigger a tool error.
    """
    status = "error" if tool_error else "success"
    return json.dumps(
        {
            "status": status,
            "files_processed": 1,
            "files_fixed": 0,
            "files_unchanged": 1,
            "files_with_errors": files_with_errors,
            "results": [],
            "error_message": error_message,
        }
    )


# ============================================================================
# Phase A – run_preflight_checks (MCP tool integration tests)
# ============================================================================


class TestRunPreflightChecks:
    """Tests for run_preflight_checks MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Preflight passes when checks and markdown lint have no errors."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="success",
                tests_success=True,
            )
            mock_md.return_value = _make_markdown_result(files_with_errors=0)

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        assert result["language"] == "python"
        check_names = {e["name"] for e in result["checks"]}
        assert "tests" in check_names
        assert "markdown_lint" in check_names

    @pytest.mark.asyncio
    async def test_sets_flag_when_checks_fail(self) -> None:
        """preflight_passed is False when checks report errors."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="error",
                tests_success=False,
            )
            mock_md.return_value = _make_markdown_result(files_with_errors=0)

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is False
        tests_entry = next(e for e in result["checks"] if e["name"] == "tests")
        assert tests_entry["status"] == "error"

    @pytest.mark.asyncio
    async def test_reports_tool_error(self) -> None:
        """Tool-level error is surfaced with status=error."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="error",
                tests_success=False,
                error_payload=True,
            )
            mock_md.return_value = _make_markdown_result(files_with_errors=0)

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "error"
        assert result["error_type"] == "PreflightToolError"
        assert "underlying tool error" in result["error"]

    @pytest.mark.asyncio
    async def test_markdown_lint_errors_fail_preflight(self) -> None:
        """Preflight fails when markdown lint finds files with errors."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="success",
                tests_success=True,
            )
            mock_md.return_value = _make_markdown_result(files_with_errors=3)

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is False
        md_entry = next(e for e in result["checks"] if e["name"] == "markdown_lint")
        assert md_entry["status"] == "error"
        assert md_entry["errors"] == 3

    @pytest.mark.asyncio
    async def test_markdown_tool_error_surfaces(self) -> None:
        """Markdown tool-level error makes status=error."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="success",
                tests_success=True,
            )
            # tool_error=True sets status="error" → _markdown_has_tool_error
            mock_md.return_value = _make_markdown_result(
                error_message="CLI not found",
                tool_error=True,
            )

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "error"
        assert result["error_type"] == "PreflightToolError"

    @pytest.mark.asyncio
    async def test_invalid_markdown_json_gracefully_handled(self) -> None:
        """Invalid JSON from markdown lint is treated as None result."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="success",
                tests_success=True,
            )
            mock_md.return_value = "NOT-JSON"

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        # With None markdown result (decode failed), success is based solely
        # on execute_pre_commit_checks
        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        # No markdown_lint entry since decode returned None
        check_names = {e["name"] for e in result["checks"]}
        assert "markdown_lint" not in check_names

    @pytest.mark.asyncio
    async def test_markdown_result_not_dict_gracefully_handled(self) -> None:
        """Valid JSON that is not a dict (e.g. array) is treated as None result."""
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
            ) as mock_exec,
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
            ) as mock_md,
        ):
            mock_exec.return_value = _make_pre_commit_result(
                status="success",
                tests_success=True,
            )
            mock_md.return_value = "[1, 2]"

            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        check_names = {e["name"] for e in result["checks"]}
        assert "markdown_lint" not in check_names

    @pytest.mark.asyncio
    async def test_multiple_check_results_in_summaries(self) -> None:
        """Multiple checks from execute_pre_commit_checks appear in summaries."""
        exec_result: ModelDict = {
            "status": "success",
            "language": "python",
            "results": {
                "format": {
                    "success": True,
                    "errors": [],
                    "warnings": ["trailing ws"],
                    "output": "formatted",
                },
                "quality": {
                    "success": True,
                    "errors": [],
                    "warnings": [],
                    "output": "ok",
                },
                "tests": {
                    "success": True,
                    "errors": [],
                    "warnings": [],
                    "output": "12 passed",
                },
            },
        }
        with (
            patch(
                "cortex.tools.pre_commit_preflight_helpers.execute_pre_commit_checks",
                new_callable=AsyncMock,
                return_value=exec_result,
            ),
            patch(
                "cortex.tools.pre_commit_preflight_helpers.fix_markdown_lint",
                new_callable=AsyncMock,
                return_value=_make_markdown_result(files_with_errors=0),
            ),
        ):
            result = await run_preflight_checks(
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        check_names = {e["name"] for e in result["checks"]}
        assert check_names == {"format", "quality", "tests", "markdown_lint"}
        assert result["preflight_passed"] is True


# ============================================================================
# Phase A – preflight helper unit tests (pure functions)
# ============================================================================


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


# ============================================================================
# Phase B – run_docs_and_memory_bank_sync (MCP tool integration tests)
# ============================================================================


class TestRunDocsAndMemoryBankSync:
    """Tests for run_docs_and_memory_bank_sync MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Docs/memory phase passes when both validations are valid."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": True,
            "total_invalid_format": 0,
            "total_invalid_with_time": 0,
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        check_names = {e["name"] for e in result["checks"]}
        assert "timestamps" in check_names
        assert "roadmap_sync" in check_names

    @pytest.mark.asyncio
    async def test_sets_flag_when_timestamps_invalid(self) -> None:
        """docs_phase_passed is False when timestamps report errors."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": False,
            "total_invalid_format": 2,
            "total_invalid_with_time": 1,
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is False
        ts_entry = next(e for e in result["checks"] if e["name"] == "timestamps")
        assert ts_entry["status"] == "error"
        assert ts_entry["errors"] == 3

    @pytest.mark.asyncio
    async def test_reports_tool_error(self) -> None:
        """Tool-level validation error is surfaced with status=error."""
        timestamps_payload = {
            "status": "error",
            "error": "roadmap missing",
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "error"
        assert result["error_type"] == "DocsMemoryBankToolError"
        assert "underlying validation error" in result["error"]

    @pytest.mark.asyncio
    async def test_both_validations_fail(self) -> None:
        """Both timestamps and roadmap invalid sets docs_phase_passed=False."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": False,
            "total_invalid_format": 1,
            "total_invalid_with_time": 0,
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": False,
            "summary": {
                "missing_entries_count": 2,
                "invalid_references_count": 1,
                "completed_entries_count": 0,
                "warnings_count": 1,
            },
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is False
        # Both checks should be error
        for entry in result["checks"]:
            assert entry["status"] == "error"

    @pytest.mark.asyncio
    async def test_roadmap_sync_error_surfaces(self) -> None:
        """Roadmap sync tool error is surfaced correctly."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": True,
            "total_invalid_format": 0,
            "total_invalid_with_time": 0,
        }
        roadmap_payload = {
            "status": "error",
            "error": "filesystem error",
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "error"
        assert result["error_type"] == "DocsMemoryBankToolError"

    @pytest.mark.asyncio
    async def test_invalid_json_from_validation_handled(self) -> None:
        """Invalid JSON from validate() is gracefully handled as None."""
        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = ["NOT-JSON", "ALSO-NOT-JSON"]
            result = await run_docs_and_memory_bank_sync()

        # Both results are None, so docs_phase_passed should be True
        # (both default to True when None)
        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        assert result["checks"] == []

    @pytest.mark.asyncio
    async def test_validation_result_not_dict_handled(self) -> None:
        """Valid JSON that is not a dict (e.g. array) from validate() is treated as None."""
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 0,
            },
        }
        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = ["[1, 2]", json.dumps(roadmap_payload)]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        check_names = {e["name"] for e in result["checks"]}
        assert "roadmap_sync" in check_names
        assert "timestamps" not in check_names

    @pytest.mark.asyncio
    async def test_roadmap_sync_with_warnings_only(self) -> None:
        """Roadmap sync passes with warnings but no errors."""
        timestamps_payload = {
            "status": "success",
            "check_type": "timestamps",
            "valid": True,
            "total_invalid_format": 0,
            "total_invalid_with_time": 0,
        }
        roadmap_payload = {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": True,
            "summary": {
                "missing_entries_count": 0,
                "invalid_references_count": 0,
                "completed_entries_count": 0,
                "warnings_count": 3,
            },
        }

        with patch(
            "cortex.tools.pre_commit_docs_memory_helpers.validate",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = [
                json.dumps(timestamps_payload),
                json.dumps(roadmap_payload),
            ]
            result = await run_docs_and_memory_bank_sync()

        assert result["status"] == "success"
        assert result["docs_phase_passed"] is True
        roadmap_entry = next(e for e in result["checks"] if e["name"] == "roadmap_sync")
        assert roadmap_entry["warnings"] == 3
        assert roadmap_entry["status"] == "success"


# ============================================================================
# Phase B – docs/memory helper unit tests (pure functions)
# ============================================================================


class TestDocsMemoryHelperFunctions:
    """Unit tests for pure helper functions in pre_commit_docs_memory_helpers."""

    def test_compute_passed_both_none(self) -> None:
        """Both None results default to passed."""
        assert _compute_docs_memory_bank_passed(None, None) is True

    def test_compute_passed_timestamps_invalid(self) -> None:
        """Fails when timestamps are invalid."""
        ts = cast(JsonDict, {"valid": False})
        assert _compute_docs_memory_bank_passed(ts, None) is False

    def test_compute_passed_roadmap_invalid(self) -> None:
        """Fails when roadmap_sync is invalid."""
        rm = cast(JsonDict, {"valid": False})
        assert _compute_docs_memory_bank_passed(None, rm) is False

    def test_build_timestamps_summary_none(self) -> None:
        """Returns None when timestamps_result is None."""
        assert _build_timestamps_summary(None) is None

    def test_build_timestamps_summary_valid(self) -> None:
        """Builds success summary for valid timestamps."""
        ts = cast(
            JsonDict,
            {
                "valid": True,
                "total_invalid_format": 0,
                "total_invalid_with_time": 0,
            },
        )
        summary = _build_timestamps_summary(ts)
        assert summary is not None
        assert summary.status == "success"
        assert summary.errors is None  # 0 counts result in None

    def test_build_timestamps_summary_invalid(self) -> None:
        """Builds error summary with counts for invalid timestamps."""
        ts = cast(
            JsonDict,
            {
                "valid": False,
                "total_invalid_format": 3,
                "total_invalid_with_time": 2,
            },
        )
        summary = _build_timestamps_summary(ts)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors == 5

    def test_build_roadmap_sync_summary_none(self) -> None:
        """Returns None when roadmap_result is None."""
        assert _build_roadmap_sync_summary(None) is None

    def test_build_roadmap_sync_summary_valid(self) -> None:
        """Builds success summary for valid roadmap sync."""
        rm = cast(
            JsonDict,
            {
                "valid": True,
                "summary": {
                    "missing_entries_count": 0,
                    "invalid_references_count": 0,
                    "completed_entries_count": 0,
                    "warnings_count": 0,
                },
            },
        )
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "success"
        assert summary.errors is None

    def test_build_roadmap_sync_summary_with_errors(self) -> None:
        """Builds error summary with aggregated error count."""
        rm = cast(
            JsonDict,
            {
                "valid": False,
                "summary": {
                    "missing_entries_count": 1,
                    "invalid_references_count": 2,
                    "completed_entries_count": 0,
                    "warnings_count": 5,
                },
            },
        )
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors == 3
        assert summary.warnings == 5

    def test_build_roadmap_sync_summary_non_dict_summary(self) -> None:
        """Handles non-dict summary field gracefully."""
        rm = cast(JsonDict, {"valid": False, "summary": "not a dict"})
        summary = _build_roadmap_sync_summary(rm)
        assert summary is not None
        assert summary.status == "error"
        assert summary.errors is None

    def test_build_docs_memory_bank_summaries_empty(self) -> None:
        """Returns empty list when both results are None."""
        assert _build_docs_memory_bank_summaries(None, None) == []

    def test_build_docs_memory_bank_model_success(self) -> None:
        """Builds success model with correct shape."""
        ts = cast(
            JsonDict,
            {
                "status": "success",
                "valid": True,
                "total_invalid_format": 0,
                "total_invalid_with_time": 0,
            },
        )
        rm = cast(
            JsonDict,
            {
                "status": "success",
                "valid": True,
                "summary": {
                    "missing_entries_count": 0,
                    "invalid_references_count": 0,
                    "completed_entries_count": 0,
                    "warnings_count": 0,
                },
            },
        )
        model = _build_docs_memory_bank_model(ts, rm)
        assert model["status"] == "success"
        assert model["docs_phase_passed"] is True

    def test_build_docs_memory_bank_model_error(self) -> None:
        """Builds error model when tool error detected."""
        ts = cast(JsonDict, {"status": "error", "error": "crash"})
        model = _build_docs_memory_bank_model(ts, None)
        assert model["status"] == "error"
        assert model["error_type"] == "DocsMemoryBankToolError"

    def test_build_docs_memory_bank_model_both_none(self) -> None:
        """Builds success model when both inputs are None."""
        model = _build_docs_memory_bank_model(None, None)
        assert model["status"] == "success"
        assert model["docs_phase_passed"] is True
        assert model["checks"] == []
