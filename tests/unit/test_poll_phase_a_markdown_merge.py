"""Tests for markdown-result merging in _poll_phase_a_result.

Verifies that the detached worker's ``markdown_result`` is merged into the
quality-gate response and that ``preflight_passed`` is set to False when
markdown lint reports errors — preventing silent CI failures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.execution.pre_commit_zero_arg_tools import (
    _markdown_result_has_errors,  # pyright: ignore[reportPrivateUsage]
    _poll_phase_a_result,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# _markdown_result_has_errors
# ---------------------------------------------------------------------------


class TestMarkdownResultHasErrors:
    """Unit tests for _markdown_result_has_errors helper."""

    def test_no_errors(self) -> None:
        assert (
            _markdown_result_has_errors({"files_with_errors": 0, "status": "success"})
            is False
        )

    def test_files_with_errors_int(self) -> None:
        assert (
            _markdown_result_has_errors({"files_with_errors": 1, "status": "error"})
            is True
        )

    def test_files_with_errors_str(self) -> None:
        assert _markdown_result_has_errors({"files_with_errors": "2"}) is True

    def test_error_status_non_timeout(self) -> None:
        assert (
            _markdown_result_has_errors(
                {"files_with_errors": 0, "status": "error", "error": "rumdl not found"}
            )
            is True
        )

    def test_error_status_timeout_ignored(self) -> None:
        """Timeout errors are not treated as lint failures."""
        assert (
            _markdown_result_has_errors(
                {"files_with_errors": 0, "status": "error", "error": "timeout"}
            )
            is False
        )

    def test_empty_dict(self) -> None:
        assert _markdown_result_has_errors({}) is False

    def test_missing_status_with_zero_errors(self) -> None:
        assert _markdown_result_has_errors({"files_with_errors": 0}) is False


# ---------------------------------------------------------------------------
# _poll_phase_a_result — markdown merging
# ---------------------------------------------------------------------------


def _fake_result_file(
    checks_result: dict[str, Any],
    markdown_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a detached-worker result envelope."""
    envelope: dict[str, Any] = {
        "version": 1,
        "status": "completed",
        "result": checks_result,
    }
    if markdown_result is not None:
        envelope["markdown_result"] = markdown_result
    return envelope


@pytest.fixture()
def _mock_project_root(tmp_path: Path) -> Path:  # pyright: ignore[reportUnusedFunction]
    session_dir = tmp_path / ".cortex" / ".session"
    session_dir.mkdir(parents=True)
    return tmp_path


class TestPollPhaseAMarkdownMerge:
    """Verify markdown_result is merged and preflight_passed is adjusted."""

    @pytest.mark.asyncio()
    async def test_markdown_errors_set_preflight_false(
        self, _mock_project_root: Path
    ) -> None:
        checks = {"preflight_passed": True, "status": "success"}
        md = {"files_with_errors": 1, "status": "error", "output": "MD036"}
        envelope = _fake_result_file(checks, md)

        with (
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.get_cortex_path",
                return_value=_mock_project_root / ".cortex" / ".session",
            ),
            patch(
                "cortex.tools.execution.pre_commit_detached.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            result = await _poll_phase_a_result(
                _mock_project_root, "test-job", timeout=30, ctx=None
            )

        assert result["preflight_passed"] is False
        assert "markdown_result" in result

    @pytest.mark.asyncio()
    async def test_clean_markdown_preserves_preflight(
        self, _mock_project_root: Path
    ) -> None:
        checks = {"preflight_passed": True, "status": "success"}
        md = {"files_with_errors": 0, "status": "success"}
        envelope = _fake_result_file(checks, md)

        with (
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.get_cortex_path",
                return_value=_mock_project_root / ".cortex" / ".session",
            ),
            patch(
                "cortex.tools.execution.pre_commit_detached.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            result = await _poll_phase_a_result(
                _mock_project_root, "test-job", timeout=30, ctx=None
            )

        assert result["preflight_passed"] is True
        assert result["markdown_result"] == md

    @pytest.mark.asyncio()
    async def test_no_markdown_result_in_envelope(
        self, _mock_project_root: Path
    ) -> None:
        """When markdown lint was not requested, result is unchanged."""
        checks = {"preflight_passed": True, "status": "success"}
        envelope = _fake_result_file(checks, markdown_result=None)

        with (
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.get_cortex_path",
                return_value=_mock_project_root / ".cortex" / ".session",
            ),
            patch(
                "cortex.tools.execution.pre_commit_detached.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            result = await _poll_phase_a_result(
                _mock_project_root, "test-job", timeout=30, ctx=None
            )

        assert result["preflight_passed"] is True
        assert "markdown_result" not in result

    @pytest.mark.asyncio()
    async def test_already_failed_checks_stays_failed(
        self, _mock_project_root: Path
    ) -> None:
        """If checks already failed, markdown clean doesn't flip to True."""
        checks = {"preflight_passed": False, "status": "error"}
        md = {"files_with_errors": 0, "status": "success"}
        envelope = _fake_result_file(checks, md)

        with (
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.get_cortex_path",
                return_value=_mock_project_root / ".cortex" / ".session",
            ),
            patch(
                "cortex.tools.execution.pre_commit_detached.poll_for_result",
                new_callable=AsyncMock,
                return_value=envelope,
            ),
        ):
            result = await _poll_phase_a_result(
                _mock_project_root, "test-job", timeout=30, ctx=None
            )

        assert result["preflight_passed"] is False
