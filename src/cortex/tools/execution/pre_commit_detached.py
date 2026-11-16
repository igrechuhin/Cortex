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
from collections.abc import Mapping
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import ExecutionEnvironment
from cortex.core.models import OperationStatus
from cortex.tools.execution.pre_commit_ownership import (
    current_owner,
    owned_request_id,
)
from cortex.tools.execution.pre_commit_process import (
    build_fix_worker_cmd,
    is_process_alive,
    poll_for_result,
    pre_commit_result_path,
    publish_started_worker,
    reap_detached_workers,
    spawn_detached_process,
    spawn_detached_worker,
)
from cortex.tools.execution.pre_commit_workspace import (
    WorkspaceBusy,
    busy_response,
    process_group_alive,
    workspace_lease,
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
    pid: int | None = Field(default=None, gt=0, strict=True)
    result: dict[str, object] | None = None
    error: str | None = None
    owner: str | None = None


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
    test_filter: str | None = None,
) -> str:
    """Deterministic hash of call arguments for result file naming."""
    key = json.dumps(
        {
            "checks": sorted(checks),
            "timeout": timeout,
            "coverage": coverage_threshold,
            "strict": strict_mode,
            "markdown": include_markdown,
            **({"test_filter": test_filter} if test_filter is not None else {}),
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
    if parsed.owner != current_owner():
        return None
    status = parsed.status
    completed_at = parsed.completed_at

    if status == DetachedResultStatus.COMPLETED and isinstance(
        completed_at, (int, float)
    ):
        age = time.time() - completed_at
        if age < _RESULT_FRESHNESS_SECONDS:
            return data
        # AI: Reads never evict a worker's evidence; startup cleans under its lease.
        return None

    if status == DetachedResultStatus.RUNNING:
        if _has_live_worker(parsed):
            return data  # Worker is still running, caller should poll
        # The workspace lease, including crash evidence, decides safe reuse.
        return None

    return data  # error status — return as-is


def _has_live_worker(parsed: DetachedResultEnvelope) -> bool:
    """Return True when a running envelope still points at a live pid."""
    pid = parsed.pid
    return isinstance(pid, int) and (is_process_alive(pid) or process_group_alive(pid))


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
    test_filter: str | None = None,
) -> str:
    return compute_args_hash(
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
        test_filter,
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
    quality_gate: bool = False,
    test_filter: str | None = None,
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
        quality_gate=quality_gate,
        test_filter=test_filter,
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
        try:
            parsed = DetachedResultEnvelope.model_validate_json(p.read_text())
        except (OSError, ValidationError):
            continue
        if (
            parsed.owner != current_owner()
            or parsed.status == DetachedResultStatus.RUNNING
        ):
            continue
        p.unlink(missing_ok=True)
        removed += 1
    if removed:
        logger.info("clear_all_cached_results: removed %d result file(s)", removed)
    return removed


def find_running_job(
    project_root: Path, owned_result_path: Path | None = None
) -> dict[str, object] | None:
    """Find a live check or fix worker before another workspace operation."""
    reap_detached_workers()
    for result_path in session_dir(project_root).glob("pre_commit_*result_*.json"):
        job_id = result_path.stem.rsplit("_", 1)[-1]
        try:
            existing = DetachedResultEnvelope.model_validate_json(
                result_path.read_text()
            )
        except (OSError, ValidationError):
            continue
        if existing.status == DetachedResultStatus.RUNNING and _has_live_worker(
            existing
        ):
            if result_path != owned_result_path or existing.owner != current_owner():
                return busy_response()
            return {
                "status": "running",
                "job_id": job_id,
                "result_file": str(result_path),
                "preflight_passed": False,
                "message": "Workspace checks or fixes are running; retry after they finish.",
            }
    return None


def _compute_job_hash(
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    test_filter: str | None = None,
) -> str:
    return owned_request_id(
        _build_job_id(
            checks,
            timeout,
            coverage_threshold,
            strict_mode,
            include_markdown_lint,
            test_filter,
        )
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
    quality_gate: bool = False,
    test_filter: str | None = None,
) -> dict[str, object]:
    """Start or reuse a detached pre-commit job; return lightweight status."""
    # AI: One spec tuple feeds identity and spawn so the two argument lists cannot drift.
    spec = (checks, timeout, coverage_threshold, strict_mode, include_markdown_lint)
    args_hash = _compute_job_hash(*spec, test_filter)
    result_path = pre_commit_result_path(session_dir(project_root), args_hash)
    try:
        with workspace_lease(project_root, args_hash):
            return _start_under_lease(
                project_root,
                spec,
                args_hash,
                env,
                force_fresh,
                quality_gate,
                test_filter,
            )
    except WorkspaceBusy:
        return _start_response(
            find_running_job(project_root, result_path) or busy_response()
        )


def _start_under_lease(
    root: Path,
    spec: tuple[list[str], int, float, bool, bool],
    args_hash: str,
    env: ExecutionEnvironment,
    force_fresh: bool,
    quality_gate: bool,
    test_filter: str | None,
) -> dict[str, object]:
    existing = _existing_or_busy_job(root, args_hash, force_fresh)
    if existing is not None:
        return existing
    return _spawn_new_job(
        root,
        *spec,
        args_hash,
        env=env,
        quality_gate=quality_gate,
        test_filter=test_filter,
    )


def _start_response(active: dict[str, object]) -> dict[str, object]:
    if active.get("busy") is True:
        return active
    return {**active, "status": DetachedJobStatus.ALREADY_RUNNING.value}


def _existing_or_busy_job(
    project_root: Path, args_hash: str, force_fresh: bool
) -> dict[str, object] | None:
    existing = _interpret_existing_job(project_root, args_hash)
    if existing is not None and (
        not force_fresh or existing.get("status") == "already_running"
    ):
        return existing
    active = find_running_job(
        project_root, pre_commit_result_path(session_dir(project_root), args_hash)
    )
    if active is not None:
        return active
    _clear_cached_result(project_root, args_hash)
    if force_fresh:
        from cortex.tools.execution.pre_commit_fingerprint_store import (
            clear_phase_a_fingerprint,
        )

        clear_phase_a_fingerprint(project_root)
    return None


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

    Returns the inner result dict for cached hits (so run_quality_gate() still
    delivers a full result without polling). For new or already-running jobs
    returns {job_id, status} so the MCP connection is not held open; callers
    poll with poll_for_result(job_id).
    """
    args_hash = _compute_job_hash(
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
    return start_pre_commit_job_impl(
        project_root, checks, timeout, coverage_threshold, strict_mode, False, env
    )


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
    return owned_request_id(hashlib.sha256(key.encode()).hexdigest()[:12])


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
    pid = spawn_detached_process(cmd, log_file, project_root, env=env)
    publish_started_worker(rp, pid, quality_gate=False)
    logger.info("Spawned detached fix worker: hash=%s result=%s", args_hash, rp)
    return rp


def start_fix_job_impl(
    project_root: Path,
    include_markdown_fix: bool,
    env: ExecutionEnvironment,
) -> dict[str, object]:
    """Start a fresh fix worker only when no workspace worker is running."""
    args_hash = fix_args_hash(include_markdown_fix)
    rp = fix_result_path(session_dir(project_root), args_hash)
    active = find_running_job(project_root, rp)
    if active is not None:
        return active
    try:
        with workspace_lease(project_root, args_hash):
            active = find_running_job(project_root, rp)
            if active is not None:
                return active
            _ = clear_all_cached_results(project_root)
            rp.unlink(missing_ok=True)
            _ = spawn_detached_fix_worker(
                project_root, include_markdown_fix, args_hash, env=env
            )
            return DetachedJobInfo(
                job_id=args_hash, status=DetachedJobStatus.STARTED
            ).to_dict()
    except WorkspaceBusy:
        return find_running_job(project_root, rp) or busy_response()


def invalid_job_handle(
    job: Mapping[str, object], result_path: Path, prefix: str, worker: str
) -> dict[str, object] | None:
    """Error result when the worker's job_id does not name `result_path`.

    Returns None when the handle is valid. A mismatch means the worker would
    deliver a different job's envelope, so it must not be polled.
    """
    job_id = job.get("job_id")
    if isinstance(job_id, str) and job_id == result_path.stem.removeprefix(prefix):
        return None
    return {
        "status": "error",
        "error": f"{worker} worker did not return a valid job handle.",
    }


__all__ = [
    "DETACHED_ENABLED",
    "clear_all_cached_results",
    "compute_args_hash",
    "find_existing_result",
    "poll_for_result",
    "run_checks_detached",
    "fix_args_hash",
    "fix_result_path",
    "spawn_detached_fix_worker",
    "spawn_detached_worker",
    "invalid_job_handle",
    "start_fix_job_impl",
    "start_pre_commit_job_impl",
]
