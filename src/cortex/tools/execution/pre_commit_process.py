"""Subprocess lifecycle and async polling for detached pre-commit workers.

Spawns the worker module as a detached process and polls the result JSON file.
State machine and job orchestration live in ``pre_commit_detached``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext, report_progress_safe
from cortex.tools.execution.session_paths import session_dir

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 2
_HEARTBEAT_TOTAL = 500


def pre_commit_result_path(sd: Path, args_hash: str) -> Path:
    """Path to the JSON result file for a given args hash."""
    return sd / f"pre_commit_result_{args_hash}.json"


def pre_commit_worker_log_path(sd: Path, args_hash: str) -> Path:
    """Path to the worker stdout/stderr log for a given args hash."""
    return sd / f"pre_commit_worker_{args_hash}.log"


def is_process_alive(pid: int) -> bool:
    """Return True if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def build_worker_cmd(
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


def build_fix_worker_cmd(
    project_root: Path,
    rp: Path,
    include_markdown_fix: bool,
) -> list[str]:
    """Build argv for the detached fix worker subprocess."""
    cmd = [
        sys.executable,
        "-m",
        "cortex.tools.execution.pre_commit_fix_worker",
        "--result-file",
        str(rp),
        "--project-root",
        str(project_root),
    ]
    if include_markdown_fix:
        cmd.append("--include-markdown-fix")
    return cmd


def spawn_detached_process(cmd: list[str], log_file: Path, project_root: Path) -> None:
    """Start detached subprocess writing stdout/stderr to ``log_file``."""
    with open(log_file, "w") as lf:
        # On Unix the child process inherits the fd after the parent's
        # `with` block closes its own handle; this is intentional so
        # stdout/stderr are captured in the detached log file.
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
    sd = session_dir(project_root)
    rp = pre_commit_result_path(sd, args_hash)
    log_file = pre_commit_worker_log_path(sd, args_hash)
    cmd = build_worker_cmd(
        project_root,
        rp,
        checks,
        timeout,
        coverage_threshold,
        strict_mode,
        include_markdown_lint,
    )
    spawn_detached_process(cmd, log_file, project_root)
    logger.info("Spawned detached worker: hash=%s result=%s", args_hash, rp)
    return rp


async def _read_result_file(
    result_path: Path,
) -> tuple[dict[str, object] | None, str | None]:
    """Read result JSON if present. Returns (data, status) or (None, None)."""
    if not result_path.exists():
        return None, None
    try:
        # Avoid blocking the async event loop: file I/O runs on a worker thread.
        text = await asyncio.to_thread(result_path.read_text)
        data = json.loads(text)
        return cast(dict[str, object], data), data.get("status")
    except (json.JSONDecodeError, OSError):
        return None, None


def worker_died_error(pid: int) -> dict[str, object]:
    """Build error dict when worker process died."""
    return {
        "version": 1,
        "status": "error",
        "error": f"Worker process {pid} died without writing result",
    }


def timeout_error(timeout: float) -> dict[str, object]:
    """Build error dict for poll timeout."""
    return {
        "version": 1,
        "status": "timeout",
        "error": f"Timeout waiting for worker result after {timeout}s",
    }


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
        data, status = await _read_result_file(result_path)
        if data is None:
            continue
        if status == "completed" or status == "error":
            return data
        if status == "running":
            pid = data.get("pid")
            if isinstance(pid, int) and not is_process_alive(pid):
                return worker_died_error(pid)
    return timeout_error(timeout)
