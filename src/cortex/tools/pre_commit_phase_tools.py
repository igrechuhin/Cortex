"""Phase-level pre-commit MCP tools for commit pipeline orchestration.

This module exposes high-level MCP tools for Phase A (preflight checks)
and Phase B (docs & memory bank validations) of the commit pipeline.
The pure business logic lives in helper modules so this file can remain
small and focused on MCP tool registration and logging.
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import external_annotations, read_only_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import ModelDict
from cortex.server import mcp
from cortex.tools.pre_commit_docs_memory_helpers import (
    run_docs_and_memory_bank_sync_impl,
)
from cortex.tools.pre_commit_preflight_helpers import run_preflight_checks_impl


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=external_annotations(
        "Run Commit Preflight Checks",
        read_only=False,
        destructive=False,
        idempotent=False,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(
    timeout=MCP_TOOL_TIMEOUT_COMPLEX,
    enable_progress=True,
)
async def run_preflight_checks(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase A preflight checks as a single MCP tool.

    USE WHEN: Commit pipeline Phase A, before memory bank or commit; user
    requests pre-commit validation, format/lint/type/quality/tests check.

    EXAMPLES: 'run preflight checks', 'run Phase A checks', 'execute
    pre-commit validation', 'run_preflight_checks(test_timeout=300,
    coverage_threshold=0.9, strict_mode=False)'.

    RETURNS: JSON with preflight_passed, language, checks (per-check
    summaries), execute_result, markdown_result; status=\"error\" on tool failure.

    This helper runs execute_pre_commit_checks for the default Phase A
    checks and fix_markdown_lint once, then returns a structured JSON
    result with per-check summaries and raw tool outputs. Tool-level
    failures are reported via status=\"error\" while normal check
    failures keep status=\"success\" but set preflight_passed=False.
    """
    await log_client(
        ctx,
        "info",
        "run_preflight_checks: starting preflight checks",
        logger_name=__name__,
    )

    result = await run_preflight_checks_impl(
        test_timeout=test_timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        include_untracked_markdown=include_untracked_markdown,
        ctx=ctx,
    )

    await log_client(
        ctx,
        "info",
        "run_preflight_checks: completed",
        logger_name=__name__,
    )
    return result


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=read_only_annotations(
        "Run Docs and Memory Bank Validations",
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(
    timeout=MCP_TOOL_TIMEOUT_COMPLEX,
    enable_progress=True,
)
async def run_docs_and_memory_bank_sync(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase B docs/memory validations as a single MCP tool.

    USE WHEN: After Phase A and memory bank/roadmap updates; commit
    pipeline Phase B; user requests timestamp or roadmap sync validation.

    EXAMPLES: 'run docs and memory bank sync', 'run Phase B validations',
    'validate timestamps and roadmap sync', 'run_docs_and_memory_bank_sync()'.

    RETURNS: JSON with docs_phase_passed, checks, timestamps_result,
    roadmap_sync_result; status=\"error\" on tool failure.

    This helper runs validate() for timestamps and roadmap_sync once, then
    returns a structured JSON result with per-check summaries and raw
    validation outputs. Validation failures keep status=\"success\" but set
    docs_phase_passed=False, while tool-level errors set status=\"error\".
    """
    await log_client(
        ctx,
        "info",
        "run_docs_and_memory_bank_sync: starting docs/memory bank validations",
        logger_name=__name__,
    )

    result = await run_docs_and_memory_bank_sync_impl(ctx=ctx)

    await log_client(
        ctx,
        "info",
        "run_docs_and_memory_bank_sync: completed",
        logger_name=__name__,
    )
    return result


__all__ = ["run_preflight_checks", "run_docs_and_memory_bank_sync"]
