"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 1 tool
- execute_pre_commit_checks: Execute pre-commit checks (fix errors,
  format, type check, quality, tests) or fix-quality mode (checks=["fix_quality"]).
"""

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import external_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
    typed_mcp_tool,
)
from cortex.core.models import ModelDict
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.services.framework_adapters.go_adapter import GoAdapter
from cortex.services.framework_adapters.java_adapter import JavaAdapter
from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter
from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.rust_adapter import RustAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter
from cortex.services.language_detector import LanguageInfo
from cortex.tools.execution.pre_commit_fix_quality import (
    create_quality_error_response,
    fix_quality_issues_impl,
)
from cortex.tools.execution.pre_commit_helpers import (
    create_error_result_dict,
    determine_checks_to_perform,
    unsupported_language_result_dict,
)
from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language
from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.execution.pre_commit_phase_dispatch import PreCommitPhase
from cortex.tools.execution.pre_commit_tools_run_helpers import (
    build_pre_commit_response,
    run_checks_with_connection_monitoring,
)

logger = logging.getLogger(__name__)

# Adapter registry: language -> factory(project_root) -> FrameworkAdapter.
# Python, TypeScript, JavaScript, Rust, Go, Java, Swift, and Kotlin have full implementations.
_ADAPTER_REGISTRY: dict[str, Callable[[str | None], FrameworkAdapter]] = {
    "python": lambda root: PythonAdapter(root),
    "typescript": lambda root: TypeScriptAdapter(root),
    "javascript": lambda root: JavaScriptAdapter(root),
    "rust": lambda root: RustAdapter(root),
    "go": lambda root: GoAdapter(root),
    "java": lambda root: JavaAdapter(root),
    "swift": lambda root: SwiftAdapter(root),
    "kotlin": lambda root: KotlinAdapter(root),
}
SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(_ADAPTER_REGISTRY.keys())
# Public alias for pre_commit_worker subprocess (avoids reportPrivateUsage).
ADAPTER_REGISTRY = _ADAPTER_REGISTRY

# Type alias for check names (must match PreCommitCheck enum).
PreCommitCheckName = PreCommitCheck


def _get_adapter(
    language_info: LanguageInfo, project_root: str | None
) -> FrameworkAdapter | None:
    """Get framework adapter for detected language.

    Args:
        language_info: Detected language information.
        project_root: Project root directory.

    Returns:
        Framework adapter instance or None if language not in registry.
    """
    factory = _ADAPTER_REGISTRY.get(language_info.language)
    if factory is None:
        return None
    return factory(project_root)


async def _resolve_language_and_adapter(
    ctx: MCPContext | None,
    root_str: str,
    language: str | None,
) -> ModelDict | tuple[FrameworkAdapter, LanguageInfo]:
    """Resolve language and adapter; return error dict or (adapter, lang_info)."""
    result = detect_or_use_language(language, root_str)
    if isinstance(result, str):
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: language detection failed",
            logger_name=__name__,
        )
        return cast(ModelDict, json.loads(result))
    language_info, root_to_use = result
    adapter = _get_adapter(language_info, root_to_use)
    if adapter is None:
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: unsupported language",
            logger_name=__name__,
        )
        return unsupported_language_result_dict(
            language_info.language, SUPPORTED_LANGUAGES
        )
    return (adapter, language_info)


async def _run_inline_pre_commit_checks(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks in-process (non-detached)."""
    root_str = str(root)
    resolved = await _resolve_language_and_adapter(ctx, root_str, language)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    checks_to_perform = determine_checks_to_perform(checks)
    results, stats = await run_checks_with_connection_monitoring(
        adapter,
        language_info,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        ctx,
    )
    out = build_pre_commit_response(results, stats, language_info.language)
    await log_client(
        ctx, "info", "execute_pre_commit_checks: completed", logger_name=__name__
    )
    return out


