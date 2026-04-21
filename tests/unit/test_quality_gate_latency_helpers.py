"""Tests for quality gate latency / response-size helpers (plan: reduce QG tokens).

Plan Step 7: full-tree ``run_quality_gate`` (MCP) verified green on 2026-04-03; field
latency/token success criteria remain for the next measurement window.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_process import poll_interval_for_elapsed
from cortex.tools.execution.pre_commit_zero_arg_tools import (
    autofix,
    run_quality_gate_inner,
    trim_passing_quality_gate_result,
)

_TRIM_FAIL_PHASE_A: ModelDict = {
    "status": "error",
    "preflight_passed": False,
    "checks": [{"name": "type_check", "output": "detail-for-agent"}],
}


def _enter_quality_gate_inner_mocks(
    stack: ExitStack, root: Path, force_fresh: bool
) -> MagicMock:
    """Patches for `run_quality_gate_inner` tests; returns `clear_all_cached_results` mock."""
    mod = "cortex.tools.execution.pre_commit_zero_arg_tools"
    passing: ModelDict = {"status": "success", "preflight_passed": True}
    _ = stack.enter_context(patch(f"{mod}.get_current_project_root", return_value=root))
    _ = stack.enter_context(
        patch(
            f"{mod}._read_quality_gate_config", return_value=(300, 0.9, force_fresh, {})
        )
    )
    mock_clear = stack.enter_context(patch(f"{mod}.clear_all_cached_results"))
    _ = stack.enter_context(
        patch(
            f"{mod}._spawn_and_poll_phase_a",
            new_callable=AsyncMock,
            return_value=passing,
        )
    )
    _ = stack.enter_context(patch(f"{mod}.apply_reflection_to_gate_result"))
    _ = stack.enter_context(
        patch(f"{mod}.persist_gate_feedback", new_callable=AsyncMock)
    )
    mock_gi = stack.enter_context(patch(f"{mod}.PipelineDirtyTracker.get_instance"))
    mock_gi.return_value.record_phase_a = MagicMock()
    return mock_clear


def _enter_trim_fail_mocks(
    stack: ExitStack, root: Path
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Patches for failing `run_quality_gate_inner` trim path; returns append, trim, tracker mocks."""
    mod = "cortex.tools.execution.pre_commit_zero_arg_tools"
    _ = stack.enter_context(patch(f"{mod}.get_current_project_root", return_value=root))
    _ = stack.enter_context(
        patch(f"{mod}._read_quality_gate_config", return_value=(300, 0.9, True, {}))
    )
    _ = stack.enter_context(patch(f"{mod}.clear_all_cached_results"))
    _ = stack.enter_context(
        patch(
            f"{mod}._spawn_and_poll_phase_a",
            new_callable=AsyncMock,
            return_value=_TRIM_FAIL_PHASE_A,
        )
    )
    _ = stack.enter_context(patch(f"{mod}.apply_reflection_to_gate_result"))
    _ = stack.enter_context(
        patch(f"{mod}.persist_gate_feedback", new_callable=AsyncMock)
    )
    mock_append = stack.enter_context(
        patch(f"{mod}.append_agent_log_to_quality_result")
    )
    mock_trim = stack.enter_context(patch(f"{mod}.trim_passing_quality_gate_result"))
    mock_gi = stack.enter_context(patch(f"{mod}.PipelineDirtyTracker.get_instance"))
    mock_gi.return_value.record_phase_a = MagicMock()
    return mock_append, mock_trim, mock_gi


def _enter_autofix_hook_mocks(stack: ExitStack, root: Path) -> AsyncMock:
    mod = "cortex.tools.execution.pre_commit_zero_arg_tools"
    _ = stack.enter_context(patch(f"{mod}.get_current_project_root", return_value=root))
    _ = stack.enter_context(
        patch(
            f"{mod}.autofix_impl",
            new_callable=AsyncMock,
            return_value='{"status":"success","changed_files":2}',
        )
    )
    _ = stack.enter_context(patch(f"{mod}.append_agent_log_to_autofix_result"))
    _ = stack.enter_context(patch(f"{mod}.clear_all_cached_results"))
    return stack.enter_context(
        patch(f"{mod}.append_log_entry_best_effort", new_callable=AsyncMock)
    )


