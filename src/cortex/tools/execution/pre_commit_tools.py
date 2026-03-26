"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Tools:
- execute_pre_commit_checks: Run checks with explicit list or phase.
- start_quality_job / get_quality_job_status: Non-blocking detached job API.
- get_last_pre_commit_status: Last run summary (internal fallback).
- run_quality_gate / run_quality_gate_fresh / run_docs_gate: Zero-arg pipeline tools.
- fix_quality_issues: Zero-arg auto-fix (format, lint, type, markdown).

Implementation helpers live in pre_commit_tools_inline_execution and
pre_commit_tools_execute_checks to satisfy file-size limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.core.usage_context import (
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.language_quality_router import LanguageQualityRouter
from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language
from cortex.tools.execution.pre_commit_phase_dispatch import PreCommitPhase
from cortex.tools.execution.pre_commit_submodule_guard import precommit_block_response
from cortex.tools.execution.pre_commit_tools_execute_checks import (
    PreCommitCheckName,
    execute_pre_commit_checks_dispatch,
)

__all__ = [
    "PreCommitCheckName",
    "PythonAdapter",
    "detect_or_use_language",
    "execute_pre_commit_checks",
    "get_current_project_root",
    "get_last_pre_commit_status",
    "get_quality_job_status",
    "log_client",
    "precommit_block_response",
    "start_quality_job",
]


SUPPORTED_LANGUAGES: tuple[str, ...] = LanguageQualityRouter.supported_languages()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX, enable_progress=False)
async def execute_pre_commit_checks(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 300,
    coverage_threshold: float = 0.9,
    strict_mode: bool = False,
    include_untracked_markdown: bool = True,
    skip_if_clean: bool = False,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run pre-commit checks or a commit-pipeline phase (A, B, or full).

    USE WHEN: Running the quality gate before commit, validating format/type/quality/tests,
    or executing Phase A (preflight) or Phase B (docs/memory sync) of the commit pipeline.

    EXAMPLES: execute_pre_commit_checks(phase="A") for preflight;
    execute_pre_commit_checks(checks=["format", "type_check"]) for targeted checks;
    execute_pre_commit_checks(checks=["tests"], skip_if_clean=True) for Step 12 re-runs
    that skip when no source files changed since Phase A;
    execute_pre_commit_checks(phase="B") for docs/memory validation after Step 5.

    DO NOT:
    - Run raw pytest/ruff/black commands in a shell for this project; use this MCP tool so
      results are structured and consistent with the commit pipeline.
    - Pass project_root or cwd-style parameters; the tool resolves the project root
      internally.
    - Mix phase and checks in the same call; use either a phase ("A", "B", "full") or an
      explicit checks list.

    RETURNS: JSON with status; for phase "A" or "full": preflight_passed, checks (per-check
    results); for phase "B" or "full": docs_phase_passed, timestamps, roadmap_sync; for
    explicit checks: results per check (format, type_check, quality, tests, etc.).
    When skip_if_clean=True and no source files changed since Phase A, returns
    {"status": "success", "skipped": true, "skip_reason": "..."}.

    Args:
        phase: "A", "B", or "full" for pipeline phases. Optional.
        checks: Required when phase is None. E.g. ["format"], ["type_check", "quality"].
        test_timeout, coverage_threshold, strict_mode: Check options.
        skip_if_clean: When True, skip checks if no source files changed since Phase A.
            Use for Step 12 re-runs to avoid redundant checks. Default False.

    When phase is None, you must pass checks (e.g. ["format"], ["type_check", "quality"],
    ["fix_quality"] for auto-fix only, or ["tests"] with test_timeout and coverage_threshold).
    Language is auto-detected. checks=["fix_quality"] runs fix_errors, format, type_check,
    and markdown lint (no tests); returns fix-quality response shape.
    """
    phase_enum: PreCommitPhase | None = (
        PreCommitPhase(phase) if phase is not None else None
    )
    return await execute_pre_commit_checks_dispatch(
        phase_enum,
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        skip_if_clean,
        ctx,
    )


@ensure_usage_context
@mcp_tool_wrapper(timeout=60.0)
async def get_last_pre_commit_status(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Return summary of the most recent detached execute_pre_commit_checks run.

    USE WHEN: You need to inspect the result of the latest pre-commit run
    (e.g. after reconnecting following a connection-closed error) without
    starting a new run. This tool is lightweight and safe to poll.

    EXAMPLES:
    - get_last_pre_commit_status() immediately after execute_pre_commit_checks(checks=["tests"])
      to see whether tests are still running or have completed.
    - get_last_pre_commit_status() in a follow-up session to inspect the outcome of a detached
      quality gate run without starting a new one.

    RETURNS: JSON with at least:
      - status: "no_runs" | "running" | "completed" | "error" | "unknown"
      - args_hash: identifier of the detached run (if known)
      - checks: list of checks or checks_performed (when available)
      - preflight_passed / docs_phase_passed / coverage when reported
      - error: optional error message for "error" or "unknown" status.
    """
    root = await get_or_resolve_project_root(ctx)
    module = __import__(
        "cortex.tools.execution.pre_commit_status",
        fromlist=["get_last_pre_commit_status_impl"],
    )
    impl = module.get_last_pre_commit_status_impl
    return cast(
        ModelDict,
        await impl(Path(root), ctx),
    )


def _resolve_pre_commit_check_names(
    *,
    phase: Literal["A", "B", "full"] | None,
    checks: Sequence[PreCommitCheckName] | None,
) -> list[str]:
    from cortex.tools.execution.pre_commit_phase_dispatch import (
        PreCommitPhase,
        phase_to_checks,
    )

    if phase is not None:
        phase_enum = PreCommitPhase(phase)
        return phase_to_checks(phase_enum)
    if checks:
        return [c.value if hasattr(c, "value") else str(c) for c in checks]
    # Cursor MCP wrapper cannot currently pass args to tools, so default
    # to Phase A when neither phase nor checks are provided. This ensures
    # commit-checks and commit-final-gate agents can start the quality job.
    return phase_to_checks(PreCommitPhase("A"))


@ensure_usage_context
@mcp_tool_wrapper(timeout=60.0)
async def start_quality_job(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 300,
    coverage_threshold: float = 0.9,
    strict_mode: bool = False,
    include_untracked_markdown: bool = True,
    force_fresh: bool = False,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Start or reuse a detached pre-commit job; return {job_id, status} quickly.

    USE WHEN: Starting a long-running quality gate without blocking the MCP
    connection. Call this once to get a job_id, then poll with
    get_quality_job_status(job_id) until status != "running".

    EXAMPLES:
    - start_quality_job(phase="A") to start a full Phase A quality gate.
    - start_quality_job(checks=["tests"], coverage_threshold=0.9) for tests only.
    - start_quality_job(phase="A", force_fresh=True) for Step 12 final gate —
      always spawns a new worker even when a recent cached result exists.

    RETURNS: {"job_id": "<hash>", "status": "started"|"already_running"|"completed"|"error"}
    - "started": worker spawned; poll with get_quality_job_status(job_id).
    - "already_running": worker already active; poll the same job_id.
    - "completed": fresh cached result exists; call get_quality_job_status for details.
    - "error": previous run failed; check get_quality_job_status for error details.

    Args:
        phase: "A", "B", or "full". Resolves to canonical check list for the phase.
            Mutually exclusive with checks.
        checks: Explicit check list. Required when phase is None.
        test_timeout, coverage_threshold, strict_mode, include_untracked_markdown:
            Passed through to the detached worker.
        force_fresh: When True, bypass any cached result and always spawn a fresh worker.
            Use for Step 12 (final gate) where Phase B/C may have modified files since
            Phase A completed.
    """
    check_names = _resolve_pre_commit_check_names(phase=phase, checks=checks)
    root = await get_or_resolve_project_root(ctx)
    module = __import__(
        "cortex.tools.execution.pre_commit_detached",
        fromlist=["start_pre_commit_job_impl"],
    )
    impl = module.start_pre_commit_job_impl
    result = impl(
        Path(root),
        check_names,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        force_fresh,
    )
    return cast(ModelDict, result)


@ensure_usage_context
@mcp_tool_wrapper(timeout=30.0)
async def get_quality_job_status(
    job_id: str = "",
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Return summary for a specific detached pre-commit job by job_id.

    USE WHEN: Polling the status of a long-running detached quality gate
    started via start_quality_job without triggering a new run. This is
    the preferred way to monitor progress and completion of Phase A/B/full
    or tests-only jobs from the commit pipeline.

    EXAMPLES:
    - get_quality_job_status(job_id="abc123") in a loop until status != "running"
      to wait for a detached tests run to complete.
    - get_quality_job_status(job_id="abc123") in a follow-up session to inspect
      the final result (status, coverage, checks) of a previously started job.
    - get_quality_job_status() with no args: falls back to get_last_pre_commit_status
      (most recent run). Use when the MCP wrapper cannot pass job_id.

    RETURNS: JSON with at least:
      - status: "no_runs" | "running" | "completed" | "error" | "unknown"
      - args_hash: identifier of the detached run (usually derived from job_id)
      - checks: list of checks or checks_performed when available
      - preflight_passed / docs_phase_passed / coverage when reported
      - error: optional error message for "error" or "unknown" status.

    Args:
        job_id: Identifier of the detached pre-commit job (from start_quality_job).
            When empty or omitted, falls back to the most recent run (same as
            get_last_pre_commit_status). This allows environments where the MCP
            wrapper cannot pass arguments to still poll the running job.
        ctx: Optional MCP context for logging and project root resolution.
    """
    root = await get_or_resolve_project_root(ctx)
    if not job_id:
        module = __import__(
            "cortex.tools.execution.pre_commit_status",
            fromlist=["get_last_pre_commit_status_impl"],
        )
        impl = module.get_last_pre_commit_status_impl
        return cast(ModelDict, await impl(Path(root), ctx))
    module = __import__(
        "cortex.tools.execution.pre_commit_status",
        fromlist=["get_pre_commit_status_impl"],
    )
    impl = module.get_pre_commit_status_impl
    return cast(
        ModelDict,
        await impl(Path(root), job_id, ctx),
    )
