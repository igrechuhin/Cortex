"""Detached pipeline execution for pre-commit checks.

Spawns the pipeline as a detached subprocess that survives MCP server
restarts. The MCP tool polls for the result file with heartbeat
progress notifications.
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext, report_progress_safe

logger = logging.getLogger(__name__)

_RESULT_FRESHNESS_SECONDS = 300  # 5 minutes
_POLL_INTERVAL_SECONDS = 2
_HEARTBEAT_TOTAL = 500

DETACHED_ENABLED = os.environ.get("CORTEX_DETACHED_PIPELINE", "1") != "0"


def _session_dir(project_root: Path) -> Path:
    """Return session directory for result files."""
    d = project_root / ".cortex" / ".session"
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def _result_path(session_dir: Path, args_hash: str) -> Path:
    return session_dir / f"pre_commit_result_{args_hash}.json"


def _log_path(session_dir: Path, args_hash: str) -> Path:
    return session_dir / f"pre_commit_worker_{args_hash}.log"


def _is_process_alive(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def find_existing_result(
    project_root: Path,
    args_hash: str,
) -> dict[str, object] | None:
    """Check for a fresh, completed result file. Return data or None."""
    rp = _result_path(_session_dir(project_root), args_hash)
    if not rp.exists():
        return None
    try:
        data = json.loads(rp.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    status = data.get("status")
    completed_at = data.get("completed_at")

    if status == "completed" and isinstance(completed_at, (int, float)):
        age = time.time() - completed_at
        if age < _RESULT_FRESHNESS_SECONDS:
            return data
        # Stale, remove
        rp.unlink(missing_ok=True)
        return None

    if status == "running":
        pid = data.get("pid")
        if isinstance(pid, int) and _is_process_alive(pid):
            return data  # Worker is still running, caller should poll
        # Orphaned running status, remove
        rp.unlink(missing_ok=True)
        return None

    return data  # error status — return as-is


def _build_worker_cmd(
    project_root: Path,
    rp: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
) -> list[str]:
    """Build argv for the detached worker subprocess."""
    cmd = [
        sys.executable,
        "-m",
        "cortex.tools.execution.pre_commit_worker",
        "--result-file",
        str(rp),
        "--project-root",
        str(project_root),
        "--timeout",
        str(timeout),
        "--coverage-threshold",
        str(coverage_threshold),
    ]
    if checks:
        cmd.extend(["--checks"] + checks)
    if strict_mode:
        cmd.append("--strict")
    if include_markdown_lint:
        cmd.append("--include-markdown-lint")
    return cmd


def _spawn_detached_process(cmd: list[str], log_file: Path, project_root: Path) -> None:
    """Start detached subprocess writing stdout/stderr to log_file."""
    with open(log_file, "w") as lf:
        _ = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=lf,
            stderr=lf,
            cwd=str(project_root),
            start_new_session=True,
        )


def spawn_detached_worker(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    args_hash: str,
) -> Path:
    """Spawn a detached worker subprocess. Returns result file path."""
    sd = _session_dir(project_root)
    rp = _result_path(sd, args_hash)
    log_file = _log_path(sd, args_hash)
    cmd = _build_worker_cmd(
        project_root,
        rp,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
    )
    _spawn_detached_process(cmd, log_file, project_root)
    logger.info("Spawned detached worker: hash=%s result=%s", args_hash, rp)
    return rp


def _read_result_file(
    result_path: Path,
) -> tuple[dict[str, object] | None, str | None]:
    """Read result JSON if present. Returns (data, status) or (None, None)."""
    if not result_path.exists():
        return None, None
    try:
        data = json.loads(result_path.read_text())
        return cast(dict[str, object], data), data.get("status")
    except (json.JSONDecodeError, OSError):
        return None, None


async def poll_for_result(
    result_path: Path,
    ctx: MCPContext | None,
    timeout: float = 900.0,
) -> dict[str, object]:
    """Poll for result file completion, sending heartbeat progress."""
    deadline = time.time() + timeout
    tick = 0
    while time.time() < deadline:
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        tick += 1
        if ctx is not None:
            await report_progress_safe(
                ctx, float(min(tick, _HEARTBEAT_TOTAL)), float(_HEARTBEAT_TOTAL)
            )
        data, status = _read_result_file(result_path)
        if data is None:
            continue
        if status == "completed" or status == "error":
            return data
        if status == "running":
            pid = data.get("pid")
            if isinstance(pid, int) and not _is_process_alive(pid):
                return _worker_died_error(pid)
    return _timeout_error(timeout)


def _worker_died_error(pid: int) -> dict[str, object]:
    """Build error dict when worker process died."""
    return {
        "version": 1,
        "status": "error",
        "error": f"Worker process {pid} died without writing result",
    }


def _timeout_error(timeout: float) -> dict[str, object]:
    """Build error dict for poll timeout."""
    return {
        "version": 1,
        "status": "timeout",
        "error": f"Timeout waiting for worker result after {timeout}s",
    }


def _cached_detached_result(
    existing: dict[str, object] | None, args_hash: str
) -> dict[str, object] | None:
    """Return cached result dict if existing is completed; else None."""
    if existing is None:
        return None
    if existing.get("status") != "completed":
        return None
    raw = existing.get("result")
    if not isinstance(raw, dict):
        return None
    logger.info("Returning cached detached result: %s", args_hash)
    out: dict[str, object] = cast(dict[str, object], raw)
    return out


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
        status = existing.get("status")
        if status == "completed":
            return {
                "job_id": args_hash,
                "status": "completed",
            }
        if status == "running":
            return {
                "job_id": args_hash,
                "status": "already_running",
            }
        return {
            "job_id": args_hash,
            "status": "error",
            "error": str(existing.get("error") or "Detached worker reported error"),
        }

    return None


def _spawn_new_job(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    args_hash: str,
) -> dict[str, object]:
    _ = spawn_detached_worker(
        project_root,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
        args_hash,
    )
    return {
        "job_id": args_hash,
        "status": "started",
    }


def _clear_cached_result(project_root: Path, args_hash: str) -> None:
    """Delete cached result file so a fresh worker is always spawned."""
    rp = _result_path(_session_dir(project_root), args_hash)
    rp.unlink(missing_ok=True)
    logger.info("force_fresh: cleared cached result for args_hash=%s", args_hash)


def start_pre_commit_job_impl(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    force_fresh: bool = False,
) -> dict[str, object]:
    """Start or reuse a detached pre-commit job; return lightweight status."""
    args_hash = _build_job_id(
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
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
    )


def _interpret_poll_data(data: dict[str, object]) -> dict[str, object]:
    """Map poll result to final result dict."""
    status = data.get("status")
    if status == "completed":
        result = data.get("result")
        if isinstance(result, dict):
            return cast(dict[str, object], result)
        return {"status": "error", "error": "Worker result missing 'result' key"}
    return {"status": "error", "error": str(data.get("error", "Unknown worker error"))}


def _already_running_error() -> dict[str, object]:
    return {
        "status": "error",
        "error": (
            "execute_pre_commit_checks is already running for this configuration; "
            "do not start a second run. Wait for the existing run to finish."
        ),
    }


async def run_checks_detached(
    project_root: Path,
    checks: list[str],
    strict_mode: bool,
    timeout: int,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> dict[str, object]:
    """Run pre-commit checks via detached worker subprocess."""
    args_hash = compute_args_hash(
        checks, timeout, coverage_threshold, strict_mode, False
    )
    existing = find_existing_result(project_root, args_hash)
    cached = _cached_detached_result(existing, args_hash)
    if cached is not None:
        return cached
    if existing is not None and existing.get("status") == "running":
        logger.info(
            "Worker already running for args_hash=%s; returning in-progress status",
            args_hash,
        )
        return _already_running_error()

    _ = spawn_detached_worker(
        project_root, checks, timeout, coverage_threshold, strict_mode, False, args_hash
    )
    result_path = _result_path(_session_dir(project_root), args_hash)
    data = await poll_for_result(result_path, ctx, timeout=900.0)
    return _interpret_poll_data(data)
