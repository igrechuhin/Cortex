"""Event log and crash-recovery tests for pipeline_handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


def _pipeline_session_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cortex" / ".session"


async def _seed_commit_phase_statuses() -> dict[str, str]:
    _ = await pipeline_handoff(
        operation="mark_running",
        pipeline="commit",
        phase="checks",
    )
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="docs",
        data={"status": "passed"},
    )
    _ = await pipeline_handoff(
        operation="write_task",
        pipeline="commit",
        phase="validate",
        data={"started": True},
    )
    _ = await pipeline_handoff(
        operation="write",
        pipeline="commit",
        phase="final-gate",
        data={"status": "failed"},
    )
    status_result = json.loads(
        await pipeline_handoff(operation="status", pipeline="commit")
    )
    return cast(dict[str, str], status_result["phases"])


@pytest.mark.asyncio
async def test_write_appends_event_before_result_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="code",
            data={"status": "passed", "tests_added": 2},
        )
    )

    assert result["status"] == "ok"
    result_file = Path(result["result_file"])
    pipeline_log = result_file.parent / "pipeline.log"
    assert pipeline_log.exists()
    lines = [
        line for line in pipeline_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["phase"] == "code"
    assert entry["operation"] == "write"
    assert entry["data_keys"] == ["status", "tests_added"]
    assert entry["status"] == "completed"
    assert "timestamp" in entry
    assert result_file.exists()


@pytest.mark.asyncio
async def test_read_log_returns_structured_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="select",
        data={"status": "complete", "selected_step": "step-1"},
    )
    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="code",
        data={"status": "passed"},
    )

    log_result = json.loads(
        await pipeline_handoff(operation="read_log", pipeline="implement")
    )

    assert log_result["status"] == "ok"
    entries = log_result["entries"]
    assert len(entries) == 2
    assert entries[0]["phase"] == "select"
    assert entries[1]["phase"] == "code"
    assert entries[0]["status"] == "completed"
    assert entries[1]["status"] == "completed"
    assert all("timestamp" in entry for entry in entries)


@pytest.mark.asyncio
async def test_mark_running_writes_running_status_and_logs_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    result = json.loads(
        await pipeline_handoff(
            operation="mark_running",
            pipeline="implement",
            phase="code",
        )
    )

    assert result["status"] == "ok"
    payload = json.loads(Path(result["result_file"]).read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert payload["phase_status"] == "running"
    assert "started_at" in payload

    log_result = json.loads(
        await pipeline_handoff(operation="read_log", pipeline="implement")
    )
    assert log_result["entries"][0]["operation"] == "mark_running"
    assert log_result["entries"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_status_reports_running_completed_failed_and_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    phases = await _seed_commit_phase_statuses()
    assert phases["checks"] == "running"
    assert phases["docs"] == "completed"
    assert phases["final-gate"] == "failed"
    assert phases["validate"] == "pending"


@pytest.mark.asyncio
async def test_session_start_detects_crash_recovery_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    write_result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="implement",
            phase="code",
            data={"status": "passed"},
        )
    )
    result_file = Path(write_result["result_file"])
    result_file.unlink()

    from cortex.tools.session.pipeline_handoff_io import detect_incomplete_state

    incomplete = detect_incomplete_state(result_file.parent)
    assert incomplete == ["code"]


@pytest.mark.asyncio
async def test_session_start_ignores_completed_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="code",
        data={"status": "passed"},
    )

    from cortex.tools.session.pipeline_handoff_io import (
        detect_incomplete_state,
        pipeline_dir,
    )

    incomplete = detect_incomplete_state(pipeline_dir(tmp_path, "implement"))
    assert incomplete == []


@pytest.mark.asyncio
async def test_write_returns_error_when_event_log_append_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    with patch(
        "cortex.tools.session.pipeline_handoff_io._append_event_log",
        side_effect=OSError("permission denied"),
    ):
        result = json.loads(
            await pipeline_handoff(
                operation="write",
                pipeline="implement",
                phase="code",
                data={"status": "failed"},
            )
        )

    assert result["status"] == "error"
    assert "permission denied" in result["error"]
    session_root = _pipeline_session_dir(tmp_path)
    assert not any(session_root.glob("**/code-result.json"))


def test_extract_routing_keys_strips_routing_from_json_payload() -> None:
    from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

    routing, cleaned_data = extract_routing_keys(
        json.dumps(
            {
                "operation": "write",
                "phase": "quality",
                "pipeline": "fix",
                "status": "passed",
                "iterations": 1,
            }
        )
    )

    assert routing == {"op": "write", "phase": "quality", "pipeline": "fix"}
    assert cleaned_data is not None
    parsed = json.loads(cleaned_data)
    assert parsed == {"status": "passed", "iterations": 1}


def test_extract_routing_keys_keeps_non_json_input_unchanged() -> None:
    from cortex.tools.session.pipeline_handoff_io import extract_routing_keys

    raw = "not-json"
    routing, cleaned_data = extract_routing_keys(raw)

    assert routing == {}
    assert cleaned_data == raw


@pytest.mark.asyncio
async def test_write_accepts_non_object_payload_as_data_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="fix",
            phase="coverage",
            data='["gap-a", "gap-b"]',
        )
    )

    assert result["status"] == "ok"
    result_file = Path(result["result_file"])
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["data"] == ["gap-a", "gap-b"]
    assert payload["phase"] == "coverage"


@pytest.mark.asyncio
async def test_read_task_returns_pipeline_state_fallback_when_task_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    _ = await pipeline_handoff(
        operation="write",
        pipeline="fix",
        phase="coverage",
        data={"status": "failed", "iterations": 1},
    )
    response = json.loads(
        await pipeline_handoff(operation="read", pipeline="fix", phase="quality")
    )

    assert response["status"] == "not_found"
    assert response["phase"] == "quality"
    assert response["pipeline"] == "fix"
    assert "pipeline_state" in response
    assert "coverage" in response["pipeline_state"]["phases"]
