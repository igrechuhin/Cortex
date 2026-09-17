"""Autofix calls resume durable workers without overlapping workspace mutations."""

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

from cortex.tools.execution import pre_commit_autofix_job as coordinator
from cortex.tools.execution import pre_commit_zero_arg_tools as gate
from cortex.tools.execution.pre_commit_detached import fix_args_hash, fix_result_path


def _result_path(root: Path) -> Path:
    return fix_result_path(root / ".cortex" / ".session", fix_args_hash(True))


def _write_envelope(path: Path, envelope: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(envelope))


def _running_envelope() -> dict[str, object]:
    return {
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
        "autofix_pending": True,
    }


def _terminal_envelope(outcome: str) -> dict[str, object]:
    if outcome == "worker_error":
        return {
            "status": "error",
            "error": "formatter crashed",
            "autofix_pending": True,
        }
    raw: dict[str, object] = {
        "results": {"fix_errors": {"errors": ["E1"], "warnings": []}},
        "files_modified": ["fixed.py"],
    }
    envelope: dict[str, object] = {"status": "completed", "result": raw}
    if outcome != "legacy":
        envelope.update(
            autofix_pending=True,
            autofix_result={
                "status": "success",
                "errors_fixed": 1,
                "files_modified": ["fixed.py"],
                "remaining_issues": ["manual repair"],
                "suggestions": [{"message": "document the new public function"}],
            },
        )
    return envelope


@pytest.fixture
def bounded_autofix(tmp_path: Path) -> Iterator[MagicMock]:
    def spawn_worker(*args: object, **kwargs: object) -> Path:
        result_path = _result_path(tmp_path)
        _write_envelope(result_path, _running_envelope())
        return result_path

    with ExitStack() as stack:
        _ = stack.enter_context(patch.object(coordinator, "AUTOFIX_WAIT_SECONDS", 0.02))
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
        _ = stack.enter_context(
            patch.object(gate, "append_log_entry_best_effort", new_callable=AsyncMock)
        )
        spawn = stack.enter_context(
            patch(
                "cortex.tools.execution.pre_commit_detached.spawn_detached_fix_worker",
                side_effect=spawn_worker,
            )
        )
        yield spawn


@pytest.mark.asyncio
async def test_deadline_returns_live_handle_and_repeated_calls_resume(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    first = await asyncio.wait_for(gate.autofix(), timeout=0.5)
    evidence = _result_path(tmp_path).with_name("pre_commit_result_previous.json")
    _write_envelope(evidence, {"status": "completed", "result": {"status": "error"}})
    second = await asyncio.wait_for(gate.autofix(), timeout=0.5)

    assert first["status"] == second["status"] == "running"
    assert first["job_id"] == second["job_id"] == fix_args_hash(True)
    assert Path(str(first["result_file"])) == _result_path(tmp_path)
    assert second["result_file"] == first["result_file"]
    assert json.loads(_result_path(tmp_path).read_text())["pid"] == os.getpid()
    bounded_autofix.assert_called_once()
    assert json.loads(evidence.read_text())["result"]["status"] == "error"


@pytest.mark.asyncio
async def test_concurrent_calls_publish_one_worker(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    first, second = await asyncio.wait_for(
        asyncio.gather(gate.autofix(), gate.autofix()), timeout=0.5
    )

    assert first["status"] == second["status"] == "running"
    assert first["result_file"] == second["result_file"] == str(_result_path(tmp_path))
    bounded_autofix.assert_called_once()
    _write_envelope(_result_path(tmp_path), _terminal_envelope("success"))
    recovered = await gate.autofix()
    assert recovered["remaining_issues"] == ["manual repair"]
    bounded_autofix.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "worker_error", "legacy"])
async def test_terminal_outcomes_survive_restart_and_are_delivered_once(
    tmp_path: Path, bounded_autofix: MagicMock, outcome: str
) -> None:
    envelope = _terminal_envelope(outcome)
    _write_envelope(_result_path(tmp_path), envelope)

    result = await asyncio.wait_for(gate.autofix(), timeout=0.5)

    assert result["status"] == ("error" if outcome == "worker_error" else "success")
    if outcome == "worker_error":
        assert "formatter crashed" in str(result)
    else:
        assert result["errors_fixed"] == 1
        assert result["files_modified"] == ["fixed.py"]
        if outcome == "success":
            assert result["remaining_issues"] == ["manual repair"]
            assert result["suggestions"] == [
                {"message": "document the new public function"}
            ]
    bounded_autofix.assert_not_called()
    retained = json.loads(_result_path(tmp_path).read_text())
    assert retained["autofix_pending"] is False
    for key, value in envelope.items():
        if key != "autofix_pending":
            assert retained[key] == value
    next_call = await asyncio.wait_for(gate.autofix(), timeout=0.5)
    assert next_call["status"] == "running"
    bounded_autofix.assert_called_once()


