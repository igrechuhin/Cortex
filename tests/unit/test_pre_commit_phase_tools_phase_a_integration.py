"""Integration tests for execute_pre_commit_checks(phase='A')."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks
from tests.unit.pre_commit_phase_tools_support import (
    detached_phase_a_mock_payload,
    get_checks_list,
    make_markdown_result,
    make_multi_check_exec_result,
    make_pre_commit_result,
)


@pytest.fixture(autouse=True)
def _disable_detached_mode():  # type: ignore[misc]  # noqa: ANN202
    """Phase tests exercise the inline runners; disable detached mode."""
    with patch(
        "cortex.tools.execution.pre_commit_detached.DETACHED_ENABLED",
        False,
    ):
        yield


class TestRunPreflightChecks:
    """Tests for execute_pre_commit_checks(phase='A') (Phase A preflight)."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Preflight passes when checks and markdown lint have no errors."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="success", tests_success=True),
                make_markdown_result(files_with_errors=0),
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        assert result["language"] == "python"
        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert "tests" in check_names
        assert "markdown_lint" in check_names

    @pytest.mark.asyncio
    async def test_sets_flag_when_checks_fail(self) -> None:
        """preflight_passed is False when checks report errors."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="error", tests_success=False),
                make_markdown_result(files_with_errors=0),
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is False
        tests_entry = next(
            (e for e in get_checks_list(result) if e.get("name") == "tests"), None
        )
        assert tests_entry is not None
        assert tests_entry.get("status") == "error"

    @pytest.mark.asyncio
    async def test_reports_tool_error(self) -> None:
        """Tool-level error is surfaced with status=error."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(
                    status="error",
                    tests_success=False,
                    error_payload=True,
                ),
                make_markdown_result(files_with_errors=0),
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "error"
        assert result["error_type"] == "PreflightToolError"
        assert "underlying tool error" in str(result.get("error", ""))

    @pytest.mark.asyncio
    async def test_markdown_lint_errors_fail_preflight(self) -> None:
        """Preflight fails when markdown lint finds files with errors."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="success", tests_success=True),
                make_markdown_result(files_with_errors=3),
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is False
        md_entry = next(
            (e for e in get_checks_list(result) if e.get("name") == "markdown_lint"),
            None,
        )
        assert md_entry is not None
        assert md_entry.get("status") == "error"
        assert md_entry.get("errors") == 3

    @pytest.mark.asyncio
    async def test_markdown_tool_error_surfaces(self) -> None:
        """Markdown tool-level error makes status=error."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="success", tests_success=True),
                make_markdown_result(
                    error_message="CLI not found",
                    tool_error=True,
                ),
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "error"
        assert result["error_type"] == "PreflightToolError"

    @pytest.mark.asyncio
    async def test_invalid_markdown_json_gracefully_handled(self) -> None:
        """Invalid JSON from markdown lint is treated as None result."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="success", tests_success=True),
                "NOT-JSON",
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert "markdown_lint" not in check_names

    @pytest.mark.asyncio
    async def test_markdown_result_not_dict_gracefully_handled(self) -> None:
        """Valid JSON that is not a dict (e.g. array) is treated as None result."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = detached_phase_a_mock_payload(
                make_pre_commit_result(status="success", tests_success=True),
                "[1, 2]",
            )

            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        assert result["status"] == "success"
        assert result["preflight_passed"] is True
        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert "markdown_lint" not in check_names

    @pytest.mark.asyncio
    @pytest.mark.timeout(20)
    async def test_multiple_check_results_in_summaries(self) -> None:
        """Multiple checks from execute_pre_commit_checks appear in summaries."""
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_detached_phase_a_checks",
            new_callable=AsyncMock,
            return_value=detached_phase_a_mock_payload(
                make_multi_check_exec_result(),
                make_markdown_result(files_with_errors=0),
            ),
        ):
            result = await execute_pre_commit_checks(
                phase="A",
                test_timeout=300,
                coverage_threshold=0.9,
                strict_mode=False,
            )

        check_names = {str(e.get("name", "")) for e in get_checks_list(result)}
        assert check_names == {"format", "quality", "tests", "markdown_lint"}
        assert result["preflight_passed"] is True
