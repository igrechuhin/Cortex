"""Extended tests for pipeline_handoff (round-trip, coercion, routing)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)

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
    await _run_commit_round_trip_preflight_phase()
    await _run_commit_round_trip_checks_phase()
    await _assert_commit_round_trip_final_state()
    clear_r = json.loads(await pipeline_handoff(operation="clear", pipeline="commit"))
    assert clear_r["status"] == "ok"


async def _run_commit_round_trip_preflight_phase() -> None:
    init_r = json.loads(await pipeline_handoff(operation="init", pipeline="commit"))
    assert init_r["status"] == "ok"
    _ = await pipeline_handoff(
        operation="write_task",
        pipeline="commit",
        phase="preflight",
        data='{"requested_by": "user"}',
    )
    task = json.loads(
        await pipeline_handoff(
            operation="read_task", pipeline="commit", phase="preflight"
        )
    )
    assert task["requested_by"] == "user"
    _ = await pipeline_handoff(
        operation="write_result",
        pipeline="commit",
        phase="preflight",
        data='{"status": "complete", "snapshot_ref": "deadbeef", "rules_loaded": true}',
    )


async def _run_commit_round_trip_checks_phase() -> None:
    state = json.loads(
        await pipeline_handoff(operation="read_state", pipeline="commit")
    )
    snapshot_ref = state["phases"]["preflight"]["snapshot_ref"]
    assert snapshot_ref == "deadbeef"
    _ = await pipeline_handoff(
        operation="write_task",
        pipeline="commit",
        phase="checks",
        data=json.dumps({"snapshot_ref": snapshot_ref, "coverage_threshold": 0.9}),
    )
    checks_task = json.loads(
        await pipeline_handoff(operation="read_task", pipeline="commit", phase="checks")
    )
    assert checks_task["snapshot_ref"] == "deadbeef"
    _ = await pipeline_handoff(
        operation="write_result",
        pipeline="commit",
        phase="checks",
        data='{"status": "passed", "coverage": 0.94, "fix_iterations": 0}',
    )


async def _assert_commit_round_trip_final_state() -> None:
    final_state = json.loads(
        await pipeline_handoff(operation="read_state", pipeline="commit")
    )
    assert final_state["phases"]["preflight"]["status"] == "complete"
    assert final_state["phases"]["checks"]["status"] == "passed"
    assert final_state["phases"]["checks"]["coverage"] == 0.94


# ---------------------------------------------------------------------------
# Bug fixes: dict data + read_task fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDataCoercion:
    """data can be a JSON string OR a native dict — both must be accepted."""

    async def test_write_result_accepts_dict_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Some MCP clients send data as a dict; tool must serialise it, not reject it."""
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        # Pass a native Python dict (simulates what some MCP client LLMs send)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
class TestSnapshotRollback:
    async def test_snapshot_operation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        target = tmp_path / "tracked.txt"
        _ = target.write_text("before", encoding="utf-8")

        result = json.loads(
            await pipeline_handoff(
                operation="snapshot",
                pipeline="implement",
                data={"paths": [str(target)]},
            )
        )

        assert result["status"] == "ok"
        assert isinstance(result["snapshot_id"], str)
        assert result["snapshot_id"]

    async def test_rollback_operation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        target = tmp_path / "tracked.txt"
        _ = target.write_text("before", encoding="utf-8")
        snapshot = json.loads(
            await pipeline_handoff(
                operation="snapshot",
                pipeline="implement",
                data={"paths": [str(target)]},
            )
        )
        _ = target.write_text("after", encoding="utf-8")

        rollback = json.loads(
            await pipeline_handoff(
                operation="rollback",
                pipeline="implement",
                data={"snapshot_id": snapshot["snapshot_id"]},
            )
        )

        assert rollback["status"] == "ok"
        assert rollback["snapshot_id"] == snapshot["snapshot_id"]
        assert rollback["restored"] == [str(target)]
        assert target.read_text(encoding="utf-8") == "before"

    async def test_snapshot_without_paths_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        result = json.loads(
            await pipeline_handoff(
                operation="snapshot",
                pipeline="implement",
            )
        )
        assert result["status"] == "error"
        assert "paths is required" in result["error"]


