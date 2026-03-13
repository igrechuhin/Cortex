"""Tests for pipeline_handoff — structured inter-agent communication.

Covers all six operations: init, write_task, read_task, write_result,
read_state, clear. Tests verify file creation, content, and error cases.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInit:
    async def test_init_creates_pipeline_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(await pipeline_handoff(operation="init", pipeline="commit"))
        assert result["status"] == "ok"
        pdir = Path(result["pipeline_dir"])
        assert pdir.exists()
        assert (pdir / "pipeline.json").exists()

    async def test_init_writes_manifest_with_session_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        init_result = json.loads(
            await pipeline_handoff(operation="init", pipeline="commit")
        )
        pdir = Path(init_result["pipeline_dir"])
        state = json.loads((pdir / "pipeline.json").read_text())
        assert state["session_id"] == init_result["session_id"]
        assert state["pipeline"] == "commit"
        assert "started_at" in state
        assert state["phases"] == {}

    async def test_init_with_data_merges_into_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        init_result = json.loads(
            await pipeline_handoff(
                operation="init",
                pipeline="commit",
                data='{"requested_by": "user", "branch": "main"}',
            )
        )
        pdir = Path(init_result["pipeline_dir"])
        state = json.loads((pdir / "pipeline.json").read_text())
        assert state["requested_by"] == "user"
        assert state["branch"] == "main"

    async def test_init_idempotent_on_second_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="commit")
        result = json.loads(await pipeline_handoff(operation="init", pipeline="commit"))
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# write_task / read_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWriteReadTask:
    async def test_write_task_creates_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="write_task",
                pipeline="commit",
                phase="preflight",
                data='{"snapshot_ref": null}',
            )
        )
        assert result["status"] == "ok"
        task_file = Path(result["task_file"])
        assert task_file.exists()
        assert task_file.name == "preflight-task.json"

    async def test_read_task_returns_written_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="preflight",
            data='{"coverage_threshold": 0.9, "snapshot_ref": "abc123"}',
        )
        task = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="commit", phase="preflight"
            )
        )
        assert task["coverage_threshold"] == 0.9
        assert task["snapshot_ref"] == "abc123"
        assert task["phase"] == "preflight"
        assert "written_at" in task

    async def test_read_task_missing_returns_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="commit", phase="checks"
            )
        )
        assert result["status"] == "not_found"
        assert "checks" in result["message"]

    async def test_write_task_without_phase_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="write_task", pipeline="commit")
        )
        assert result["status"] == "error"
        assert "phase" in result["error"]

    async def test_write_task_overwrites_previous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="checks",
            data='{"round": 1}',
        )
        await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="checks",
            data='{"round": 2}',
        )
        task = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="commit", phase="checks"
            )
        )
        assert task["round"] == 2


# ---------------------------------------------------------------------------
# write_result / read_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWriteResultReadState:
    async def test_write_result_creates_result_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="write_result",
                pipeline="commit",
                phase="preflight",
                data='{"status": "complete", "snapshot_ref": "abc123"}',
            )
        )
        assert result["status"] == "ok"
        result_file = Path(result["result_file"])
        assert result_file.exists()
        assert result_file.name == "preflight-result.json"

    async def test_write_result_updates_pipeline_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete", "snapshot_ref": "abc123"}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert "preflight" in state["phases"]
        assert state["phases"]["preflight"]["status"] == "complete"
        assert state["phases"]["preflight"]["snapshot_ref"] == "abc123"

    async def test_multiple_phases_accumulate_in_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete", "snapshot_ref": "abc"}',
        )
        await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"status": "passed", "coverage": 0.94}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert set(state["phases"].keys()) == {"preflight", "checks"}
        assert state["phases"]["checks"]["coverage"] == 0.94
        assert "last_updated" in state

    async def test_read_state_not_found_returns_informative_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="nonexistent")
        )
        assert result["status"] == "not_found"
        assert "nonexistent" in result["message"]

    async def test_write_result_without_phase_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="write_result", pipeline="commit")
        )
        assert result["status"] == "error"
        assert "phase" in result["error"]


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestClear:
    async def test_clear_removes_pipeline_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        init_result = json.loads(
            await pipeline_handoff(operation="init", pipeline="commit")
        )
        pdir = Path(init_result["pipeline_dir"])
        assert pdir.exists()
        result = json.loads(
            await pipeline_handoff(operation="clear", pipeline="commit")
        )
        assert result["status"] == "ok"
        assert not pdir.exists()

    async def test_clear_nonexistent_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="clear", pipeline="never_existed")
        )
        assert result["status"] == "ok"

    async def test_read_state_after_clear_returns_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete"}',
        )
        await pipeline_handoff(operation="clear", pipeline="commit")
        result = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Unknown operation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_operation_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )
    result = json.loads(await pipeline_handoff(operation="explode", pipeline="commit"))
    assert result["status"] == "error"
    assert "explode" in result["error"]


# ---------------------------------------------------------------------------
# Full pipeline round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_commit_pipeline_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulates orchestrator + subagent interaction for the commit pipeline."""
    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff.get_or_resolve_project_root",
        AsyncMock(return_value=str(tmp_path)),
    )

    # Orchestrator: init
    init_r = json.loads(await pipeline_handoff(operation="init", pipeline="commit"))
    assert init_r["status"] == "ok"

    # Orchestrator: dispatch preflight with context
    await pipeline_handoff(
        operation="write_task",
        pipeline="commit",
        phase="preflight",
        data='{"requested_by": "user"}',
    )

    # Preflight subagent: read task, do work, write result
    task = json.loads(
        await pipeline_handoff(
            operation="read_task", pipeline="commit", phase="preflight"
        )
    )
    assert task["requested_by"] == "user"

    await pipeline_handoff(
        operation="write_result",
        pipeline="commit",
        phase="preflight",
        data='{"status": "complete", "snapshot_ref": "deadbeef", "rules_loaded": true}',
    )

    # Orchestrator: read state, extract snapshot_ref, dispatch checks
    state = json.loads(
        await pipeline_handoff(operation="read_state", pipeline="commit")
    )
    snapshot_ref = state["phases"]["preflight"]["snapshot_ref"]
    assert snapshot_ref == "deadbeef"

    await pipeline_handoff(
        operation="write_task",
        pipeline="commit",
        phase="checks",
        data=json.dumps({"snapshot_ref": snapshot_ref, "coverage_threshold": 0.9}),
    )

    # Checks subagent: read task (receives snapshot_ref from preflight), write result
    checks_task = json.loads(
        await pipeline_handoff(operation="read_task", pipeline="commit", phase="checks")
    )
    assert checks_task["snapshot_ref"] == "deadbeef"

    await pipeline_handoff(
        operation="write_result",
        pipeline="commit",
        phase="checks",
        data='{"status": "passed", "coverage": 0.94, "fix_iterations": 0}',
    )

    # Final state has both phases
    final_state = json.loads(
        await pipeline_handoff(operation="read_state", pipeline="commit")
    )
    assert final_state["phases"]["preflight"]["status"] == "complete"
    assert final_state["phases"]["checks"]["status"] == "passed"
    assert final_state["phases"]["checks"]["coverage"] == 0.94

    # Cleanup
    clear_r = json.loads(await pipeline_handoff(operation="clear", pipeline="commit"))
    assert clear_r["status"] == "ok"


