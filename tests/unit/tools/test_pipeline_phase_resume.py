"""Phase status tracking and resume capability tests for pipeline_handoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from cortex.tools.session.pipeline_handoff_io import (
    detect_incomplete_state,
    pipeline_dir,
)
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


def _should_skip_phase(status_map: dict[str, str], phase: str) -> bool:
    return status_map.get(phase) == "completed"


async def _phase_statuses(pipeline: str) -> dict[str, str]:
    result = json.loads(await pipeline_handoff(operation="status", pipeline=pipeline))
    return result["phases"]


@pytest.mark.asyncio
async def test_mark_running_sets_running_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    result = json.loads(
        await pipeline_handoff(
            operation="mark_running",
            pipeline="commit",
            phase="checks",
        )
    )
    assert result["status"] == "ok"

    rfile = Path(result["result_file"])
    payload = json.loads(rfile.read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert "started_at" in payload

    statuses = await _phase_statuses("commit")
    assert statuses["checks"] == "running"


@pytest.mark.asyncio
async def test_write_sets_completed_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="mark_running",
        pipeline="commit",
        phase="checks",
    )
    result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="commit",
            phase="checks",
            data='{"status":"passed","coverage":0.94}',
        )
    )
    assert result["status"] == "ok"

    rfile = Path(result["result_file"])
    payload = json.loads(rfile.read_text(encoding="utf-8"))
    assert payload["phase_status"] == "completed"
    assert "completed_at" in payload
    assert payload["coverage"] == 0.94

    statuses = await _phase_statuses("commit")
    assert statuses["checks"] == "completed"


@pytest.mark.asyncio
async def test_status_query_returns_all_phases_including_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="preflight",
        data='{"status":"passed"}',
    )
    _ = await pipeline_handoff(
        operation="mark_running",
        pipeline="commit",
        phase="checks",
    )
    statuses = await _phase_statuses("commit")
    assert statuses["preflight"] == "completed"
    assert statuses["checks"] == "running"


@pytest.mark.asyncio
async def test_resume_simulation_skips_completed_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="checks",
        data='{"status":"passed","coverage":0.92}',
    )
    statuses = await _phase_statuses("commit")
    assert statuses["checks"] == "completed"
    assert _should_skip_phase(statuses, "checks") is True


@pytest.mark.asyncio
async def test_failed_phase_is_not_skipped_and_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="fix",
        phase="quality",
        data='{"status":"failed","error":"lint"}',
    )
    statuses_before = await _phase_statuses("fix")
    assert statuses_before["quality"] == "failed"
    assert _should_skip_phase(statuses_before, "quality") is False

    _ = await pipeline_handoff(
        operation="mark_running", pipeline="fix", phase="quality"
    )
    _ = await pipeline_handoff(
        operation="write",
        pipeline="fix",
        phase="quality",
        data='{"status":"passed"}',
    )
    statuses_after = await _phase_statuses("fix")
    assert statuses_after["quality"] == "completed"
    assert _should_skip_phase(statuses_after, "quality") is True


@pytest.mark.asyncio
async def test_mark_running_writes_to_event_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    result = json.loads(
        await pipeline_handoff(
            operation="mark_running", pipeline="commit", phase="checks"
        )
    )
    log_result = json.loads(
        await pipeline_handoff(operation="read_log", pipeline="commit")
    )
    assert any(e["operation"] == "mark_running" for e in log_result["entries"])
    assert any(e["phase"] == "checks" for e in log_result["entries"])

    # mark_running creates the result file with status=running, so detect_incomplete_state
    # (which checks for write events with no result file) correctly does not flag it.
    pdir = Path(result["result_file"]).parent
    incomplete = detect_incomplete_state(pdir)
    assert "checks" not in incomplete


@pytest.mark.asyncio
async def test_completed_phase_not_flagged_as_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="checks",
        data='{"status":"passed"}',
    )
    incomplete = detect_incomplete_state(pipeline_dir(tmp_path, "commit"))
    assert incomplete == []