@pytest.mark.asyncio
class TestReadTaskFallback:
    """read_task with no task file falls back to pipeline state."""

    async def test_read_task_not_found_includes_pipeline_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no task file exists, pipeline state from prior phases is returned."""
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        # Write a result for a prior phase
        _ = await pipeline_handoff(
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
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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

        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        assert is_commit_pipeline_active(tmp_path) is True

    @pytest.mark.asyncio
    async def test_returns_false_after_clear(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cortex.core.pipeline_state import is_commit_pipeline_active

        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        _ = await pipeline_handoff(operation="clear", pipeline="commit")
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

        from cortex.tools.session.pipeline_handoff_clock import PIPELINE_TTL_SECONDS
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir, state_path

        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        pdir = pipeline_dir(tmp_path, "commit")
        sfile = state_path(pdir)
        state = _json.loads(sfile.read_text())
        stale_time = datetime.now() - timedelta(seconds=PIPELINE_TTL_SECONDS + 10)
        state["started_at"] = stale_time.isoformat(timespec="seconds")
        _ = sfile.write_text(_json.dumps(state))
        _ = (pdir / "sentinel.txt").write_text("old")
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        assert not (pdir / "sentinel.txt").exists()

    @pytest.mark.asyncio
    async def test_fresh_pipeline_is_preserved_on_reinit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recently created pipeline.json is preserved on a second init call."""
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir

        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        pdir = pipeline_dir(tmp_path, "commit")
        _ = (pdir / "sentinel.txt").write_text("new")
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        assert (pdir / "sentinel.txt").exists()

    @pytest.mark.asyncio
    async def test_reinit_mid_run_preserves_prior_phases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: a second init call must not wipe already-written phases.

        Reproduces the reported bug: orchestrator writes "select", a long
        subagent gap intervenes and something re-triggers `operation="init"`
        for the same live (non-stale) pipeline, orchestrator writes "code" —
        the read afterwards must still show both phases, not just "code".
        """
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="implement")
        _ = await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="select",
            data='{"status": "complete"}',
        )
        # AI: simulates a redundant init call happening mid-run (e.g. a
        # retried tool call or stale routing state) between two phase writes.
        _ = await pipeline_handoff(operation="init", pipeline="implement")
        _ = await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="code",
            data='{"status": "passed"}',
        )
        result = json.loads(
            await pipeline_handoff(operation="read", pipeline="implement")
        )
        assert "select" in result["phases"]
        assert "code" in result["phases"]

    @pytest.mark.asyncio
    async def test_reinit_merges_data_without_dropping_phases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second init with extra data merges it but keeps existing phases."""
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        _ = await pipeline_handoff(
            operation="write",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete"}',
        )
        result = json.loads(
            await pipeline_handoff(
                operation="init", pipeline="commit", data='{"run_id": "r1"}'
            )
        )
        pdir = Path(result["pipeline_dir"])
        state = json.loads((pdir / "pipeline.json").read_text())
        assert state["run_id"] == "r1"
        assert "preflight" in state["phases"]

    @pytest.mark.asyncio
    async def test_stale_reinit_still_resets_phases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A genuinely stale pipeline still gets a fresh phases={} on re-init."""
        import json as _json
        from datetime import datetime, timedelta

        from cortex.tools.session.pipeline_handoff_clock import PIPELINE_TTL_SECONDS
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir, state_path

        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        _ = await pipeline_handoff(
            operation="write",
            pipeline="commit",
            phase="preflight",
            data='{"status": "complete"}',
        )
        pdir = pipeline_dir(tmp_path, "commit")
        sfile = state_path(pdir)
        state = _json.loads(sfile.read_text())
        stale_time = datetime.now() - timedelta(seconds=PIPELINE_TTL_SECONDS + 10)
        state["started_at"] = stale_time.isoformat(timespec="seconds")
        _ = sfile.write_text(_json.dumps(state))
        _ = await pipeline_handoff(operation="init", pipeline="commit")
        refreshed = _json.loads(sfile.read_text())
        assert refreshed["phases"] == {}


# ---------------------------------------------------------------------------
# Zero-arg / MCP-client arg-stripping fallback (_resolve_zero_arg_defaults)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestZeroArgFallback:
    """Verify that pipeline_handoff recovers from an MCP client's arg-stripping.

    Some MCP clients send {} for every MCP tool call, leaving operation="read_state"
    and pipeline="default".  The tool must read session config and use
    whatever the orchestrator wrote there.
    """

    def _setup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Mock both root-resolution paths needed by the tool and session_config."""
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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
        _ = await pipeline_handoff(operation="init", pipeline="implement")
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
        _ = await pipeline_handoff(operation="init", pipeline="implement")
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
                "operation": "write",
                "phase": "select",
                "pipeline": "implement",
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

        data = json.dumps({"operation": "clear", "pipeline": "implement"})
        routing, cleaned = extract_routing_keys(data)
        assert routing["op"] == "clear"
        assert cleaned is None  # no payload keys remain


# ---------------------------------------------------------------------------
# Routing keys in data — integration tests via pipeline_handoff()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoutingKeysInData:
    """Verify pipeline_handoff extracts operation/phase/pipeline from data payload.

    This is the zero-arg-friendly protocol: agent writes one JSON blob to current-task.json
    containing both routing and payload instead of a separate routing write.
    """

    def _setup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
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

    @staticmethod
    def _routing_payload() -> dict[str, object]:
        return {
            "operation": "write",
            "phase": "select",
            "pipeline": "implement",
            "status": "complete",
            "selected_step": "step-1",
        }

    async def test_routing_keys_in_data_trigger_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """operation/phase/pipeline in data drive the write operation."""
        self._setup(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="implement")
        payload = self._routing_payload()
        self._write_session_config(tmp_path, {"data": json.dumps(payload)})
        result = json.loads(await pipeline_handoff(data=payload))
        assert (result["status"], result["phase"]) == ("ok", "select")

    async def test_routing_keys_stripped_from_stored_payload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Routing keys operation/phase/pipeline are not stored in the phase file."""
        self._setup(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="implement")
        _ = await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="select",
            data={
                "operation": "write",
                "phase": "select",
                "pipeline": "implement",
                "status": "complete",
            },
        )
        from cortex.tools.session.pipeline_handoff_io import pipeline_dir, result_path

        pdir = pipeline_dir(tmp_path, "implement")
        stored = json.loads(result_path(pdir, "select").read_text())
        assert "operation" not in stored
        assert "pipeline" not in stored
        assert stored["status"] == "complete"

    async def test_write_response_includes_pipeline_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """write response includes pipeline_state so gate checks don't need a read."""
        self._setup(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="implement")
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
        _ = await pipeline_handoff(operation="init", pipeline="implement")
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


def test_pipeline_handoff_docstring_mentions_agent_internal_brevity() -> None:
    doc = pipeline_handoff.__doc__
    assert doc is not None
    assert "Agent-Internal Communication" in doc
    assert "context" in doc
    assert "summary" in doc
