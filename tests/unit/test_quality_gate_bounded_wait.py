"""Behavior regressions for resumable Phase A calls within the MCP deadline."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.tools.execution import pre_commit_zero_arg_tools as gate
from cortex.tools.execution.pre_commit_detached import compute_args_hash
from cortex.tools.execution.pre_commit_phase_dispatch import PHASE_A_CHECKS


def _result_path(root: Path) -> Path:
    job_id = compute_args_hash(list(PHASE_A_CHECKS), 600, 0.9, False, True)
    return root / ".cortex" / ".session" / f"pre_commit_result_{job_id}.json"


def _write_envelope(path: Path, envelope: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(envelope))


def _running_envelope() -> dict[str, object]:
    return {
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
        "quality_gate_pending": True,
    }


def _terminal_envelope(outcome: str) -> dict[str, object]:
    if outcome == "worker_error":
        return {
            "status": "error",
            "error": "worker could not execute checks",
            "quality_gate_pending": True,
        }
    return {
        "status": "completed",
        "quality_gate_pending": True,
        "completed_at": time.time(),
        "result": {
            "status": "error" if outcome == "checks_failed" else "success",
            "checks": [{"name": "tests", "output": "failing assertion detail"}],
            "results": {"tests": {"success": outcome != "checks_failed"}},
        },
        "markdown_result": {
            "status": "error" if outcome == "markdown_failed" else "success",
            "files_with_errors": int(outcome == "markdown_failed"),
        },
    }


def _patch_finalization(stack: ExitStack) -> tuple[AsyncMock, MagicMock]:
    module = "cortex.tools.execution.pre_commit_zero_arg_tools"
    feedback = stack.enter_context(
        patch(f"{module}.persist_gate_feedback", new_callable=AsyncMock)
    )
    tracker = stack.enter_context(patch(f"{module}.PipelineDirtyTracker.get_instance"))
    for name in (
        "apply_reflection_to_gate_result",
        "append_agent_log_to_quality_result",
    ):
        _ = stack.enter_context(patch(f"{module}.{name}"))
    for name in ("record_gate_result", "append_log_entry_best_effort"):
        _ = stack.enter_context(patch(f"{module}.{name}", new_callable=AsyncMock))
    return feedback, tracker.return_value


@pytest.fixture
def bounded_gate(
    tmp_path: Path,
) -> Iterator[tuple[MagicMock, AsyncMock, MagicMock]]:
    """Keep real job selection/polling; replace only worker launch and publication."""

    def spawn_worker(*args: object, **kwargs: object) -> None:
        _write_envelope(_result_path(tmp_path), _running_envelope())

    with ExitStack() as stack:
        _ = stack.enter_context(
            patch.object(gate, "QUALITY_GATE_WAIT_SECONDS", 0.02, create=True)
        )
        _ = stack.enter_context(
            patch.object(gate, "get_current_project_root", return_value=tmp_path)
        )
        _ = stack.enter_context(
            patch(
                "cortex.core.mcp_stability_usage.get_current_managers", return_value={}
            )
        )
        _ = stack.enter_context(
            patch(
                "cortex.tools.execution.pre_commit_process.poll_interval_for_elapsed",
                return_value=0.001,
            )
        )
        spawn = stack.enter_context(
            patch(
                "cortex.tools.execution.pre_commit_detached.spawn_detached_worker",
                side_effect=spawn_worker,
            )
        )
        feedback, tracker = _patch_finalization(stack)
        yield spawn, feedback, tracker


@pytest.mark.asyncio
async def test_public_gate_resumes_live_job_despite_force_fresh(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    spawn, feedback, tracker = bounded_gate
    first = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)
    second = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)
    result_file = _result_path(tmp_path)

    assert first["status"] == second["status"] == "running"
    assert first.get("preflight_passed") is not True
    assert second.get("preflight_passed") is not True
    assert (
        first["job_id"]
        == second["job_id"]
        == result_file.stem.removeprefix("pre_commit_result_")
    )
    assert (
        Path(str(first["result_file"]))
        == Path(str(second["result_file"]))
        == result_file
    )
    assert json.loads(result_file.read_text())["pid"] == os.getpid()
    spawn.assert_called_once()
    feedback.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome", ["success", "checks_failed", "markdown_failed", "worker_error"]
)
async def test_pending_gate_returns_real_terminal_outcome(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock], outcome: str
) -> None:
    spawn, feedback, tracker = bounded_gate
    pending = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)
    assert pending["status"] == "running"
    _write_envelope(_result_path(tmp_path), _terminal_envelope(outcome))

    result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    expected_status = (
        "error" if outcome in ("checks_failed", "worker_error") else "success"
    )
    assert result["status"] == expected_status
    assert (result.get("preflight_passed") is True) == (outcome == "success")
    if outcome == "worker_error":
        assert result["error"] == "worker could not execute checks"
    else:
        assert (
            result["markdown_result"] == _terminal_envelope(outcome)["markdown_result"]
        )
        if outcome != "success":
            assert result["checks"] == [
                {"name": "tests", "output": "failing assertion detail"}
            ]
    spawn.assert_called_once()
    assert feedback.await_count == int(outcome != "worker_error")
    assert tracker.record_phase_a.call_count == int(outcome == "success")
    retained = json.loads(_result_path(tmp_path).read_text())
    assert retained["quality_gate_pending"] is False
    evidence_key = "error" if outcome == "worker_error" else "result"
    assert retained[evidence_key] == _terminal_envelope(outcome)[evidence_key]


@pytest.mark.asyncio
async def test_public_budget_includes_contended_root_lock(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    spawn, feedback, tracker = bounded_gate
    result_file = _result_path(tmp_path)
    _write_envelope(result_file, _running_envelope())
    lock = gate.get_phase_a_lock(str(tmp_path.resolve()))

    async with lock:
        result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    assert result["status"] == "running"
    assert result.get("preflight_passed") is not True
    assert result["job_id"] == result_file.stem.removeprefix("pre_commit_result_")
    assert Path(str(result["result_file"])) == result_file
    spawn.assert_not_called()
    feedback.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("completed_result_exists", [False, True])
async def test_contended_lock_never_invents_a_worker_handle(
    tmp_path: Path,
    bounded_gate: tuple[MagicMock, AsyncMock, MagicMock],
    completed_result_exists: bool,
) -> None:
    spawn, feedback, tracker = bounded_gate
    result_file = _result_path(tmp_path)
    if completed_result_exists:
        _write_envelope(result_file, _terminal_envelope("success"))

    with patch.object(gate, "record_gate_result", new_callable=AsyncMock) as fitness:
        async with gate.get_phase_a_lock(str(tmp_path.resolve())):
            result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    assert result.get("preflight_passed") is not True
    if completed_result_exists:
        assert result["status"] == "running"
        assert Path(str(result["result_file"])) == result_file
    else:
        assert result["status"] == "error"
        assert "job_id" not in result
        assert "result_file" not in result
    spawn.assert_not_called()
    feedback.assert_not_awaited()
    fitness.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
async def test_changed_configuration_reports_the_actual_live_worker(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    spawn, _, tracker = bounded_gate
    pending = await gate.run_quality_gate()

    with patch.object(
        gate, "_read_quality_gate_config", return_value=(600, 0.95, True, {})
    ):
        result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    assert result["status"] == "running"
    assert result["job_id"] == pending["job_id"]
    assert result["result_file"] == pending["result_file"]
    assert Path(str(result["result_file"])).is_file()
    assert result.get("preflight_passed") is not True
    spawn.assert_called_once()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
async def test_poll_timeout_does_not_record_failed_checks(
    bounded_gate: tuple[MagicMock, AsyncMock, MagicMock],
) -> None:
    _, feedback, tracker = bounded_gate
    timeout_result = {"status": "timeout", "error": "Result polling timed out"}
    with (
        patch.object(gate, "poll_phase_a_result", return_value=timeout_result),
        patch.object(gate, "record_gate_result", new_callable=AsyncMock) as fitness,
    ):
        result = await gate.run_quality_gate()

    assert result == timeout_result
    feedback.assert_not_awaited()
    fitness.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
async def test_worker_launch_error_does_not_record_failed_checks(
    bounded_gate: tuple[MagicMock, AsyncMock, MagicMock],
) -> None:
    _, feedback, tracker = bounded_gate
    launch_error = {"status": "error", "error": "Worker could not be launched"}
    with (
        patch.object(gate, "start_phase_a_job", return_value=launch_error),
        patch.object(gate, "record_gate_result", new_callable=AsyncMock) as fitness,
    ):
        result = await gate.run_quality_gate()

    assert result == launch_error
    feedback.assert_not_awaited()
    fitness.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
async def test_shared_preflight_waits_beyond_public_budget(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    _ = bounded_gate
    task = asyncio.create_task(
        gate.run_detached_phase_a_checks(
            tmp_path,
            test_timeout=600,
            coverage_threshold=0.9,
            strict_mode=False,
            force_fresh=True,
            ctx=None,
            env=LocalExecutionEnvironment(),
        )
    )
    try:
        await asyncio.sleep(0.06)
        assert not task.done()
        _write_envelope(_result_path(tmp_path), _terminal_envelope("checks_failed"))
        result = await asyncio.wait_for(task, timeout=0.5)
        assert result["status"] == "error"
        assert result["preflight_passed"] is False
        assert result["checks"] == [
            {"name": "tests", "output": "failing assertion detail"}
        ]
    finally:
        if not task.done():
            _ = task.cancel()
        _ = await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_force_fresh_does_not_reuse_unmarked_completed_result(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    spawn, feedback, tracker = bounded_gate
    old_result = _terminal_envelope("success")
    _ = old_result.pop("quality_gate_pending")
    _write_envelope(_result_path(tmp_path), old_result)

    result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    assert result["status"] == "running"
    assert result.get("preflight_passed") is not True
    spawn.assert_called_once()
    feedback.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()


@pytest.mark.asyncio
async def test_autofix_leaves_files_unchanged_during_live_gate(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    _ = bounded_gate
    source = tmp_path / "example.py"
    _ = source.write_text("original source")

    def apply_fix(*args: object, **kwargs: object) -> Path:
        _ = source.write_text("mutated source")
        return tmp_path / "unexpected.json"

    pending = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)
    envelope_before = _result_path(tmp_path).read_text()
    with patch(
        "cortex.tools.execution.pre_commit_detached.spawn_detached_fix_worker",
        side_effect=apply_fix,
    ) as spawn_fix:
        result = await asyncio.wait_for(gate.autofix(), timeout=0.5)

    assert result["status"] == "running"
    assert result["job_id"] == pending["job_id"]
    assert source.read_text() == "original source"
    assert _result_path(tmp_path).read_text() == envelope_before
    spawn_fix.assert_not_called()


@pytest.mark.asyncio
async def test_quality_gate_cannot_overlap_live_autofix(
    tmp_path: Path, bounded_gate: tuple[MagicMock, AsyncMock, MagicMock]
) -> None:
    from cortex.tools.execution.pre_commit_detached import (
        fix_args_hash,
        fix_result_path,
    )

    spawn, feedback, tracker = bounded_gate
    result_file = fix_result_path(
        tmp_path / ".cortex" / ".session", fix_args_hash(True)
    )
    envelope: dict[str, object] = {
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
        "autofix_pending": True,
    }
    _write_envelope(result_file, envelope)

    result = await asyncio.wait_for(gate.run_quality_gate(), timeout=0.5)

    assert result["status"] == "running"
    assert result["job_id"] == fix_args_hash(True)
    assert Path(str(result["result_file"])) == result_file
    assert result.get("preflight_passed") is not True
    assert json.loads(result_file.read_text()) == envelope
    spawn.assert_not_called()
    feedback.assert_not_awaited()
    tracker.record_phase_a.assert_not_called()