async def _execute_pre_commit_checks_impl(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks and return result dict (FastMCP serializes to JSON)."""
    from cortex.tools.execution.pre_commit_detached import (
        DETACHED_ENABLED,
        run_checks_detached,
    )

    if DETACHED_ENABLED:
        return cast(
            ModelDict,
            await run_checks_detached(
                root,
                list(checks) if checks else [],
                strict_mode,
                timeout or 300,
                coverage_threshold,
                ctx,
            ),
        )
    return await _run_inline_pre_commit_checks(
        root, language, checks, strict_mode, timeout, coverage_threshold, ctx
    )


async def _dispatch_phase(
    phase: PreCommitPhase,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Dispatch to phase-based runner (A, B, or full)."""
    from cortex.tools.execution.pre_commit_phase_dispatch import (
        run_execute_pre_commit_checks_by_phase,
    )

    return await run_execute_pre_commit_checks_by_phase(
        phase,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        ctx,
    )


async def _run_fix_quality_and_return_dict(
    include_untracked_markdown: bool, ctx: MCPContext | None
) -> ModelDict:
    """Run fix_quality_issues_impl and return result as dict."""
    root = await get_or_resolve_project_root(ctx)
    json_str = await fix_quality_issues_impl(
        Path(root), include_untracked_markdown, ctx
    )
    result = json.loads(json_str)
    return cast(ModelDict, result)


async def _run_fix_quality_mode(
    include_untracked_markdown: bool, ctx: MCPContext | None
) -> ModelDict:
    """Run fix_quality path and return result dict."""
    await log_client(
        ctx,
        "info",
        "execute_pre_commit_checks: fix_quality mode (fix_errors, format, type_check, markdown)",
        logger_name=__name__,
    )
    try:
        return await _run_fix_quality_and_return_dict(include_untracked_markdown, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks fix_quality: {e!s}",
            logger_name=__name__,
        )
        error_json = create_quality_error_response(str(e))
        return cast(ModelDict, json.loads(error_json))


def _build_skip_clean_result(
    check_names: list[str],
    skip_reasons: list[str],
) -> ModelDict:
    """Build the ModelDict returned when checks are skipped (no source changes)."""
    return cast(
        ModelDict,
        {
            "status": "success",
            "skipped": True,
            "skip_reason": "No source files changed since Phase A",
            "checks_skipped": check_names,
            "skip_details": skip_reasons,
            "success": True,
            "total_errors": 0,
            "total_warnings": 0,
            "results": {},
            "checks_performed": [],
            "files_modified": [],
        },
    )


async def _try_skip_clean_checks(
    checks: Sequence[PreCommitCheckName],
    ctx: MCPContext | None,
) -> ModelDict | None:
    """Return a skip result if all checks can be skipped (no source changes).

    Returns None if any check cannot be skipped, meaning the full run
    must proceed.
    """
    from cortex.tools.execution.pre_commit_dirty_state import PipelineDirtyTracker

    tracker = PipelineDirtyTracker.get_instance()
    if not tracker.is_active:
        return None

    skip_reasons: list[str] = []
    for check in checks:
        check_name = check.value
        decision = tracker.can_skip_check(check_name)
        if not decision.can_skip:
            return None
        skip_reasons.append(f"{check_name}: {decision.reason}")

    check_names = [c.value for c in checks]
    await log_client(
        ctx,
        "info",
        f"execute_pre_commit_checks: skipping {check_names} (no source changes since Phase A)",
        logger_name=__name__,
    )
    return _build_skip_clean_result(check_names, skip_reasons)


async def _run_standard_checks_mode(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run standard checks path and return result dict."""
    await log_client(
        ctx,
        "info",
        f"execute_pre_commit_checks: checks={list(checks)}, timeout={test_timeout}, cov={coverage_threshold}, strict={strict_mode}",
        logger_name=__name__,
    )
    try:
        root = await get_or_resolve_project_root(ctx)
        return await _execute_pre_commit_checks_impl(
            root, None, checks, strict_mode, test_timeout, coverage_threshold, ctx
        )
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks: {e!s}",
            logger_name=__name__,
        )
        return create_error_result_dict(str(e), type(e).__name__)


async def _run_execute_pre_commit_checks(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    skip_if_clean: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Resolve root, run impl, log and handle errors."""
    is_fix_quality_only = len(checks) == 1 and checks[0] == PreCommitCheck.FIX_QUALITY
    if is_fix_quality_only:
        return await _run_fix_quality_mode(include_untracked_markdown, ctx)
    if skip_if_clean:
        skip_result = await _try_skip_clean_checks(checks, ctx)
        if skip_result is not None:
            return skip_result
    return await _run_standard_checks_mode(
        checks, test_timeout, coverage_threshold, strict_mode, ctx
    )


async def _execute_checks_for_explicit_list(
    checks: Sequence[PreCommitCheckName] | None,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    skip_if_clean: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Execute checks list when no phase is provided."""
    if not checks:
        return create_error_result_dict(
            "checks required when phase is None; or use phase='A'/'B'/'full'",
            "ValidationError",
        )
    return await _run_execute_pre_commit_checks(
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        skip_if_clean,
        ctx,
    )


async def _execute_pre_commit_checks_dispatch(
    phase: PreCommitPhase | None,
    checks: Sequence[PreCommitCheckName] | None,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    skip_if_clean: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Dispatch to phase or explicit checks list."""
    if phase is not None:
        return await _dispatch_phase(
            phase,
            test_timeout,
            coverage_threshold,
            strict_mode,
            include_untracked_markdown,
            ctx,
        )
    return await _execute_checks_for_explicit_list(
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        skip_if_clean,
        ctx,
    )


@typed_mcp_tool(
    annotations=external_annotations(
        "Execute Pre-Commit Checks",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
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
    return await _execute_pre_commit_checks_dispatch(
        phase_enum,
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        skip_if_clean,
        ctx,
    )


@typed_mcp_tool(
    annotations=external_annotations(
        "Get Last Pre-Commit Status",
        read_only=True,
        destructive=False,
        idempotent=True,
    )
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


@typed_mcp_tool(
    annotations=external_annotations(
        "Start Pre-Commit Job",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=60.0)
async def start_pre_commit_job(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 300,
    coverage_threshold: float = 0.9,
    strict_mode: bool = False,
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Start or reuse a detached pre-commit job; return {job_id, status} quickly.

    USE WHEN: Starting a long-running quality gate without blocking the MCP
    connection. Call this once to get a job_id, then poll with
    get_pre_commit_job_status(job_id) until status != "running".

    EXAMPLES:
    - start_pre_commit_job(phase="A") to start a full Phase A quality gate.
    - start_pre_commit_job(checks=["tests"], coverage_threshold=0.9) for tests only.

    RETURNS: {"job_id": "<hash>", "status": "started"|"already_running"|"completed"|"error"}
    - "started": worker spawned; poll with get_pre_commit_job_status(job_id).
    - "already_running": worker already active; poll the same job_id.
    - "completed": fresh cached result exists; call get_pre_commit_job_status for details.
    - "error": previous run failed; check get_pre_commit_job_status for error details.

    Args:
        phase: "A", "B", or "full". Resolves to canonical check list for the phase.
            Mutually exclusive with checks.
        checks: Explicit check list. Required when phase is None.
        test_timeout, coverage_threshold, strict_mode, include_untracked_markdown:
            Passed through to the detached worker.
    """
    from cortex.tools.execution.pre_commit_phase_dispatch import (
        PreCommitPhase,
        phase_to_checks,
    )

    if phase is not None:
        phase_enum = PreCommitPhase(phase)
        check_names: list[str] = phase_to_checks(phase_enum)
    elif checks:
        check_names = [c.value if hasattr(c, "value") else str(c) for c in checks]
    else:
        return create_error_result_dict(
            "Either phase ('A', 'B', 'full') or checks list is required",
            "ValidationError",
        )
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
    )
    return cast(ModelDict, result)


@typed_mcp_tool(
    annotations=external_annotations(
        "Get Pre-Commit Job Status",
        read_only=True,
        destructive=False,
        idempotent=True,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=30.0)
async def get_pre_commit_job_status(
    job_id: str,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Return summary for a specific detached pre-commit job by job_id.

    USE WHEN: Polling the status of a long-running detached quality gate
    started via start_pre_commit_job without triggering a new run. This is
    the preferred way to monitor progress and completion of Phase A/B/full
    or tests-only jobs from the commit pipeline.

    EXAMPLES:
    - get_pre_commit_job_status(job_id="abc123") in a loop until status != "running"
      to wait for a detached tests run to complete.
    - get_pre_commit_job_status(job_id="abc123") in a follow-up session to inspect
      the final result (status, coverage, checks) of a previously started job.

    RETURNS: JSON with at least:
      - status: "no_runs" | "running" | "completed" | "error" | "unknown"
      - args_hash: identifier of the detached run (usually derived from job_id)
      - checks: list of checks or checks_performed when available
      - preflight_passed / docs_phase_passed / coverage when reported
      - error: optional error message for "error" or "unknown" status.

    Args:
        job_id: Identifier of the detached pre-commit job (from start_pre_commit_job).
        ctx: Optional MCP context for logging and project root resolution.
    """
    root = await get_or_resolve_project_root(ctx)
    module = __import__(
        "cortex.tools.execution.pre_commit_status",
        fromlist=["get_pre_commit_status_impl"],
    )
    impl = module.get_pre_commit_status_impl
    return cast(
        ModelDict,
        await impl(Path(root), job_id, ctx),
    )
