"""Phase dispatch for execute_pre_commit_checks(phase="A"|"B"|"full").

Lazy imports avoid circular dependency with pre_commit_tools (preflight
helpers import execute_pre_commit_checks from pre_commit_tools).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import cast

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict


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


async def _run_phase_a(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run Phase A preflight (lazy import)."""
    from cortex.tools.execution.pre_commit_preflight_helpers import (
        run_preflight_checks_impl,
    )

    return await run_preflight_checks_impl(
        test_timeout=test_timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        include_untracked_markdown=include_untracked_markdown,
        ctx=ctx,
    )


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
