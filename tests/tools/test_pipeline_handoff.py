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
            await pipeline_handoff(operation="read_state", pipeline="fix")
        )
        assert result["status"] == "not_found"
        assert "fix" in result["message"]

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
            await pipeline_handoff(operation="clear", pipeline="review")
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
# Token validation & async-to-thread offload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTokenValidation:
    async def test_init_rejects_pipeline_path_traversal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _resolve_root(monkeypatch, tmp_path)

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
        _resolve_root(monkeypatch, tmp_path)

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
        _resolve_root(monkeypatch, tmp_path)

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


# ---------------------------------------------------------------------------
# is_commit_pipeline_active (Fix 1)
# ---------------------------------------------------------------------------


class TestIsCommitPipelineActive:
    def test_returns_false_before_init(self, tmp_path: Path) -> None:
        from cortex.core.pipeline_state import is_commit_pipeline_active

        assert is_commit_pipeline_active(tmp_path) is False

    @pytest.mark.asyncio
    async def test_returns_true_after_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cortex.core.pipeline_state import is_commit_pipeline_active

        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="commit")
        assert is_commit_pipeline_active(tmp_path) is True

    @pytest.mark.asyncio
    async def test_returns_false_after_clear(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cortex.core.pipeline_state import is_commit_pipeline_active

        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="commit")
        await pipeline_handoff(operation="clear", pipeline="commit")
        assert is_commit_pipeline_active(tmp_path) is False


# ---------------------------------------------------------------------------
# Stale pipeline auto-expiry on re-init (Fix 5)
# ---------------------------------------------------------------------------


class TestStalePipelineExpiry:
    @pytest.mark.asyncio
    async def test_stale_pipeline_is_replaced_on_reinit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pipeline.json older than TTL is removed and recreated on next init."""
        import json as _json
        from datetime import datetime, timedelta

        from cortex.tools.session.pipeline_handoff_io import (
            PIPELINE_TTL_SECONDS,
            pipeline_dir,
            state_path,
        )

        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="commit")
        pdir = pipeline_dir(tmp_path, "commit")
        sfile = state_path(pdir)
        state = _json.loads(sfile.read_text())
        stale_time = datetime.now() - timedelta(seconds=PIPELINE_TTL_SECONDS + 10)
        state["started_at"] = stale_time.isoformat(timespec="seconds")
        _ = sfile.write_text(_json.dumps(state))
        _ = (pdir / "sentinel.txt").write_text("old")
        await pipeline_handoff(operation="init", pipeline="commit")
        assert not (pdir / "sentinel.txt").exists()

    @pytest.mark.asyncio
    async def test_fresh_pipeline_is_preserved_on_reinit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recently created pipeline.json is preserved on a second init call."""
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir

        _resolve_root(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="commit")
        pdir = pipeline_dir(tmp_path, "commit")
        _ = (pdir / "sentinel.txt").write_text("new")
        await pipeline_handoff(operation="init", pipeline="commit")
        assert (pdir / "sentinel.txt").exists()


