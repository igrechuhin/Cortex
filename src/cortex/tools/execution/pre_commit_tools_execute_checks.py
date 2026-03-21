"""Dispatch and mode selection for execute_pre_commit_checks (non-MCP surface).

Extracted from pre_commit_tools to keep that module within file-size limits.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import ModelDict
from cortex.core.usage_context import (
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.tools.execution.pre_commit_fix_quality import (
    create_quality_error_response,
    fix_quality_issues_impl,
)
from cortex.tools.execution.pre_commit_helpers import (
    create_error_result_dict,
)
from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.execution.pre_commit_phase_dispatch import PreCommitPhase
from cortex.tools.execution.pre_commit_tools_inline_execution import (
    run_inline_pre_commit_checks,
)

logger = logging.getLogger(__name__)

PreCommitCheckName = PreCommitCheck


async def execute_pre_commit_checks_impl(
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
    return await run_inline_pre_commit_checks(
        root, language, checks, strict_mode, timeout, coverage_threshold, ctx
    )


async def _run_phase_detached(
    phase: PreCommitPhase,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run phase via detached worker; used when DETACHED_ENABLED."""
    from cortex.tools.execution.pre_commit_detached import run_checks_detached
    from cortex.tools.execution.pre_commit_phase_dispatch import phase_to_checks

    checks = phase_to_checks(phase)
    root = get_current_project_root() or await get_or_resolve_project_root(ctx)
    return cast(
        ModelDict,
        await run_checks_detached(
            root, checks, strict_mode, test_timeout, coverage_threshold, ctx
        ),
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
    from cortex.tools.execution.pre_commit_detached import DETACHED_ENABLED

    if DETACHED_ENABLED:
        return await _run_phase_detached(
            phase, test_timeout, coverage_threshold, strict_mode, ctx
        )
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
    except (OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError) as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks fix_quality: {e!s}",
            logger_name=__name__,
        )
        error_json = create_quality_error_response(str(e))
        return cast(ModelDict, json.loads(error_json))
    except Exception as e:
        logger.exception("execute_pre_commit_checks fix_quality: unexpected exception")
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


async def try_skip_clean_checks(
    checks: Sequence[PreCommitCheckName],
    ctx: MCPContext | None,
) -> ModelDict | None:
    """Return a skip result if all checks can be skipped (no source changes)."""
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
    logger.info(
        "execute_pre_commit_checks: checks=%s, timeout=%s, cov=%s, strict=%s",
        list(checks),
        test_timeout,
        coverage_threshold,
        strict_mode,
    )
    try:
        root = get_current_project_root() or await get_or_resolve_project_root(ctx)
        return await execute_pre_commit_checks_impl(
            root, None, checks, strict_mode, test_timeout, coverage_threshold, ctx
        )
    except (OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError) as e:
        logger.error("execute_pre_commit_checks: %s", e)
        return create_error_result_dict(str(e), type(e).__name__)
    except Exception as e:
        logger.exception("execute_pre_commit_checks: unexpected exception")
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
        skip_result = await try_skip_clean_checks(checks, ctx)
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


async def execute_pre_commit_checks_dispatch(
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


__all__ = [
    "PreCommitCheckName",
    "execute_pre_commit_checks_dispatch",
    "execute_pre_commit_checks_impl",
    "try_skip_clean_checks",
]
