"""Zero-arg pre-commit MCP tools for the commit pipeline.

Extracted from ``pre_commit_tools.py`` to keep that module under the
file-length limit while preserving the public MCP surface:

- run_quality_gate: Phase A quality gate (used by commit orchestrator and Step 12)
- run_docs_gate: Phase B docs/memory validation
- autofix: Auto-fix format/type/quality/markdown issues
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import cast

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import (
    ExecutionEnvironment,
    LocalExecutionEnvironment,
)
from cortex.core.mcp_annotations import external_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
    typed_mcp_tool,
)
from cortex.core.models import JsonDict, ModelDict, OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import (
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.experience.gate_hook import record_gate_result
from cortex.tools.evaluation.reflection import apply_reflection_to_gate_result
from cortex.tools.execution.pre_commit_config import (
    as_bool,
    as_float,
    as_int,
    read_pipeline_phase_config,
)
from cortex.tools.execution.pre_commit_detached import clear_all_cached_results
from cortex.tools.execution.pre_commit_dirty_state import PipelineDirtyTracker
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    run_docs_and_memory_bank_sync_impl,
)
from cortex.tools.execution.pre_commit_fix_quality import autofix_impl
from cortex.tools.execution.pre_commit_phase_dispatch import (
    PreCommitPhase,
    phase_to_checks,
)
from cortex.tools.execution.pre_commit_preflight_helpers import compute_preflight_passed
from cortex.tools.logging.instrumentation import (
    append_agent_log_to_autofix_result,
    append_agent_log_to_quality_result,
)
from cortex.tools.plans.operations_log import OperationsLogType
from cortex.tools.plans.operations_log_hooks import append_log_entry_best_effort
from cortex.tools.session.gate_feedback import (
    feedback_from_docs_result,
    feedback_from_quality_result,
    persist_gate_feedback,
)

logger = logging.getLogger(__name__)

# Serializes Phase-A spawns (run_quality_gate, autofix) per project root.
# Concurrent Phase-A subprocess jobs for the same project crash the MCP server
# because they race on shared session files and stdout.
#
# Lazy per-loop: asyncio.Lock() binds to the running event loop at construction
# time. A module-level singleton created at import time fails with
# "bound to a different event loop" when tests (or xdist workers) each run in
# their own fresh loop. We key the lock to (loop, root scope) so each loop
# and project root pair gets its own lock, preventing cross-project contention.
_phase_a_lock_map: dict[tuple[asyncio.AbstractEventLoop, str], asyncio.Lock] = {}


def get_phase_a_lock(lock_scope: str | None = None) -> asyncio.Lock:
    """Return the Phase-A serialization lock for current loop and scope.

    Creates a new asyncio.Lock on first call for each distinct (event loop,
    lock scope) key, so pytest-asyncio and pytest-xdist workers that each spin
    up a fresh loop never share a lock bound to a different loop.
    """
    try:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    if lock_scope is None:
        root = get_current_project_root()
        lock_scope = str(root.resolve()) if root is not None else "__global__"
    key = (loop, lock_scope)
    if key not in _phase_a_lock_map:
        _phase_a_lock_map[key] = asyncio.Lock()
    return _phase_a_lock_map[key]


# Backwards-compatible alias: older call sites referenced `phase_a_lock()`.
# Keep it as a callable (not a module-level Lock) to avoid cross-event-loop bugs.
phase_a_lock = get_phase_a_lock


def _start_phase_a_job(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
    *,
    strict_mode: bool = False,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Start detached Phase A pre-commit job and return {job_id,status}."""
    from cortex.tools.execution.pre_commit_detached import start_pre_commit_job_impl

    checks = list(phase_to_checks(PreCommitPhase.A))
    job = start_pre_commit_job_impl(
        root,
        checks=checks,
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        include_markdown_lint=True,
        force_fresh=force_fresh,
        env=env,
    )
    return cast(ModelDict, job)


