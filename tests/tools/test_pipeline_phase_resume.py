"""Phase resume behavior tests for pipeline_handoff status tracking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


def _should_skip_phase(status_map: dict[str, str], phase: str) -> bool:
    """Mirror prompt-level resume decision: skip only completed phases."""
    return status_map.get(phase) == "completed"


async def _phase_status(pipeline: str) -> dict[str, str]:
    status_result = json.loads(
        await pipeline_handoff(operation="status", pipeline=pipeline)
    )
    return status_result["phases"]


async def _retry_failed_quality_phase() -> dict[str, str]:
    running_result = json.loads(
        await pipeline_handoff(
            operation="mark_running",
            pipeline="fix",
            phase="quality",
        )
    )
    assert running_result["status"] == "ok"
    assert (await _phase_status("fix"))["quality"] == "running"
    write_result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="fix",
            phase="quality",
            data={"status": "passed"},
        )
    )
    assert write_result["status"] == "ok"
    return await _phase_status("fix")


@pytest.mark.asyncio
async def test_resume_simulation_skips_completed_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Completed phase is detected and would be skipped by prompt logic."""
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="checks",
        data={"status": "passed", "coverage": 0.92},
    )

    status_result = json.loads(
        await pipeline_handoff(operation="status", pipeline="commit")
    )
    statuses = status_result["phases"]
    assert statuses["checks"] == "completed"
    assert _should_skip_phase(statuses, "checks") is True


@pytest.mark.asyncio
async def test_failed_phase_retry_simulation_marks_running_then_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed phase should be retried and transitioned running -> completed."""
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="fix",
        phase="quality",
        data={"status": "failed", "error": "lint violation"},
    )

    status_before = await _phase_status("fix")
    assert status_before["quality"] == "failed"
    assert _should_skip_phase(status_before, "quality") is False

    status_after = await _retry_failed_quality_phase()
    assert status_after["quality"] == "completed"
    assert _should_skip_phase(status_after, "quality") is True