class TestPollIntervalAdaptive:
    def test_fast_window_uses_one_second(self) -> None:
        assert poll_interval_for_elapsed(0.0) == 1.0
        assert poll_interval_for_elapsed(29.9) == 1.0

    def test_after_thirty_seconds_uses_three_seconds(self) -> None:
        assert poll_interval_for_elapsed(30.0) == 3.0
        assert poll_interval_for_elapsed(100.0) == 3.0


class TestTrimPassingResult:
    def test_keeps_summary_fields_drops_heavy_keys(self) -> None:
        result: ModelDict = {
            "status": "success",
            "preflight_passed": True,
            "checks_performed": ["format", "tests"],
            "markdown_result": {"status": "success"},
            "results": {"tests": {"success": True}},
            "checks": [{"name": "x", "status": "passed", "output": "huge" * 1000}],
            "agent_log": "## log",
        }
        out = trim_passing_quality_gate_result(result)
        assert out is result
        assert "results" not in result
        assert "checks" not in result
        assert "agent_log" not in result
        assert result["checks_performed"] == ["format", "tests"]
        assert result["preflight_passed"] is True

    def test_preserves_reflection_when_present(self) -> None:
        result: ModelDict = {
            "preflight_passed": True,
            "status": "success",
            "reflection_result": {"findings": []},
            "results": {},
        }
        _ = trim_passing_quality_gate_result(result)
        assert "reflection_result" in result
        assert "results" not in result

    def test_trimmed_json_under_mcp_token_budget_heuristic(self) -> None:
        """Passing-run trim should drop heavy keys so serialized size stays < ~800 tokens."""
        result: ModelDict = {
            "status": "success",
            "preflight_passed": True,
            "checks_performed": ["format", "tests"],
            "markdown_result": {"status": "success"},
            "summary": "ok",
            "results": {"tests": {"blob": "x" * 20_000}},
            "checks": [{"name": "t", "status": "passed", "output": "y" * 40_000}],
        }
        _ = trim_passing_quality_gate_result(result)
        estimated_tokens = max(1, len(json.dumps(result)) // 4)
        assert estimated_tokens < 800


class TestRunQualityGateInnerCacheClear:
    """Verify Step 1 plan behavior: clear_all_cached_results only when force_fresh."""

    @pytest.mark.asyncio
    async def test_skips_clear_when_force_fresh_false(self) -> None:
        root = Path("/tmp/cortex-qg-cache-test")
        with ExitStack() as stack:
            mock_clear = _enter_quality_gate_inner_mocks(stack, root, False)
            _ = await run_quality_gate_inner(None, LocalExecutionEnvironment())
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_when_force_fresh_true(self) -> None:
        root = Path("/tmp/cortex-qg-cache-test-2")
        with ExitStack() as stack:
            mock_clear = _enter_quality_gate_inner_mocks(stack, root, True)
            _ = await run_quality_gate_inner(None, LocalExecutionEnvironment())
        mock_clear.assert_called_once_with(root)


class TestRunQualityGateInnerTrimPass:
    """Failing runs must keep full `checks` / detail payloads (plan Step 2)."""

    @pytest.mark.asyncio
    async def test_skips_trim_when_preflight_failed(self) -> None:
        root = Path("/tmp/cortex-qg-trim-skip-fail")
        with ExitStack() as stack:
            mock_append, mock_trim, mock_gi = _enter_trim_fail_mocks(stack, root)
            out = await run_quality_gate_inner(None, LocalExecutionEnvironment())
        mock_trim.assert_not_called()
        mock_append.assert_called_once()
        mock_gi.return_value.record_phase_a.assert_not_called()
        assert out["checks"] == [{"name": "type_check", "output": "detail-for-agent"}]


class TestOperationsLogHooks:
    """Quality tools should append best-effort operations-log entries."""

    @pytest.mark.asyncio
    async def test_run_quality_gate_inner_appends_operations_log(self) -> None:
        root = Path("/tmp/cortex-qg-log-hook")
        with ExitStack() as stack:
            _ = _enter_quality_gate_inner_mocks(stack, root, False)
            mock_log = stack.enter_context(
                patch(
                    "cortex.tools.execution.pre_commit_zero_arg_tools.append_log_entry_best_effort",
                    new_callable=AsyncMock,
                )
            )
            _ = await run_quality_gate_inner(None, LocalExecutionEnvironment())
        mock_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_autofix_appends_operations_log(self) -> None:
        root = Path("/tmp/cortex-autofix-log-hook")
        with ExitStack() as stack:
            mock_log = _enter_autofix_hook_mocks(stack, root)
            _ = await autofix(None)
        mock_log.assert_awaited_once()