def markdown_result_has_errors(md: dict[str, object]) -> bool:
    """Return True when the detached worker's markdown_result indicates failures."""
    files_err = md.get("files_with_errors", 0)
    try:
        if isinstance(files_err, (int, str)) and int(files_err) > 0:
            return True
    except (ValueError, TypeError):
        # Non-numeric string — treat as error signal.
        return True
    status = str(md.get("status", "success"))
    error_msg = md.get("error")
    if (
        status == "error"
        and isinstance(error_msg, str)
        and "No such file or directory: 'rumdl'" in error_msg
    ):
        # Some sandboxed environments used by tool execution cannot spawn native
        # binaries like `rumdl`. Treat this as a non-blocking markdown-lint
        # prerequisite issue so the rest of the quality gate can proceed.
        return False

    if status == "error" and error_msg != "timeout":
        return True
    return False


def _merge_markdown_into_inner(
    envelope: dict[str, object], inner: dict[str, object]
) -> None:
    """Merge markdown_result from envelope into inner, updating preflight_passed."""
    md_raw = envelope.get("markdown_result")
    md_typed: JsonDict | None = None
    if isinstance(md_raw, dict):
        md_typed = cast(JsonDict, md_raw)
        inner["markdown_result"] = md_typed
    # AI: Must combine Phase A status with markdown; clean markdown must not mask failed checks.
    inner["preflight_passed"] = compute_preflight_passed(
        cast(ModelDict, inner), md_typed
    )


async def poll_phase_a_result(
    root: Path,
    job_id: str,
    timeout: int,
    ctx: MCPContext | None,
) -> ModelDict:
    """Poll detached Phase A result envelope and return inner dict.

    Merges ``result`` and ``markdown_result`` so ``preflight_passed``
    reflects both language checks and markdown lint.
    """
    from cortex.tools.execution.pre_commit_detached import poll_for_result

    rp = (
        get_cortex_path(root, CortexResourceType.SESSION)
        / f"pre_commit_result_{job_id}.json"
    )
    envelope = await poll_for_result(rp, ctx=ctx, timeout=float(timeout + 60))
    if envelope.get("status") != "completed":
        return cast(ModelDict, envelope)
    inner = envelope.get("result")
    if not isinstance(inner, dict):
        return cast(
            ModelDict,
            {"status": OperationStatus.ERROR.value, "error": "Missing result key"},
        )
    inner_dict = cast(dict[str, object], inner)
    _merge_markdown_into_inner(envelope, inner_dict)
    return cast(ModelDict, inner)


