"""Tests for detached pre-commit execution helpers.

Focus on:
- Cached result reuse for completed runs.
- Fast-fail behavior when a worker is already running for the same args_hash.
- Phase-based job start (phase="A"/"B"/"full" resolved to canonical checks list).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from cortex.tools.execution.pre_commit_detached import (
    compute_args_hash,
    find_existing_result,
    run_checks_detached,
    start_pre_commit_job_impl,
)
from cortex.tools.execution.pre_commit_phase_dispatch import (
    _PHASE_A_CHECKS,
    _PHASE_B_CHECKS,
    PreCommitPhase,
    phase_to_checks,
)


def _write_result_file(
    project_root: Path,
    args_hash: str,
    payload: dict[str, object],
) -> Path:
    session_dir = project_root / ".cortex" / ".session"
    session_dir.mkdir(parents=True, exist_ok=True)
    result_path = session_dir / f"pre_commit_result_{args_hash}.json"
    result_path.write_text(json.dumps(payload))
    return result_path


@pytest.mark.asyncio
async def test_cached_completed_result_is_reused(tmp_path: Path) -> None:
    """Completed result for same args_hash is returned without spawning worker."""
    project_root = tmp_path
    args_hash = compute_args_hash(
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown=False,
    )
    payload: dict[str, object] = {
        "version": 1,
        "status": "completed",
        "completed_at": time.time(),
        "result": {
            "status": "success",
            "preflight_passed": True,
            "checks": ["tests"],
        },
    }
    _write_result_file(project_root, args_hash, payload)

    existing = find_existing_result(project_root, args_hash)
    assert existing is not None
    assert existing.get("status") == "completed"

    result = await run_checks_detached(
        project_root=project_root,
        checks=["tests"],
        strict_mode=False,
        timeout=300,
        coverage_threshold=0.9,
        ctx=None,
    )
    # Inner "result" dict should be returned directly
    assert result["status"] == "success"
    assert result["preflight_passed"] is True
    assert result["checks"] == ["tests"]


@pytest.mark.asyncio
async def test_running_status_returns_fast_error_for_second_call(
    tmp_path: Path,
) -> None:
    """Second call while a worker is running returns clear non-retryable error."""
    project_root = tmp_path
    args_hash = compute_args_hash(
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown=False,
    )
    running_payload: dict[str, object] = {
        "version": 1,
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
    }
    _write_result_file(project_root, args_hash, running_payload)

    existing = find_existing_result(project_root, args_hash)
    assert existing is not None
    assert existing.get("status") == "running"

    result = await run_checks_detached(
        project_root=project_root,
        checks=["tests"],
        strict_mode=False,
        timeout=300,
        coverage_threshold=0.9,
        ctx=None,
    )
    assert result["status"] == "error"
    assert "already running for this configuration" in str(result["error"])


def test_start_pre_commit_job_impl_reuses_completed_result(tmp_path: Path) -> None:
    """start_pre_commit_job_impl returns completed when fresh result exists."""
    project_root = tmp_path
    args_hash = compute_args_hash(
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown=False,
    )
    payload: dict[str, object] = {
        "version": 1,
        "status": "completed",
        "completed_at": time.time(),
        "result": {"status": "success"},
    }
    _write_result_file(project_root, args_hash, payload)

    result = start_pre_commit_job_impl(
        project_root=project_root,
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown_lint=False,
    )
    assert result["job_id"] == args_hash
    assert result["status"] == "completed"


def test_start_pre_commit_job_impl_reports_already_running(tmp_path: Path) -> None:
    """start_pre_commit_job_impl returns already_running when status is running."""
    project_root = tmp_path
    args_hash = compute_args_hash(
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown=False,
    )
    running_payload: dict[str, object] = {
        "version": 1,
        "status": "running",
        "pid": os.getpid(),
        "started_at": time.time(),
    }
    _write_result_file(project_root, args_hash, running_payload)

    result = start_pre_commit_job_impl(
        project_root=project_root,
        checks=["tests"],
        timeout=300,
        coverage_threshold=0.9,
        strict_mode=False,
        include_markdown_lint=False,
    )
    assert result["job_id"] == args_hash
    assert result["status"] == "already_running"


def test_phase_to_checks_phase_a_returns_canonical_list() -> None:
    """phase_to_checks(A) returns all Phase A check names."""
    checks = phase_to_checks(PreCommitPhase.A)
    assert isinstance(checks, list)
    assert len(checks) == len(_PHASE_A_CHECKS)
    assert set(checks) == set(_PHASE_A_CHECKS)
    # Required checks must be present
    for required in ("fix_errors", "format", "type_check", "quality", "tests"):
        assert required in checks, f"Missing required check: {required}"


def test_phase_to_checks_phase_b_returns_canonical_list() -> None:
    """phase_to_checks(B) returns Phase B check names."""
    checks = phase_to_checks(PreCommitPhase.B)
    assert isinstance(checks, list)
    assert len(checks) == len(_PHASE_B_CHECKS)
    assert set(checks) == set(_PHASE_B_CHECKS)


def test_phase_to_checks_full_combines_a_and_b() -> None:
    """phase_to_checks(FULL) returns combined A + B check names."""
    checks = phase_to_checks(PreCommitPhase.FULL)
    expected = list(_PHASE_A_CHECKS + _PHASE_B_CHECKS)
    assert checks == expected
    # Full must be a superset of both A and B
    a_checks = phase_to_checks(PreCommitPhase.A)
    b_checks = phase_to_checks(PreCommitPhase.B)
    for c in a_checks + b_checks:
        assert c in checks, f"Full phase missing check: {c}"
