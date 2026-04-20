"""Event log coverage for pipeline_handoff crash-recovery primitives."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.models import SessionStartResult
from cortex.tools.session.pipeline_handoff import pipeline_handoff
from cortex.tools.session.pipeline_handoff_io import detect_incomplete_state
from cortex.tools.session.start_tools import session_start_impl
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)
from tests.tools.session_start_fixtures import managers_for_phase54_session_start


@pytest.mark.asyncio
async def test_write_result_appends_event_log_before_state_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    result = json.loads(
        await pipeline_handoff(
            operation="write",
            pipeline="commit",
            phase="checks",
            data='{"status":"passed","coverage":0.91}',
        )
    )
    assert result["status"] == "ok"
    log_file = Path(result["result_file"]).parent / "pipeline.log"
    entries = [
        json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()
    ]
    assert len(entries) == 1
    assert entries[0]["phase"] == "checks"
    assert entries[0]["operation"] == "write"
    assert set(entries[0]["data_keys"]) == {"coverage", "status"}


@pytest.mark.asyncio
async def test_read_log_returns_structured_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="select",
        data='{"status":"complete","selected_step":"x"}',
    )
    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="code",
        data='{"status":"passed","tests_added":2}',
    )
    log_data = json.loads(
        await pipeline_handoff(operation="read_log", pipeline="implement")
    )
    assert log_data["status"] == "ok"
    assert len(log_data["entries"]) == 2
    assert log_data["entries"][0]["operation"] == "write"
    assert log_data["entries"][1]["phase"] == "code"


def test_detect_incomplete_state_flags_logged_write(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir(parents=True)
    log_file = pipeline_dir / "pipeline.log"
    _ = log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "phase": "checks",
                        "timestamp": "2026-04-20T10:00:00",
                        "operation": "write",
                        "data_keys": ["status"],
                    }
                ),
                json.dumps(
                    {
                        "phase": "docs",
                        "timestamp": "2026-04-20T10:00:01",
                        "operation": "read",
                        "data_keys": [],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    assert detect_incomplete_state(pipeline_dir) == ["checks"]


@pytest.mark.asyncio
async def test_session_start_reports_incomplete_pipelines(tmp_path: Path) -> None:
    managers = await managers_for_phase54_session_start(tmp_path)
    session_pipeline_dir = tmp_path / ".cortex" / ".session" / "abc123" / "implement"
    session_pipeline_dir.mkdir(parents=True, exist_ok=True)
    _ = (session_pipeline_dir / "pipeline.log").write_text(
        json.dumps(
            {
                "phase": "code",
                "timestamp": "2026-04-20T10:00:02",
                "operation": "write",
                "data_keys": ["status"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with patch(
        "cortex.tools.session.health.get_mcp_health_status",
        new_callable=AsyncMock,
        return_value=(True, None),
    ):
        result = await session_start_impl(
            None,
            tmp_path,
            managers,
        )
    assert isinstance(result, SessionStartResult)
    assert result.status == "success"
    assert "abc123/implement" in result.brief.incomplete_pipelines


@pytest.mark.asyncio
async def test_session_start_ignores_completed_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = await pipeline_handoff(
        operation="write",
        pipeline="implement",
        phase="code",
        data='{"status":"passed"}',
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
                data='{"status":"failed"}',
            )
        )
    assert result["status"] == "error"
    assert "permission denied" in result["error"]