async def run_detached_phase_a_checks(
    root: Path,
    *,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    force_fresh: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Run Phase A via the detached subprocess path (same engine as ``run_quality_gate``).

    ``run_quality_gate`` reads timeouts and thresholds from the commit pipeline
    task file; preflight and tests call this helper with explicit parameters.
    """
    lock_scope = str(root.resolve())
    async with get_phase_a_lock(lock_scope):
        job = _start_phase_a_job(
            root,
            timeout=test_timeout,
            coverage_threshold=coverage_threshold,
            force_fresh=force_fresh,
            strict_mode=strict_mode,
            env=env,
        )
        job_id = str(job.get("job_id", ""))
        status = str(job.get("status", ""))
        if status == "error":
            return job
        return await poll_phase_a_result(root, job_id, timeout=test_timeout, ctx=ctx)


async def _spawn_and_poll_phase_a(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Spawn Phase A as a detached subprocess and poll with heartbeats.

    This keeps the MCP stdio connection alive by yielding to the event loop
    every 2 seconds (via asyncio.sleep in poll_for_result), allowing
    progress notifications to flow. Without this, long-running in-process
    checks block the event loop and some MCP clients drop the connection.

    Acquires ``get_phase_a_lock()`` before spawning to prevent concurrent
    Phase-A jobs, which race on shared session files and crash the MCP server.
    """
    return await run_detached_phase_a_checks(
        root,
        test_timeout=timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=False,
        force_fresh=force_fresh,
        ctx=ctx,
        env=env,
    )


_QUALITY_GATE_DEFAULTS: dict[str, object] = {
    "coverage_threshold": 0.90,
    "test_timeout": 600,
    "force_fresh": True,
    "reflection": False,
    "force_reflection": False,
}


def _read_quality_gate_config(root: Path) -> tuple[int, float, bool, dict[str, object]]:
    """Read pipeline config and return (timeout, coverage_threshold, force_fresh, cfg)."""
    cfg = read_pipeline_phase_config(root, "commit", "checks", _QUALITY_GATE_DEFAULTS)
    return (
        as_int(cfg.get("test_timeout"), 600),
        as_float(cfg.get("coverage_threshold"), 0.90),
        as_bool(cfg.get("force_fresh"), True),
        cfg,
    )


_PASS_TRIM_KEYS: frozenset[str] = frozenset(
    {
        "status",
        "preflight_passed",
        "summary",
        "checks_performed",
        "markdown_result",
        "language",
        "success",
        "total_errors",
        "total_warnings",
        "reflection_languages",
        "reflection_result",
        "skipped_checks",
        "skip_details",
    }
)


def trim_passing_quality_gate_result(result: ModelDict) -> ModelDict:
    """Shrink passing quality gate payloads for MCP (drop per-check bodies, large dicts)."""
    trimmed: ModelDict = {k: result[k] for k in _PASS_TRIM_KEYS if k in result}
    result.clear()
    result.update(trimmed)
    return result


async def run_quality_gate_inner(
    ctx: MCPContext | None, env: ExecutionEnvironment
) -> ModelDict:
    """Resolve config and spawn Phase A quality gate."""
    root = get_current_project_root() or Path(await get_or_resolve_project_root(ctx))
    timeout, coverage_threshold, force_fresh, cfg = _read_quality_gate_config(root)
    scope = str(root.resolve())
    logger.info(
        "run_quality_gate: start scope=%s timeout=%ss coverage_threshold=%.2f force_fresh=%s",
        scope,
        timeout,
        coverage_threshold,
        force_fresh,
    )
    # AI: Cache clears only when Step 12 / explicit force_fresh; default True preserves behavior.
    if force_fresh:
        _ = clear_all_cached_results(root)
    result = await _spawn_and_poll_phase_a(
        root,
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        force_fresh=force_fresh,
        ctx=ctx,
        env=env,
    )
    gate_passed = await _finalize_quality_gate_result(root, result, cfg, ctx)
    logger.info("run_quality_gate: done scope=%s passed=%s", scope, gate_passed)
    return result


async def _finalize_quality_gate_result(
    root: Path,
    result: ModelDict,
    cfg: dict[str, object],
    ctx: MCPContext | None,
) -> bool:
    """Apply reflection/feedback and record quality-gate completion."""
    apply_reflection_to_gate_result(root, result, cfg)
    await persist_gate_feedback(
        feedback_from_quality_result(cast(dict[str, object], result)), ctx
    )
    gate_passed = result.get("preflight_passed") is True
    # AI: record fitness before trim — the summary keys are dropped for passing gates.
    _ = await record_gate_result(root, result)
    if gate_passed:
        _ = trim_passing_quality_gate_result(result)
        PipelineDirtyTracker.get_instance().record_phase_a(root, True)
    else:
        append_agent_log_to_quality_result(result)
    await append_log_entry_best_effort(
        operation_type=OperationsLogType.LINT,
        title=f"Quality gate {'passed' if gate_passed else 'failed'}",
        summary=str(result.get("summary", "")).strip() or None,
        ctx=ctx,
        project_root=root,
    )
    return gate_passed


@typed_mcp_tool(
    annotations=external_annotations(
        "Run Quality Gate",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def run_quality_gate(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase A quality gate end-to-end and return full result. Zero args required.

    USE WHEN: Running the commit pipeline Phase A quality gate or the Step 12
    final gate. Spawns checks as a detached subprocess and polls with heartbeat
    progress notifications, keeping the MCP stdio connection alive.

    Config is read from the pipeline session file written by
    pipeline_handoff(operation="write", pipeline="commit", phase="checks").
    Supported keys: coverage_threshold (float), test_timeout (int), force_fresh (bool),
    reflection (bool), force_reflection (bool). When reflection is enabled and primary
    checks pass, a heuristic reflection pass runs; error-level findings set
    preflight_passed to false.

    EXAMPLES:
    - run_quality_gate() before commit Phase A.
    - pipeline_handoff(write, checks, {"force_fresh": true, "test_timeout": 600})
      then run_quality_gate() for Step 12 final gate.
    """
    return await run_quality_gate_with_env(ctx, LocalExecutionEnvironment())


async def run_quality_gate_with_env(
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Internal quality-gate entrypoint with injected execution environment."""
    return await run_quality_gate_inner(ctx, env)


@typed_mcp_tool(
    annotations=external_annotations(
        "Run Docs Gate",
        read_only=False,
        destructive=False,
        idempotent=True,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_docs_gate(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase B docs/memory-bank sync validation. Zero args required.

    USE WHEN: Validating that timestamps, roadmap_sync, and memory-bank files
    are consistent after documentation updates. Called by the commit-docs
    subagent as a zero-arg alternative to execute_pre_commit_checks(phase="B")
    (which some MCP client bridges zero-arg to Phase A, running tests instead).

    RETURNS: JSON with docs_phase_passed (bool), timestamps_result, and
    roadmap_sync_result. Does NOT run tests or code quality checks.

    EXAMPLES:
    - run_docs_gate() after updating memory-bank files via manage_file() in
      Phase B of the commit pipeline.
    - run_docs_gate() to re-check roadmap_sync and timestamps without
      re-running tests or other quality checks.
    """
    result = await run_docs_gate_with_env(ctx, LocalExecutionEnvironment())
    return result


async def run_docs_gate_with_env(
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Internal docs-gate entrypoint with injected execution environment."""
    _ = env
    result = await run_docs_and_memory_bank_sync_impl(ctx=ctx)
    await persist_gate_feedback(
        feedback_from_docs_result(cast(dict[str, object], result)),
        ctx,
    )
    return result


@typed_mcp_tool(
    annotations=external_annotations(
        "Fix Quality Issues",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def autofix(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Auto-fix formatting, linting, type errors, and markdown lint. Zero args required.

    USE WHEN: Phase A fails and automated fixes are needed before re-running checks.
    Called by commit-checks, commit-final-gate, and implement-code agents after
    preflight_passed=false. Runs fix_errors, format, type_check, and markdown auto-fix.

    INTEGRITY SAFEGUARDS:
    - Do not use this tool output as a "done" signal by itself; always re-run
      run_quality_gate() and validate changed modules still import cleanly.
    - If a fix iteration introduces new failures/regressions, roll back that
      attempt and retry with a different approach (max 3 attempts).

    EXAMPLES:
    - autofix() immediately after a failing run_quality_gate() call
      to auto-fix formatting, linting, type, and markdown issues.
    - autofix() inside implement-code or commit-checks agents on
      the fix path before re-running the quality gate.
    """
    return await autofix_with_env(ctx, LocalExecutionEnvironment())


async def autofix_with_env(
    ctx: MCPContext | None,
    env: ExecutionEnvironment,
) -> ModelDict:
    """Internal autofix entrypoint with injected execution environment."""
    root = get_current_project_root() or Path(await get_or_resolve_project_root(ctx))
    lock_scope = str(root.resolve())
    async with get_phase_a_lock(lock_scope):
        result_json = await autofix_impl(
            root,
            include_untracked_markdown=True,
            ctx=ctx,
            env=env,
        )
    _ = clear_all_cached_results(root)
    parsed = cast(ModelDict, json.loads(result_json))
    append_agent_log_to_autofix_result(parsed)
    await append_log_entry_best_effort(
        operation_type=OperationsLogType.FIX,
        title="Autofix completed",
        summary=(
            f"status={parsed.get('status')}; changed_files={parsed.get('changed_files')}"
        ),
        ctx=ctx,
        project_root=root,
    )
    return parsed
