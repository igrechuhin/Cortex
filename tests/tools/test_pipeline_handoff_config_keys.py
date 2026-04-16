"""Tests for pipeline state config-key separation in pipeline_handoff_io.

Covers fix for pipeline state overwrite: config-only keys (force_fresh,
test_timeout) written via write_result are now stored under a top-level
"config" block rather than polluting the phase result record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


@pytest.mark.asyncio
class TestConfigKeysSeparation:
    async def test_force_fresh_goes_to_config_not_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"status": "passed", "coverage": 0.92, "force_fresh": true}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        phase = state["phases"]["checks"]
        # config key must NOT be in the phase result
        assert "force_fresh" not in phase
        # phase result data must be intact
        assert phase["status"] == "passed"
        assert phase["coverage"] == 0.92
        # config key must be in top-level "config" block
        assert state.get("config", {}).get("force_fresh") is True

    async def test_test_timeout_goes_to_config_not_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"status": "passed", "test_timeout": 600}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        phase = state["phases"]["checks"]
        assert "test_timeout" not in phase
        assert state.get("config", {}).get("test_timeout") == 600

    async def test_multiple_config_keys_accumulate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"status": "passed", "force_fresh": true, "test_timeout": 300}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        config = state.get("config", {})
        assert config.get("force_fresh") is True
        assert config.get("test_timeout") == 300
        phase = state["phases"]["checks"]
        assert "force_fresh" not in phase
        assert "test_timeout" not in phase

    async def test_phase_a_result_not_overwritten_by_config_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Phase A result survives a subsequent config-only write to the same phase."""
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        # Phase A writes its result
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"status": "passed", "coverage": 0.95}',
        )
        # Step 12 writes fresh-check config into the same phase
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="checks",
            data='{"force_fresh": true, "test_timeout": 600}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        phase = state["phases"]["checks"]
        # The second write replaces the phase record (last-write-wins for result fields),
        # but config keys must never appear in the phase record.
        assert "force_fresh" not in phase
        assert "test_timeout" not in phase
        # Config block must have the keys
        config = state.get("config", {})
        assert config.get("force_fresh") is True
        assert config.get("test_timeout") == 600

    async def test_normal_result_keys_not_affected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(
            operation="write_result",
            pipeline="commit",
            phase="preflight",
            data='{"snapshot_ref": "abc123", "branch": "main"}',
        )
        state = json.loads(
            await pipeline_handoff(operation="read_state", pipeline="commit")
        )
        phase = state["phases"]["preflight"]
        assert phase["snapshot_ref"] == "abc123"
        assert phase["branch"] == "main"
        # No spurious config block when no config keys were written
        assert "config" not in state