@pytest.mark.asyncio
async def test_cancelled_caller_leaves_worker_recoverable(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    with patch.object(coordinator, "AUTOFIX_WAIT_SECONDS", 10):
        task = asyncio.ensure_future(gate.autofix())
        try:
            async with asyncio.timeout(0.5):
                while not _result_path(tmp_path).exists():
                    await asyncio.sleep(0.001)
            _ = task.cancel()
            assert "CancelledError" in str(await task)
        finally:
            if not task.done():
                _ = task.cancel()
            _ = await asyncio.gather(task, return_exceptions=True)

    resumed = await asyncio.wait_for(gate.autofix(), timeout=0.5)
    assert resumed["status"] == "running"
    assert Path(str(resumed["result_file"])) == _result_path(tmp_path)
    bounded_autofix.assert_called_once()
    _write_envelope(_result_path(tmp_path), _terminal_envelope("success"))
    recovered = await asyncio.wait_for(gate.autofix(), timeout=0.5)
    assert recovered["errors_fixed"] == 1
    bounded_autofix.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("live_worker", [False, True])
async def test_root_lock_contention_is_bounded_without_duplicate_worker(
    tmp_path: Path, bounded_autofix: MagicMock, live_worker: bool
) -> None:
    if live_worker:
        _write_envelope(_result_path(tmp_path), _running_envelope())

    async with gate.get_phase_a_lock(str(tmp_path.resolve())):
        result = await asyncio.wait_for(gate.autofix(), timeout=0.5)

    bounded_autofix.assert_not_called()
    if live_worker:
        assert result["status"] == "running"
        assert Path(str(result["result_file"])) == _result_path(tmp_path)
    else:
        assert result["status"] == "error"
        assert "job_id" not in result
        assert "result_file" not in result


@pytest.mark.asyncio
async def test_dead_worker_error_is_retained_instead_of_rerunning_mutations(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    _write_envelope(_result_path(tmp_path), _running_envelope())
    with patch(
        "cortex.tools.execution.pre_commit_process.is_process_alive", return_value=False
    ):
        result = await asyncio.wait_for(gate.autofix(), timeout=0.5)

    assert result["status"] == "error"
    bounded_autofix.assert_not_called()
    retained = json.loads(_result_path(tmp_path).read_text())
    assert retained["status"] == "error"
    assert retained["autofix_pending"] is False


@pytest.mark.asyncio
async def test_poll_timeout_preserves_live_work_and_later_outcome(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    _write_envelope(_result_path(tmp_path), _running_envelope())
    with patch.object(
        coordinator,
        "poll_for_result",
        new_callable=AsyncMock,
        return_value={"status": "timeout"},
    ):
        pending = await gate.autofix()

    assert pending["status"] == "running"
    assert json.loads(_result_path(tmp_path).read_text())["autofix_pending"] is True
    _write_envelope(_result_path(tmp_path), _terminal_envelope("worker_error"))
    recovered = await gate.autofix()
    assert recovered["status"] == "error"
    assert "formatter crashed" in str(recovered)
    bounded_autofix.assert_not_called()


@pytest.mark.asyncio
async def test_completed_outcome_waits_for_busy_lock_without_being_consumed(
    tmp_path: Path, bounded_autofix: MagicMock
) -> None:
    _write_envelope(_result_path(tmp_path), _terminal_envelope("success"))
    async with gate.get_phase_a_lock(str(tmp_path.resolve())):
        pending = await asyncio.wait_for(gate.autofix(), timeout=0.5)
        assert pending["status"] == "running"
        assert pending["result_file"] == str(_result_path(tmp_path))
        assert json.loads(_result_path(tmp_path).read_text())["autofix_pending"] is True

    recovered = await gate.autofix()
    assert recovered["remaining_issues"] == ["manual repair"]
    bounded_autofix.assert_not_called()
