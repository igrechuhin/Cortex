"""Bounded autofix waits over durable detached-worker outcomes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import ExecutionEnvironment
from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_detached import (
    clear_all_cached_results,
    find_running_job,
    fix_args_hash,
    fix_result_path,
    start_fix_job_impl,
)
from cortex.tools.execution.pre_commit_process import poll_for_result, read_result_file
from cortex.tools.execution.pre_commit_worker import atomic_write
from cortex.tools.execution.session_paths import session_dir

AUTOFIX_WAIT_SECONDS = 20.0


def _pending_result(root: Path, result_path: Path) -> ModelDict:
    active = find_running_job(root)
    if active is not None:
        return cast(ModelDict, active)
    if not result_path.exists():
        return {"status": "error", "error": "Phase A lock is busy; retry autofix."}
    return {
        "status": "running",
        "job_id": result_path.stem.removeprefix("pre_commit_fix_result_"),
        "result_file": str(result_path),
        "message": "Autofix is pending; call autofix again to retrieve its outcome.",
    }


def _deliver_result(result_path: Path, envelope: dict[str, object]) -> ModelDict:
    from cortex.tools.execution.pre_commit_fix_quality import parse_fix_envelope

    result = envelope.get("autofix_result")
    if envelope.get("status") == "error" or not isinstance(result, dict):
        # AI: Recover legacy outcomes without repeating their workspace mutations.
        result = json.loads(parse_fix_envelope(cast(ModelDict, envelope)))
    envelope["autofix_pending"] = False
    atomic_write(result_path, envelope)
    return cast(ModelDict, result)


async def _run_locked_job(
    root: Path,
    include_markdown: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
    result_path: Path,
) -> ModelDict:
    from cortex.tools.execution.pre_commit_zero_arg_tools import get_phase_a_lock

    async with get_phase_a_lock(str(root.resolve())):
        active = find_running_job(root)
        if active is not None and active.get("result_file") != str(result_path):
            return cast(ModelDict, active)
        envelope, status = await read_result_file(result_path)
        if active is None and (
            envelope is None or envelope.get("autofix_pending") is False
        ):
            _ = clear_all_cached_results(root)
            job = start_fix_job_impl(root, include_markdown, env)
            if job.get("status") in {"error", "running"}:
                return cast(ModelDict, job)
            envelope, status = None, None
        if envelope is None or status not in {"completed", "error"}:
            envelope = await poll_for_result(result_path, ctx, timeout=960.0)
        if envelope.get("status") == "timeout":
            return _pending_result(root, result_path)
        return _deliver_result(result_path, envelope)


async def run_bounded_autofix(
    root: Path,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Bound lock acquisition and polling; never cancel detached mutation work."""
    result_path = fix_result_path(
        session_dir(root), fix_args_hash(include_untracked_markdown)
    )
    try:
        async with asyncio.timeout(AUTOFIX_WAIT_SECONDS):
            return await _run_locked_job(
                root, include_untracked_markdown, ctx, env, result_path
            )
    except TimeoutError:
        return _pending_result(root, result_path)
