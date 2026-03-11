"""Tests for detached pre-commit status helpers and MCP tool."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from cortex.tools.execution.pre_commit_status import (
    get_last_pre_commit_status_impl,
    get_pre_commit_status_impl,
)
from cortex.tools.execution.pre_commit_tools import (
    get_last_pre_commit_status,
    get_pre_commit_job_status,
)


def _write_result(
    dir_path: Path,
    name: str,
    payload: dict[str, Any],
) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / name
    path.write_text(json.dumps(payload))
    return path


@pytest.mark.asyncio
async def test_no_runs_returns_no_runs_status(tmp_path: Path) -> None:
    """When there are no detached result files, status is 'no_runs'."""
    project_root = tmp_path
    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "no_runs"


@pytest.mark.asyncio
async def test_completed_result_summarized_correctly(tmp_path: Path) -> None:
    """Most recent completed result is summarized with checks and flags."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    now = time.time()
    payload: dict[str, Any] = {
        "version": 1,
        "status": "completed",
        "completed_at": now,
        "result": {
            "status": "success",
            "preflight_passed": True,
            "docs_phase_passed": False,
            "coverage": 0.95,
            "checks": ["tests"],
        },
    }
    _ = _write_result(session_dir, "pre_commit_result_abc123456789.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "completed"
    assert result["args_hash"] == "abc123456789"
    assert result["preflight_passed"] is True
    assert result["docs_phase_passed"] is False
    assert result["coverage"] == pytest.approx(0.95)
    assert result["completed_at"] == pytest.approx(now)
    assert result["checks"] == ["tests"]


@pytest.mark.asyncio
async def test_running_result_reports_running_status(tmp_path: Path) -> None:
    """Running result is reported as 'running'."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, Any] = {
        "version": 1,
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
    }
    _ = _write_result(session_dir, "pre_commit_result_zzz999.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "running"
    assert result["args_hash"] == "zzz999"


@pytest.mark.asyncio
async def test_error_result_reports_error_status(tmp_path: Path) -> None:
    """Error result is summarized with error message."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, Any] = {
        "version": 1,
        "status": "error",
        "error": "Worker process died",
    }
    _ = _write_result(session_dir, "pre_commit_result_err123.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "error"
    assert result["args_hash"] == "err123"
    assert "Worker process died" in str(result.get("error", ""))


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_returns_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP tool get_last_pre_commit_status returns a ModelDict."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, Any] = {
        "version": 1,
        "status": "completed",
        "completed_at": time.time(),
        "result": {
            "status": "success",
            "preflight_passed": True,
            "coverage": 0.9,
            "checks": ["tests"],
        },
    }
    _ = _write_result(session_dir, "pre_commit_result_tooltest.json", payload)

    async def _fake_root(_ctx: object | None) -> str:
        return str(project_root)

    from cortex.tools.execution import pre_commit_tools as tools_mod

    monkeypatch.setattr(
        tools_mod, "get_or_resolve_project_root", _fake_root, raising=True
    )
    result = await get_last_pre_commit_status(ctx=None)
    assert isinstance(result, dict)
    model_result = result  # type: ModelDict
    assert model_result["status"] == "completed"
    assert model_result["args_hash"] == "pre_commit_result_tooltest".replace(
        "pre_commit_result_", ""
    )


@pytest.mark.asyncio
async def test_get_pre_commit_status_impl_no_runs(tmp_path: Path) -> None:
    """get_pre_commit_status_impl returns no_runs when job_id has no result file."""
    project_root = tmp_path
    result = await get_pre_commit_status_impl(
        project_root=project_root,
        job_id="missing123",
        ctx=None,
    )
    assert result["status"] == "no_runs"
    assert result["args_hash"] == "missing123"


@pytest.mark.asyncio
async def test_get_pre_commit_job_status_mcp_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP tool get_pre_commit_job_status returns a ModelDict for specific job."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    now = time.time()
    payload: dict[str, Any] = {
        "version": 1,
        "status": "completed",
        "completed_at": now,
        "result": {
            "status": "success",
            "preflight_passed": True,
            "coverage": 0.9,
            "checks": ["tests"],
        },
    }
    _ = _write_result(session_dir, "pre_commit_result_job123.json", payload)

    async def _fake_root(_ctx: object | None) -> str:
        return str(project_root)

    from cortex.tools.execution import pre_commit_tools as tools_mod

    monkeypatch.setattr(
        tools_mod, "get_or_resolve_project_root", _fake_root, raising=True
    )
    result = await get_pre_commit_job_status(job_id="job123", ctx=None)
    assert isinstance(result, dict)
    assert result["status"] == "completed"
    assert result["args_hash"] == "job123"