# ---------------------------------------------------------------------------
# Bug fixes: dict data + read_task fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDataCoercion:
    """data can be a JSON string OR a native dict — both must be accepted."""

    async def test_write_result_accepts_dict_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cursor sends data as a dict; tool must serialise it, not reject it."""
        _resolve_root(monkeypatch, tmp_path)
        # Pass a native Python dict (simulates what Cursor's LLM sends)
        result = json.loads(
            await pipeline_handoff(
                operation="write_result",
                pipeline="commit",
                phase="verify",
                data={"status": "passed", "roadmap_check": "passed"},  # type: ignore[arg-type]
            )
        )
        assert result["status"] == "ok"
        # Verify the written result contains the correct content
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert state["phases"]["verify"]["status"] == "passed"
        assert state["phases"]["verify"]["roadmap_check"] == "passed"

    async def test_write_task_accepts_dict_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """write_task also accepts a dict for data."""
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="write_task",
                pipeline="commit",
                phase="checks",
                data={"coverage_threshold": 0.9, "snapshot_ref": "abc"},  # type: ignore[arg-type]
            )
        )
        assert result["status"] == "ok"
        task = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="commit", phase="checks"
            )
        )
        assert task["coverage_threshold"] == 0.9
        assert task["snapshot_ref"] == "abc"

    async def test_write_result_accepts_string_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """String data still works (existing behaviour must not regress)."""
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="write_result",
                pipeline="commit",
                phase="docs",
                data='{"status": "complete", "docs_phase_passed": true}',
            )
        )
        assert result["status"] == "ok"
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert state["phases"]["docs"]["docs_phase_passed"] is True


@pytest.mark.asyncio
class TestReadTaskFallback:
    """read_task with no task file falls back to pipeline state."""

    async def test_read_task_not_found_includes_pipeline_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no task file exists, pipeline state from prior phases is returned."""
        _resolve_root(monkeypatch, tmp_path)
        # Write a result for a prior phase
        await pipeline_handoff(
            operation="write_result",
            pipeline="implement",
            phase="select",
            data='{"status": "complete", "selected_step": "Fix something"}',
        )
        # Read task for the next phase — no write_task was called
        result = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="implement", phase="code"
            )
        )
        assert result["status"] == "not_found"
        # But pipeline_state is populated with the prior phase result
        assert "pipeline_state" in result
        assert "select" in result["pipeline_state"]["phases"]
        assert (
            result["pipeline_state"]["phases"]["select"]["selected_step"]
            == "Fix something"
        )

    async def test_read_task_not_found_empty_pipeline_returns_empty_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no pipeline exists at all, pipeline_state is empty dict."""
        _resolve_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="read_task", pipeline="implement", phase="select"
            )
        )
        assert result["status"] == "not_found"
        assert result["pipeline_state"] == {}
