"""Detached pipeline execution for pre-commit checks.

Spawns the pipeline as a detached subprocess that survives MCP server
restarts. The MCP tool polls for the result file with heartbeat
progress notifications.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from enum import Enum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ValidationError

from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import ExecutionEnvironment
from cortex.core.models import OperationStatus
from cortex.tools.execution.pre_commit_process import (
    build_fix_worker_cmd,
    is_process_alive,
    poll_for_result,
    pre_commit_result_path,
    spawn_detached_process,
    spawn_detached_worker,
)
from cortex.tools.execution.session_paths import session_dir

logger = logging.getLogger(__name__)

_RESULT_FRESHNESS_SECONDS = 300  # 5 minutes

DETACHED_ENABLED = os.environ.get("CORTEX_DETACHED_PIPELINE", "1") != "0"


class DetachedResultStatus(str, Enum):
    """Status values persisted by detached worker result files."""

    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class DetachedJobStatus(str, Enum):
    """Status values returned when creating/reusing detached jobs."""

    STARTED = "started"
    COMPLETED = "completed"
    ALREADY_RUNNING = "already_running"
    ERROR = OperationStatus.ERROR.value


class DetachedResultEnvelope(BaseModel):
    """Parsed result envelope for detached worker output."""

    status: DetachedResultStatus
    completed_at: float | None = None
    pid: int | None = None
    result: dict[str, object] | None = None
    error: str | None = None


class DetachedJobInfo(BaseModel):
    """Structured detached-job response used by tool call sites."""

    job_id: str
    status: DetachedJobStatus
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True)


def compute_args_hash(
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown: bool,
) -> str:
    """Deterministic hash of call arguments for result file naming."""
    key = json.dumps(
        {
            "checks": sorted(checks),
            "timeout": timeout,
            "coverage": coverage_threshold,
            "strict": strict_mode,
            "markdown": include_markdown,
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def find_existing_result(
    project_root: Path,
    args_hash: str,
) -> dict[str, object] | None:
    """Check for a fresh, completed result file. Return data or None."""
    rp = pre_commit_result_path(session_dir(project_root), args_hash)
    if not rp.exists():
        return None
    try:
        data = json.loads(rp.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    try:
        parsed = DetachedResultEnvelope.model_validate(data)
    except ValidationError:
        return None
    status = parsed.status
    completed_at = parsed.completed_at

    if status == DetachedResultStatus.COMPLETED and isinstance(
        completed_at, (int, float)
    ):
        age = time.time() - completed_at
        if age < _RESULT_FRESHNESS_SECONDS:
            return data
        # Stale, remove
        rp.unlink(missing_ok=True)
        return None

    if status == DetachedResultStatus.RUNNING:
        if _has_live_worker(parsed):
            return data  # Worker is still running, caller should poll
        # Orphaned running status, remove
        rp.unlink(missing_ok=True)
        return None

    return data  # error status — return as-is


def _has_live_worker(parsed: DetachedResultEnvelope) -> bool:
    """Return True when a running envelope still points at a live pid."""
    pid = parsed.pid
    return isinstance(pid, int) and is_process_alive(pid)


def _cached_detached_result(
    existing: DetachedResultEnvelope | None, args_hash: str
) -> dict[str, object] | None:
    """Return cached result dict if existing is completed; else None."""
    if existing is None or existing.status != DetachedResultStatus.COMPLETED:
        return None
    if existing.result is None:
        return None
    logger.info("Returning cached detached result: %s", args_hash)
    return existing.result


def _build_job_id(
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
) -> str:
    return compute_args_hash(
        checks, timeout, coverage_threshold, strict_mode, include_markdown_lint
    )


def _interpret_existing_job(
    project_root: Path,
    args_hash: str,
) -> dict[str, object] | None:
    existing = find_existing_result(project_root, args_hash)
    if existing is not None:
        status = DetachedResultEnvelope.model_validate(existing).status
        if status == DetachedResultStatus.COMPLETED:
            return DetachedJobInfo(
                job_id=args_hash,
                status=DetachedJobStatus.COMPLETED,
            ).to_dict()
        if status == DetachedResultStatus.RUNNING:
            return DetachedJobInfo(
                job_id=args_hash,
                status=DetachedJobStatus.ALREADY_RUNNING,
            ).to_dict()
        return DetachedJobInfo(
            job_id=args_hash,
            status=DetachedJobStatus.ERROR,
            error=str(existing.get("error") or "Detached worker reported error"),
        ).to_dict()

    return None


def _spawn_new_job(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    args_hash: str,
    env: ExecutionEnvironment,
) -> dict[str, object]:
    _ = spawn_detached_worker(
        project_root,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
        args_hash,
        env=env,
    )
    return DetachedJobInfo(job_id=args_hash, status=DetachedJobStatus.STARTED).to_dict()


def _clear_cached_result(project_root: Path, args_hash: str) -> None:
    """Delete cached result file so a fresh worker is always spawned."""
    rp = pre_commit_result_path(session_dir(project_root), args_hash)
    rp.unlink(missing_ok=True)
    logger.info("force_fresh: cleared cached result for args_hash=%s", args_hash)


def clear_all_cached_results(project_root: Path) -> int:
    """Delete all pre-commit result cache files and return count removed.

    Call before re-running checks after code changes so stale cached
    worker results are not returned to the caller.
    """
    sd = session_dir(project_root)
    removed = 0
    for p in sd.glob("pre_commit_result_*.json"):
        p.unlink(missing_ok=True)
        removed += 1
    if removed:
        logger.info("clear_all_cached_results: removed %d result file(s)", removed)
    return removed


async def poll_job_to_completion(
    project_root: Path,
    job_id: str,
    timeout: float = 900.0,
) -> dict[str, object]:
    """Poll a detached job until completed/error, then return its inner result dict.

    Use after execute_pre_commit_checks returns {job_id, status} in detached mode
    to wait for the worker to finish and get the full result with output/errors fields.
    Returns the inner result on success, or an error dict on timeout/failure.
    """
    rp = pre_commit_result_path(session_dir(project_root), job_id)
    envelope = await poll_for_result(rp, ctx=None, timeout=timeout)
    if envelope.get("status") != "completed":
        return envelope
    inner = envelope.get("result")
    if isinstance(inner, dict):
        return cast(dict[str, object], inner)
    return {
        "status": OperationStatus.ERROR.value,
        "error": "Worker result missing 'result' key",
    }


def _compute_job_hash(
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
) -> str:
    return _build_job_id(
        checks, timeout, coverage_threshold, strict_mode, include_markdown_lint
    )


def start_pre_commit_job_impl(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    env: ExecutionEnvironment,
    force_fresh: bool = False,
) -> dict[str, object]:
    """Start or reuse a detached pre-commit job; return lightweight status."""
    args_hash = _compute_job_hash(
        checks, timeout, coverage_threshold, strict_mode, include_markdown_lint
    )
    if force_fresh:
        _clear_cached_result(project_root, args_hash)
    existing_result = _interpret_existing_job(project_root, args_hash)
    if existing_result is not None:
        return existing_result
    return _spawn_new_job(
        project_root,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
        args_hash,
        env=env,
    )


async def run_checks_detached(
    project_root: Path,
    checks: list[str],
    strict_mode: bool,
    timeout: int,
    coverage_threshold: float,
    ctx: MCPContext | None,  # noqa: ARG001 — retained for call-site compatibility
    env: ExecutionEnvironment,
) -> dict[str, object]:
    """Spawn detached worker and return immediately with lightweight status.

    Returns the inner result dict for cached hits (so execute_pre_commit_checks
    still delivers a full result without polling). For new or already-running
    jobs returns {job_id, status} so the MCP connection is not held open.
    Callers should poll with get_quality_job_status(job_id).
    """
    args_hash = compute_args_hash(
        checks, timeout, coverage_threshold, strict_mode, False
    )
    existing = find_existing_result(project_root, args_hash)
    existing_envelope = _validate_existing_envelope(existing)
    cached = _cached_detached_result(existing_envelope, args_hash)
    if cached is not None:
        return cached
    maybe_running = _running_job_response(existing_envelope, args_hash)
    if maybe_running is not None:
        return maybe_running
    _spawn_detached_checks_worker(
        project_root=project_root,
        checks=checks,
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        args_hash=args_hash,
        env=env,
    )
    return DetachedJobInfo(job_id=args_hash, status=DetachedJobStatus.STARTED).to_dict()


def _running_job_response(
    existing_envelope: DetachedResultEnvelope | None,
    args_hash: str,
) -> dict[str, object] | None:
    """Return already-running response when the cached envelope is in running state."""
    if (
        existing_envelope is None
        or existing_envelope.status != DetachedResultStatus.RUNNING
    ):
        return None
    logger.info(
        "Worker already running for args_hash=%s; returning already_running",
        args_hash,
    )
    return DetachedJobInfo(
        job_id=args_hash,
        status=DetachedJobStatus.ALREADY_RUNNING,
    ).to_dict()


def _spawn_detached_checks_worker(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    args_hash: str,
    env: ExecutionEnvironment,
) -> None:
    """Spawn a detached worker for the checks-only path."""
    _ = spawn_detached_worker(
        project_root,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        False,
        args_hash,
        env=env,
    )


def _validate_existing_envelope(
    existing: dict[str, object] | None,
) -> DetachedResultEnvelope | None:
    """Validate cached detached result envelope when present."""
    return (
        DetachedResultEnvelope.model_validate(existing)
        if existing is not None
        else None
    )


_FIX_RESULT_PREFIX = "pre_commit_fix_result_"


def fix_result_path(sd: Path, args_hash: str) -> Path:
    """Path to the JSON result file for a fix worker run."""
    return sd / f"{_FIX_RESULT_PREFIX}{args_hash}.json"


def fix_args_hash(include_markdown_fix: bool) -> str:
    """Deterministic hash for fix worker args."""
    key = json.dumps({"fix": True, "markdown": include_markdown_fix}, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def spawn_detached_fix_worker(
    project_root: Path,
    include_markdown_fix: bool,
    args_hash: str,
    env: ExecutionEnvironment,
) -> Path:
    """Spawn a detached fix worker subprocess. Returns result file path."""
    sd = session_dir(project_root)
    rp = fix_result_path(sd, args_hash)
    log_file = sd / f"pre_commit_fix_worker_{args_hash}.log"
    cmd = build_fix_worker_cmd(project_root, rp, include_markdown_fix)
    spawn_detached_process(cmd, log_file, project_root, env=env)
    logger.info("Spawned detached fix worker: hash=%s result=%s", args_hash, rp)
    return rp


def start_fix_job_impl(
    project_root: Path,
    include_markdown_fix: bool,
    env: ExecutionEnvironment,
) -> dict[str, object]:
    """Clear any prior fix result, spawn fresh fix worker, return {job_id, status}."""
    args_hash = fix_args_hash(include_markdown_fix)
    rp = fix_result_path(session_dir(project_root), args_hash)
    rp.unlink(missing_ok=True)
    _ = spawn_detached_fix_worker(
        project_root, include_markdown_fix, args_hash, env=env
    )
    return DetachedJobInfo(job_id=args_hash, status=DetachedJobStatus.STARTED).to_dict()


__all__ = [
    "DETACHED_ENABLED",
    "clear_all_cached_results",
    "compute_args_hash",
    "find_existing_result",
    "poll_for_result",
    "poll_job_to_completion",
    "run_checks_detached",
    "fix_args_hash",
    "fix_result_path",
    "spawn_detached_fix_worker",
    "spawn_detached_worker",
    "start_fix_job_impl",
    "start_pre_commit_job_impl",
]