# ---------------------------------------------------------------------------
# Zero-arg / Cursor arg-stripping fallback (_resolve_zero_arg_defaults)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestZeroArgFallback:
    """Verify that pipeline_handoff recovers from Cursor's arg-stripping.

    Cursor sends {} for every MCP tool call, leaving operation="read_state"
    and pipeline="default".  The tool must read session config and use
    whatever the orchestrator wrote there.
    """

    def _setup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Mock both root-resolution paths needed by the tool and session_config."""
        _resolve_root(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "cortex.core.session_config.get_current_project_root",
            lambda: tmp_path,
        )

    def _write_session_config(self, tmp_path: Path, config: dict[str, object]) -> None:
        session_dir = tmp_path / ".cortex" / ".session"
        session_dir.mkdir(parents=True, exist_ok=True)
        _ = (session_dir / "current-task.json").write_text(
            json.dumps(config), encoding="utf-8"
        )

    async def test_zero_arg_init_uses_session_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero-arg call runs 'init' for 'commit' when session config says so."""
        self._setup(monkeypatch, tmp_path)
        self._write_session_config(
            tmp_path, {"operation": "init", "pipeline": "commit"}
        )
        result = json.loads(await pipeline_handoff())
        assert result["status"] == "ok"
        assert "pipeline_dir" in result

    async def test_zero_arg_read_uses_session_config_pipeline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero-arg read returns state for the pipeline named in session config."""
        self._setup(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="implement")
        self._write_session_config(
            tmp_path, {"operation": "read", "pipeline": "implement"}
        )
        result = json.loads(await pipeline_handoff())
        assert result.get("pipeline") == "implement"

    async def test_zero_arg_preserves_explicit_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When explicit args differ from defaults, session config is NOT used."""
        self._setup(monkeypatch, tmp_path)
        self._write_session_config(
            tmp_path, {"operation": "init", "pipeline": "commit"}
        )
        # Passing an explicit pipeline name — should NOT fall back to session config
        await pipeline_handoff(operation="init", pipeline="implement")
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir, state_path

        pdir = pipeline_dir(tmp_path, "implement")
        assert state_path(pdir).exists()

    async def test_zero_arg_no_session_config_returns_read_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero-arg with no session config falls through to read_state/default."""
        self._setup(monkeypatch, tmp_path)
        # No session config file — returns not_found for the default pipeline
        result = json.loads(await pipeline_handoff())
        assert result.get("status") == "not_found"


# ---------------------------------------------------------------------------
# extract_routing_keys() — unit tests
# ---------------------------------------------------------------------------


class TestExtractRoutingKeys:
    """Unit tests for the extract_routing_keys helper."""

    def test_extracts_all_three_routing_keys(self) -> None:
        from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

        data = json.dumps(
            {
                "_op": "write",
                "_phase": "select",
                "_pipeline": "implement",
                "status": "ok",
            }
        )
        routing, cleaned = extract_routing_keys(data)
        assert routing == {"op": "write", "phase": "select", "pipeline": "implement"}
        assert json.loads(cleaned or "") == {"status": "ok"}

    def test_no_routing_keys_returns_unchanged(self) -> None:
        from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

        data = json.dumps({"status": "complete", "coverage": 0.91})
        routing, cleaned = extract_routing_keys(data)
        assert routing == {}
        assert cleaned == data

    def test_none_data_returns_empty(self) -> None:
        from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

        routing, cleaned = extract_routing_keys(None)
        assert routing == {}
        assert cleaned is None

    def test_non_json_data_returns_unchanged(self) -> None:
        from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

        routing, cleaned = extract_routing_keys("not json at all")
        assert routing == {}
        assert cleaned == "not json at all"

    def test_routing_only_data_returns_none_cleaned(self) -> None:
        from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

        data = json.dumps({"_op": "clear", "_pipeline": "implement"})
        routing, cleaned = extract_routing_keys(data)
        assert routing["op"] == "clear"
        assert cleaned is None  # no payload keys remain


# ---------------------------------------------------------------------------
# Routing keys in data — integration tests via pipeline_handoff()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoutingKeysInData:
    """Verify pipeline_handoff extracts _op/_phase/_pipeline from data payload.

    This is the Cursor protocol: agent writes one JSON blob to current-task.json
    containing both routing and payload instead of a separate routing write.
    """

    def _setup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _resolve_root(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "cortex.core.session_config.get_current_project_root",
            lambda: tmp_path,
        )

    def _write_session_config(self, tmp_path: Path, config: dict[str, object]) -> None:
        session_dir = tmp_path / ".cortex" / ".session"
        session_dir.mkdir(parents=True, exist_ok=True)
        _ = (session_dir / "current-task.json").write_text(
            json.dumps(config), encoding="utf-8"
        )

    async def test_routing_keys_in_data_trigger_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_op/_phase/_pipeline in data drive the write operation."""
        self._setup(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="implement")
        self._write_session_config(
            tmp_path,
            {
                "data": json.dumps(
                    {
                        "_op": "write",
                        "_phase": "select",
                        "_pipeline": "implement",
                        "status": "complete",
                        "selected_step": "step-1",
                    }
                )
            },
        )
        result = json.loads(
            await pipeline_handoff(
                data={
                    "_op": "write",
                    "_phase": "select",
                    "_pipeline": "implement",
                    "status": "complete",
                    "selected_step": "step-1",
                }
            )
        )
        assert (result["status"], result["phase"]) == ("ok", "select")

    async def test_routing_keys_stripped_from_stored_payload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Routing keys _op/_phase/_pipeline are not stored in the phase file."""
        self._setup(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="implement")
        await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="select",
            data={
                "_op": "write",
                "_phase": "select",
                "_pipeline": "implement",
                "status": "complete",
            },
        )
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir, result_path

        pdir = pipeline_dir(tmp_path, "implement")
        stored = json.loads(result_path(pdir, "select").read_text())
        assert "_op" not in stored
        assert "_phase" not in stored
        assert "_pipeline" not in stored
        assert stored["status"] == "complete"

    async def test_write_response_includes_pipeline_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """write response includes pipeline_state so gate checks don't need a read."""
        self._setup(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="implement")
        result = json.loads(
            await pipeline_handoff(
                operation="write",
                pipeline="implement",
                phase="select",
                data='{"status": "complete", "selected_step": "step-1"}',
            )
        )
        assert "pipeline_state" in result
        phases = result["pipeline_state"]["phases"]
        assert phases["select"]["status"] == "complete"

    async def test_gate_check_from_write_response(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After write, agent can gate-check phases.select.status without a read call."""
        self._setup(monkeypatch, tmp_path)
        await pipeline_handoff(operation="init", pipeline="implement")
        write_result = json.loads(
            await pipeline_handoff(
                operation="write",
                pipeline="implement",
                phase="select",
                data='{"status": "complete"}',
            )
        )
        # Gate check: no separate pipeline_handoff(operation="read") needed
        assert (
            write_result["pipeline_state"]["phases"]["select"]["status"] == "complete"
        )
