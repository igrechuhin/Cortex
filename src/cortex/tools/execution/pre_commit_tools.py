"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Tools:
- execute_pre_commit_checks: Run checks with explicit list or phase.
- start_quality_job / get_quality_job_status: Non-blocking detached job API.
- get_last_pre_commit_status: Last run summary (internal fallback).
- run_quality_gate / run_docs_gate: Zero-arg pipeline tools.
- autofix: Zero-arg auto-fix (format, lint, type, markdown).

Implementation helpers live in pre_commit_tools_inline_execution and
pre_commit_tools_execute_checks to satisfy file-size limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.execution_env import ExecutionEnvironment, LocalExecutionEnvironment
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


async def _execute_pre_commit_checks_inner(
    phase: Literal["A", "B", "full"] | None,
    checks: Sequence[PreCommitCheckName] | None,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    skip_if_clean: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Dispatch pre-commit checks after resolving phase enum."""
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
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX, enable_progress=False)
async def execute_pre_commit_checks(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 600,
    coverage_threshold: float = 0.9,
    strict_mode: bool = False,
    include_untracked_markdown: bool = True,
    skip_if_clean: bool = False,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run pre-commit checks or a commit-pipeline phase (A, B, or full).

    USE WHEN: Running the quality gate before commit, validating format/type/quality/tests,
    or executing Phase A (preflight) or Phase B (docs/memory sync) of the commit pipeline.
    """
    return await _execute_pre_commit_checks_inner(
        phase,
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        skip_if_clean,
        ctx,
    )


async def _fetch_last_pre_commit_status(
    root: Path, ctx: MCPContext | None
) -> ModelDict:
    """Lazy-import and call get_last_pre_commit_status_impl."""
    module = __import__(
        "cortex.tools.execution.pre_commit_status",
        fromlist=["get_last_pre_commit_status_impl"],
    )
    impl = module.get_last_pre_commit_status_impl
    return cast(ModelDict, await impl(Path(root), ctx))


@ensure_usage_context
@mcp_tool_wrapper(timeout=60.0)
async def get_last_pre_commit_status(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Return summary of the most recent detached execute_pre_commit_checks run.

    USE WHEN: You need to inspect the result of the latest pre-commit run
    (e.g. after reconnecting following a connection-closed error) without
    starting a new run. This tool is lightweight and safe to poll.

    RETURNS: JSON with status, args_hash, checks, preflight_passed, coverage, error.
    """
    root = await get_or_resolve_project_root(ctx)
    return await _fetch_last_pre_commit_status(root, ctx)


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


def _spawn_quality_job(
    root: Path,
    check_names: list[str],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    env: ExecutionEnvironment,
    force_fresh: bool = False,
) -> ModelDict:
    """Lazy-import and call start_pre_commit_job_impl."""
    module = __import__(
        "cortex.tools.execution.pre_commit_detached",
        fromlist=["start_pre_commit_job_impl"],
    )
    impl = module.start_pre_commit_job_impl
    result = impl(
        root,
        check_names,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        env,
        force_fresh,
    )
    return cast(ModelDict, result)


@ensure_usage_context
@mcp_tool_wrapper(timeout=60.0)
async def start_quality_job(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 600,
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

    RETURNS: {"job_id": "<hash>", "status": "started"|"already_running"|"completed"|"error"}
    """
    check_names = _resolve_pre_commit_check_names(phase=phase, checks=checks)
    root = await get_or_resolve_project_root(ctx)
    return _spawn_quality_job(
        Path(root),
        check_names,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        LocalExecutionEnvironment(),
        force_fresh,
    )


async def _fetch_quality_job_status(
    root: Path, job_id: str, ctx: MCPContext | None
) -> ModelDict:
    """Lazy-import and call get_pre_commit_status_impl for a specific job."""
    module = __import__(
        "cortex.tools.execution.pre_commit_status",
        fromlist=["get_pre_commit_status_impl"],
    )
    impl = module.get_pre_commit_status_impl
    return cast(ModelDict, await impl(root, job_id, ctx))


@ensure_usage_context
@mcp_tool_wrapper(timeout=30.0)
async def get_quality_job_status(
    job_id: str = "",
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Return summary for a specific detached pre-commit job by job_id.

    USE WHEN: Polling the status of a long-running detached quality gate
    started via start_quality_job without triggering a new run.

    RETURNS: JSON with status, args_hash, checks, preflight_passed, coverage, error.
    """
    root = await get_or_resolve_project_root(ctx)
    if not job_id:
        return await _fetch_last_pre_commit_status(root, ctx)
    return await _fetch_quality_job_status(Path(root), job_id, ctx)
