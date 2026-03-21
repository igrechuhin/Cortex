"""Phase dispatch for execute_pre_commit_checks(phase="A"|"B"|"full").

Lazy imports avoid circular dependency with pre_commit_tools (preflight
helpers import execute_pre_commit_checks from pre_commit_tools).
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict
from cortex.core.usage_context import get_or_resolve_project_root

logger = logging.getLogger(__name__)

# Canonical check names for each phase, used by start_quality_job(phase=...).
# Language checks (all but markdown_lint) must match _PRE_FLIGHT_DEFAULT_CHECKS in
# pre_commit_preflight_helpers.py; markdown_lint is listed for job hashing but run
# separately in preflight / detached worker (same as CI rumdl step).
_PHASE_A_CHECKS: tuple[str, ...] = (
    "fix_errors",
    "format",
    "synapse_format",
    "synapse_lint",
    "type_check",
    "quality",
    "spelling",
    "tests",
    "eval_fast",
    "markdown_lint",
)
# Phase B is handled inline by run_docs_and_memory_bank_sync_impl; expose a
# sentinel check name so callers can form a deterministic job_id hash.
_PHASE_B_CHECKS: tuple[str, ...] = ("docs_and_memory_sync",)

# Public aliases for tests and external callers that should not rely on
# underscored module internals.
PHASE_A_CHECKS: tuple[str, ...] = _PHASE_A_CHECKS
PHASE_B_CHECKS: tuple[str, ...] = _PHASE_B_CHECKS


def phase_to_checks(phase: PreCommitPhase) -> list[str]:
    """Return canonical check name list for a phase.

    Used by start_quality_job(phase=...) to resolve the checks list
    without needing to invoke the full phase runner.

    Args:
        phase: Phase enum value (A, B, or FULL).

    Returns:
        List of check name strings for the given phase.
    """
    if phase is PreCommitPhase.A:
        return list(_PHASE_A_CHECKS)
    if phase is PreCommitPhase.B:
        return list(_PHASE_B_CHECKS)
    return list(_PHASE_A_CHECKS + _PHASE_B_CHECKS)


def _ensure_dict(value: ModelDict | str) -> ModelDict:
    """Ensure value is a dict; parse JSON string if needed (MCP protocol edge case).

    Some MCP clients may return tool results as JSON strings instead of parsed dicts.
    This prevents AttributeError: 'str' object has no attribute 'get'.
    """
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return (
            cast(ModelDict, parsed) if isinstance(parsed, dict) else cast(ModelDict, {})
        )
    except (json.JSONDecodeError, TypeError):
        return cast(ModelDict, {"status": "error", "error": str(value)})


class PreCommitPhase(str, Enum):
    A = "A"
    B = "B"
    FULL = "full"


def _record_phase_a_fingerprint(result: ModelDict, project_root: Path) -> None:
    """Record dirty-state fingerprint after Phase A if it passed."""
    from cortex.tools.execution.pre_commit_dirty_state import PipelineDirtyTracker

    passed = bool(result.get("preflight_passed", False))
    tracker = PipelineDirtyTracker.get_instance()
    tracker.record_phase_a(project_root, passed)


async def _best_effort_record_phase_a_fingerprint(
    result: ModelDict,
    ctx: MCPContext | None,
) -> None:
    """Best-effort Phase A fingerprint bookkeeping (never changes Phase A result)."""
    root: Path | None = None
    preflight_passed: bool | None = None
    try:
        root = await get_or_resolve_project_root(ctx)
        candidate = result.get("preflight_passed", None)
        if not isinstance(candidate, bool):
            logger.warning(
                "Skipping Phase A fingerprint bookkeeping due to invalid result shape; preflight_passed=%r (type=%s)",
                candidate,
                type(candidate).__name__,
            )
            return
        preflight_passed = candidate
        _record_phase_a_fingerprint(result, root)
    except (OSError, ValueError, TypeError, RuntimeError):
        logger.warning(
            "Phase A fingerprint bookkeeping failed (best-effort); preflight_passed=%s project_root=%s",
            preflight_passed,
            root,
            exc_info=True,
        )


async def _run_phase_a(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run Phase A preflight (lazy import).

    After completion, records a dirty-state fingerprint so Step 12 can
    skip redundant re-runs when no source files changed.
    """
    from cortex.tools.execution.pre_commit_preflight_helpers import (
        run_preflight_checks_impl,
    )

    result = await run_preflight_checks_impl(
        test_timeout=test_timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        include_untracked_markdown=include_untracked_markdown,
        ctx=ctx,
    )
    await _best_effort_record_phase_a_fingerprint(result, ctx)
    return result


async def _run_phase_b(ctx: MCPContext | None) -> ModelDict:
    """Run Phase B docs/memory sync (lazy import)."""
    from cortex.tools.execution.pre_commit_docs_memory_helpers import (
        run_docs_and_memory_bank_sync_impl,
    )

    return await run_docs_and_memory_bank_sync_impl(ctx=ctx)


async def _run_phase_full(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run Phase A then B (lazy import)."""
    phase_a_result = await _run_phase_a(
        test_timeout, coverage_threshold, strict_mode, include_untracked_markdown, ctx
    )
    phase_b_result = await _run_phase_b(ctx)
    phase_a_dict = _ensure_dict(phase_a_result)
    phase_b_dict = _ensure_dict(phase_b_result)
    return cast(
        ModelDict,
        {
            "status": "success",
            "phase": "full",
            "phase_a": phase_a_dict,
            "phase_b": phase_b_dict,
            "preflight_passed": phase_a_dict.get("preflight_passed", False),
            "docs_phase_passed": phase_b_dict.get("docs_phase_passed", False),
        },
    )


async def run_execute_pre_commit_checks_by_phase(
    phase: PreCommitPhase,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run Phase A and/or B; lazy import to avoid cycle with pre_commit_tools."""
    if phase is PreCommitPhase.A:
        return await _run_phase_a(
            test_timeout,
            coverage_threshold,
            strict_mode,
            include_untracked_markdown,
            ctx,
        )
    if phase is PreCommitPhase.B:
        return await _run_phase_b(ctx)
    return await _run_phase_full(
        test_timeout, coverage_threshold, strict_mode, include_untracked_markdown, ctx
    )
