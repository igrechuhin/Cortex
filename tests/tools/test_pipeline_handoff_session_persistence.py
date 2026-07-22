"""Regression tests: pipeline_handoff phase-state must survive a session-id
env var loss (e.g. an MCP server process restart during a long-running
subagent call).

Root cause: ``get_session_id()`` cached the session id only in
``os.environ``. If the MCP server process backing the orchestrator's
connection was recycled between two ``pipeline_handoff`` calls, the next
call ran in a fresh process with no ``CORTEX_SESSION_ID``, minted a
brand-new random id, and silently resolved to an empty pipeline directory —
orphaning every phase already written under the old session id.

The fix persists the session id to an on-disk marker
(``.cortex/.session/.active-session.json``) so a fresh process recovers the
same identity instead of diverging. See
``cortex.tools.session.pipeline_handoff_session``.
"""

import json
import os
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)

_ENV_KEY = "CORTEX_SESSION_ID"


def _reset_session_env() -> None:
    """Undo get_session_id()'s direct (non-monkeypatch) os.environ mutation.

    ``get_session_id`` writes ``os.environ[_ENV_KEY]`` directly rather than
    through ``monkeypatch``, so pytest's automatic fixture teardown cannot
    revert it. Each test calls this explicitly on both ends.
    """
    _ = os.environ.pop(_ENV_KEY, None)


def _simulate_process_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a fresh MCP server process: no cached session id in-process."""
    monkeypatch.delenv(_ENV_KEY, raising=False)


async def _write_phase(pipeline: str, phase: str, data: str) -> dict[str, object]:
    raw = await pipeline_handoff(
        operation="write", pipeline=pipeline, phase=phase, data=data
    )
    return cast(dict[str, object], json.loads(raw))


def _pipeline_state(result: dict[str, object]) -> dict[str, object]:
    """Narrow ``result["pipeline_state"]`` to a typed dict."""
    state = result["pipeline_state"]
    assert isinstance(state, dict)
    return cast(dict[str, object], state)


def _phases(result: dict[str, object]) -> dict[str, object]:
    """Narrow ``result["pipeline_state"]["phases"]`` to a typed dict."""
    phases = _pipeline_state(result)["phases"]
    assert isinstance(phases, dict)
    return cast(dict[str, object], phases)


@pytest.mark.asyncio
async def test_phases_survive_session_env_loss_between_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write(select) -> simulated restart -> write(code) -> both phases visible."""
    _reset_session_env()
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    try:
        init_r = json.loads(
            await pipeline_handoff(operation="init", pipeline="implement")
        )
        assert init_r["status"] == "ok"

        select_r = await _write_phase("implement", "select", '{"status": "complete"}')
        assert "select" in _phases(select_r)

        # AI: simulate the long-subagent-call gap: the orchestrator's own
        # MCP server process is recycled and loses its in-memory session cache.
        _simulate_process_restart(monkeypatch)

        code_r = await _write_phase("implement", "code", '{"status": "complete"}')
        phases = _phases(code_r)
        assert "select" in phases, f"select lost: {phases}"
        assert "code" in phases
    finally:
        _reset_session_env()


@pytest.mark.asyncio
async def test_session_id_recovered_after_env_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh process (env var gone) resolves the same session id as before."""
    _reset_session_env()
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    try:
        init_r = json.loads(
            await pipeline_handoff(operation="init", pipeline="implement")
        )
        original_session_id = init_r["session_id"]

        _simulate_process_restart(monkeypatch)

        status_r = await _write_phase("implement", "select", '{"status": "complete"}')
        recovered_id = _pipeline_state(status_r)["session_id"]
        assert recovered_id == original_session_id
    finally:
        _reset_session_env()


@pytest.mark.asyncio
async def test_explicit_env_var_still_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit CORTEX_SESSION_ID (e.g. test isolation) wins over the marker."""
    _reset_session_env()
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv(_ENV_KEY, "explicit-override")
    try:
        init_r = json.loads(
            await pipeline_handoff(operation="init", pipeline="implement")
        )
        assert init_r["session_id"] == "explicit-override"
    finally:
        _reset_session_env()
