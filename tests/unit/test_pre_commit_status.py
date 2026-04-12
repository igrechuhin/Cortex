"""Tests for detached pre-commit status helpers and MCP tool."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from cortex.tools.execution.pre_commit_status import (
    get_last_pre_commit_status_impl,
    get_pre_commit_status_impl,
)
from cortex.tools.execution.pre_commit_tools import (
    get_last_pre_commit_status,
    get_quality_job_status,
)


def _json_number(value: object) -> float:
    """Narrow MCP summary numeric fields (JsonValue) for strict type checks."""
    assert isinstance(value, (int, float))
    return float(value)


def _write_result(
    dir_path: Path,
    name: str,
    payload: dict[str, object],
) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / name
    _ = path.write_text(json.dumps(payload))
    return path


def _completed_result_file_payload(
    now: float,
    *,
    preflight_passed: bool,
    docs_phase_passed: bool,
    result_status: str,
    coverage: float,
    results: dict[str, object],
) -> dict[str, object]:
    return {
        "version": 1,
        "status": "completed",
        "completed_at": now,
        "result": {
            "status": result_status,
            "preflight_passed": preflight_passed,
            "docs_phase_passed": docs_phase_passed,
            "coverage": coverage,
            "checks": ["tests"],
            "results": results,
        },
    }


_COMPLETED_ALL_CHECKS_OK: dict[str, object] = {
    "tests": {"success": True},
    "format": {"success": True},
    "type_check": {"success": True},
    "quality": {"success": True},
}


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
    payload = _completed_result_file_payload(
        now,
        preflight_passed=True,
        docs_phase_passed=False,
        result_status="success",
        coverage=0.95,
        results=_COMPLETED_ALL_CHECKS_OK,
    )
    _ = _write_result(session_dir, "pre_commit_result_abc123456789.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "completed"
    assert result["args_hash"] == "abc123456789"
    assert result["preflight_passed"] is True
    assert result["docs_phase_passed"] is False
    assert abs(_json_number(result["coverage"]) - 0.95) < 1e-9
    assert abs(_json_number(result["completed_at"]) - now) < 1e-6
    assert result["checks"] == ["tests"]
    # Per-category summary and log path should be present
    assert result["checks_summary"] == {
        "tests": True,
        "format": True,
        "type_check": True,
        "quality": True,
    }
    assert isinstance(result.get("log_path"), str)


@pytest.mark.asyncio
async def test_running_result_reports_running_status(tmp_path: Path) -> None:
    """Running result is reported as 'running'."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, object] = {
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
    payload: dict[str, object] = {
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
async def test_running_result_older_than_max_age_reports_timeout(
    tmp_path: Path,
) -> None:
    """Long-running job beyond max age is summarized as timeout."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    # Create a running payload with a started_at far in the past so age > _MAX_RUNNING_AGE_SECONDS
    past = time.time() - 2000.0
    payload: dict[str, object] = {
        "version": 1,
        "status": "running",
        "pid": os.getpid(),
        "started_at": past,
    }
    _ = _write_result(session_dir, "pre_commit_result_timeout1.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "timeout"
    assert result["args_hash"] == "timeout1"
    assert "maximum allowed duration" in str(result.get("error", ""))
    assert isinstance(result.get("log_path"), str)


@pytest.mark.asyncio
async def test_explicit_timeout_status_in_result_file_is_preserved(
    tmp_path: Path,
) -> None:
    """Result files marked with status 'timeout' are surfaced as timeout."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    now = time.time()
    payload: dict[str, object] = {
        "version": 1,
        "status": "timeout",
        "completed_at": now,
        "error": "Timeout waiting for worker result after 900s",
    }
    _ = _write_result(session_dir, "pre_commit_result_timeout2.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "timeout"
    assert result["args_hash"] == "timeout2"
    assert "Timeout waiting for worker result" in str(result.get("error", ""))
    assert abs(_json_number(result["completed_at"]) - now) < 1e-6


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_returns_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP tool get_last_pre_commit_status returns a ModelDict."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, object] = {
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
    assert result["status"] == "completed"
    assert result["args_hash"] == "pre_commit_result_tooltest".replace(
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
async def test_get_pre_commit_status_impl_completed_failure_flags(
    tmp_path: Path,
) -> None:
    """Completed job with failing checks is summarized with failure flags."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    now = time.time()
    payload = _completed_result_file_payload(
        now,
        preflight_passed=False,
        docs_phase_passed=False,
        result_status="failed",
        coverage=0.75,
        results={"tests": {"success": False}},
    )
    _ = _write_result(session_dir, "pre_commit_result_failjob.json", payload)

    result = await get_pre_commit_status_impl(
        project_root=project_root,
        job_id="failjob",
        ctx=None,
    )
    assert result["status"] == "completed"
    assert result["args_hash"] == "failjob"
    assert result["preflight_passed"] is False
    assert result["docs_phase_passed"] is False
    assert abs(_json_number(result["coverage"]) - 0.75) < 1e-9
    assert result["checks"] == ["tests"]
    # checks_summary should reflect failing tests
    assert result["checks_summary"] == {"tests": False}


@pytest.mark.asyncio
async def test_get_quality_job_status_mcp_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP tool get_quality_job_status returns a ModelDict for specific job."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    now = time.time()
    payload: dict[str, object] = {
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
    result = await get_quality_job_status(job_id="job123", ctx=None)
    assert isinstance(result, dict)
    assert result["status"] == "completed"
    assert result["args_hash"] == "job123"


@pytest.mark.asyncio
async def test_queued_result_reports_queued_status(tmp_path: Path) -> None:
    """Queued result is reported as 'queued'."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, object] = {
        "version": 1,
        "status": "queued",
    }
    _ = _write_result(session_dir, "pre_commit_result_queue1.json", payload)

    result = await get_last_pre_commit_status_impl(project_root, ctx=None)
    assert result["status"] == "queued"
    assert result["args_hash"] == "queue1"


@pytest.mark.asyncio
async def test_get_pre_commit_status_impl_queued(tmp_path: Path) -> None:
    """get_pre_commit_status_impl returns queued when job_id has queued result."""
    project_root = tmp_path
    session_dir = project_root / ".cortex" / ".session"
    payload: dict[str, object] = {
        "version": 1,
        "status": "queued",
    }
    _ = _write_result(session_dir, "pre_commit_result_queue2.json", payload)

    result = await get_pre_commit_status_impl(
        project_root=project_root,
        job_id="queue2",
        ctx=None,
    )
    assert result["status"] == "queued"
    assert result["args_hash"] == "queue2"
