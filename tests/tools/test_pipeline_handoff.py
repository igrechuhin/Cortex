"""Tests for pipeline_handoff — structured inter-agent communication.

Covers all six operations: init, write_task, read_task, write_result,
read_state, clear. Tests verify file creation, content, and error cases.
"""

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)

# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInit:
    async def test_init_creates_pipeline_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        result = json.loads(await pipeline_handoff(operation="init", pipeline="commit"))
        assert result["status"] == "ok"
        pdir = Path(result["pipeline_dir"])
        assert pdir.exists()
        assert (pdir / "pipeline.json").exists()

    async def test_init_writes_manifest_with_session_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="write_task", pipeline="commit")
        )
        assert result["status"] == "error"
        assert "phase" in result["error"]

    async def test_write_task_overwrites_previous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="checks",
            data='{"round": 1}',
        )
        _ = await pipeline_handoff(
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete", "snapshot_ref": "abc"}',
        )
        _ = await pipeline_handoff(
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="fix")
        )
        assert result["status"] == "not_found"
        assert "fix" in result["message"]

    async def test_write_result_without_phase_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(operation="clear", pipeline="review")
        )
        assert result["status"] == "ok"

    async def test_read_state_after_clear_returns_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete"}',
        )
        _ = await pipeline_handoff(operation="clear", pipeline="commit")
        result = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Token validation & async-to-thread offload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTokenValidation:
    async def test_init_rejects_pipeline_path_traversal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

        outside_name = f"outside_sentinel_{uuid.uuid4().hex}"
        outside_path = tmp_path.parent / outside_name
        assert not outside_path.exists()
        assert list(tmp_path.iterdir()) == []

        result = json.loads(
            await pipeline_handoff(
                operation="init",
                pipeline=f"../../../../{outside_name}",
            )
        )
        assert result["status"] == "error"
        assert not outside_path.exists()
        assert list(tmp_path.iterdir()) == []

    async def test_write_result_rejects_phase_path_traversal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

        outside_name = f"outside_sentinel_{uuid.uuid4().hex}"
        outside_path = tmp_path.parent / outside_name
        assert not outside_path.exists()
        assert list(tmp_path.iterdir()) == []

        result = json.loads(
            await pipeline_handoff(
                operation="write_result",
                pipeline="commit",
                phase=f"../../../../{outside_name}",
                data='{"status":"passed"}',
            )
        )
        assert result["status"] == "error"
        assert not outside_path.exists()
        assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
class TestAsyncToThreadOffload:
    async def test_pipeline_handoff_offloads_dispatch_to_thread(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

        async def run_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        with patch(
            "cortex.tools.session.pipeline_handoff.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.side_effect = run_sync
            result = json.loads(
                await pipeline_handoff(operation="init", pipeline="commit")
            )
        assert result["status"] == "ok"
        assert mock_to_thread.call_count >= 1


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
