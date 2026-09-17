"""Bounded MCP waits over the existing detached Phase A result files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import ExecutionEnvironment
from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_detached import (
    compute_args_hash,
    find_running_job,
)
from cortex.tools.execution.pre_commit_phase_dispatch import (
    PreCommitPhase,
    phase_to_checks,
)
from cortex.tools.execution.pre_commit_process import (
    pre_commit_result_path,
    read_result_file,
)
from cortex.tools.execution.session_paths import session_dir


def quality_gate_job_path(root: Path, timeout: int, coverage_threshold: float) -> Path:
    """Resolve the same identity used by the detached Phase A worker."""
    job_id = compute_args_hash(
        list(phase_to_checks(PreCommitPhase.A)),
        timeout,
        coverage_threshold,
        False,
        True,
    )
    return pre_commit_result_path(session_dir(root), job_id)


async def _needs_new_job(result_path: Path, force_fresh: bool) -> bool:
    envelope, _ = await read_result_file(result_path)
    return envelope is None or (
        force_fresh and envelope.get("quality_gate_pending") is not True
    )


async def _mark_delivered(result_path: Path) -> None:
    from cortex.tools.execution.pre_commit_worker import atomic_write

    envelope, _ = await read_result_file(result_path)
    if envelope is not None:
        envelope["quality_gate_pending"] = False
        atomic_write(result_path, envelope)


async def _run_locked_job(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
    result_path: Path,
) -> ModelDict:
    from cortex.tools.execution import pre_commit_zero_arg_tools as tools
    from cortex.tools.execution.pre_commit_fingerprint_store import (
        clear_phase_a_fingerprint,
    )

    async with tools.get_phase_a_lock(str(root.resolve())):
        active = find_running_job(root)
        if active is not None and active.get("result_file") != str(result_path):
            return cast(ModelDict, active)
        if active is None and await _needs_new_job(result_path, force_fresh):
            if force_fresh:
                clear_phase_a_fingerprint(root)
            job = tools.start_phase_a_job(
                root,
                timeout,
                coverage_threshold,
                force_fresh,
                env=env,
                quality_gate=True,
            )
            if job.get("status") == "error":
                return job
        return await _poll_and_deliver(root, result_path, timeout, ctx)


async def _poll_and_deliver(
    root: Path, result_path: Path, timeout: int, ctx: MCPContext | None
) -> ModelDict:
    from cortex.tools.execution.pre_commit_zero_arg_tools import poll_phase_a_result

    job_id = result_path.stem.removeprefix("pre_commit_result_")
    result = await poll_phase_a_result(root, job_id, timeout, ctx)
    if result.get("status") not in {"running", "timeout"}:
        await _mark_delivered(result_path)
    return result


async def run_bounded_phase_a(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
    wait_seconds: float,
) -> ModelDict:
    """Bound lock acquisition and polling without cancelling the detached worker."""
    result_path = quality_gate_job_path(root, timeout, coverage_threshold)
    try:
        async with asyncio.timeout(wait_seconds):
            return await _run_locked_job(
                root, timeout, coverage_threshold, force_fresh, ctx, env, result_path
            )
    except TimeoutError:
        return _pending_result(root, result_path)


def _pending_result(root: Path, result_path: Path) -> ModelDict:
    active = find_running_job(root)
    if active is not None:
        return cast(ModelDict, active)
    if not result_path.exists():
        return {"status": "error", "error": "Phase A lock is busy; retry the gate."}
    return {
        "status": "running",
        "job_id": result_path.stem.removeprefix("pre_commit_result_"),
        "result_file": str(result_path),
        "preflight_passed": False,
        "message": "Phase A is pending; call run_quality_gate again to resume.",
    }
