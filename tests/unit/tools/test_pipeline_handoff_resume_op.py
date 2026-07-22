"""Dispatcher-level tests for pipeline_handoff(operation="resume")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


@pytest.mark.asyncio
async def test_resume_without_recorded_run_reports_fresh_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="resume", pipeline="implement")
    )

    # Assert
    assert result["status"] == "ok"
    assert result["resumable"] is False
    assert "no experience store" in result["reason"]


@pytest.mark.asyncio
async def test_resume_after_committed_phase_returns_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: one committed phase, then a simulated crash.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    monkeypatch.delenv("CORTEX_EXPERIENCE_RECORDING", raising=False)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="select",
        data='{"status":"passed"}',
    )

    # Act
    result = json.loads(
        await pipeline_handoff(operation="resume", pipeline="implement")
    )

    # Assert
    assert result["status"] == "ok"
    assert result["resumable"] is True
    assert result["completed_phases"] == ["select"]
    assert result["frontier_phase"] == "select"
