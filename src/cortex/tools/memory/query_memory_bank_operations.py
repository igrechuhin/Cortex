"""Unified Memory Bank query tool (Phase 50).

Single entry point for stats, version history, dependency graph, link graph,
parse links, validate links, and resolve transclusions.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.server import mcp


class QueryMemoryBankParams(BaseModel):
    """Parameters for query_memory_bank dispatch; all query types use a subset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_name: str | None = None
    limit: int = 10
    format: str = "json"
    include_transclusions: bool = True
    max_depth: int = 5
    include_token_budget: bool = True
    include_refactoring_history: bool = False
    refactoring_days: int = 90
    response_format: ResponseFormat = ResponseFormat.CONCISE


def _error_payload(message: str) -> str:
    """Return a JSON error payload."""
    return json.dumps(
        {"status": "error", "error": message, "error_type": "ValueError"},
        indent=2,
    )


async def _run_stats(params: QueryMemoryBankParams, ctx: MCPContext | None) -> str:
    from cortex.tools.memory.foundation_stats import get_memory_bank_stats

    return await get_memory_bank_stats(
        include_token_budget=params.include_token_budget,
        include_refactoring_history=params.include_refactoring_history,
        refactoring_days=params.refactoring_days,
        response_format=params.response_format,
        ctx=ctx,
    )


async def _run_version_history(
    params: QueryMemoryBankParams, ctx: MCPContext | None
) -> str:
    if not params.file_name:
        return _error_payload("file_name is required for query_type=version_history")
    from cortex.tools.memory.foundation_version import get_version_history

    return await get_version_history(
        file_name=params.file_name,
        limit=params.limit,
        ctx=ctx,
    )


async def _run_dependency_graph(
    params: QueryMemoryBankParams, ctx: MCPContext | None
) -> str:
    from cortex.tools.memory.foundation_dependency import get_dependency_graph

    return await get_dependency_graph(format=params.format, ctx=ctx)


async def _run_link_graph(params: QueryMemoryBankParams, ctx: MCPContext | None) -> str:
    from cortex.tools.linking.graph_operations import get_link_graph

    return await get_link_graph(
        include_transclusions=params.include_transclusions,
        format=params.format,
        ctx=ctx,
    )


async def _run_parse_links(
    params: QueryMemoryBankParams, ctx: MCPContext | None
) -> str:
    if not params.file_name:
        return _error_payload("file_name is required for query_type=parse_links")
    from cortex.tools.linking.parser_operations import parse_file_links

    return await parse_file_links(file_name=params.file_name, ctx=ctx)


async def _run_validate_links(
    params: QueryMemoryBankParams, ctx: MCPContext | None
) -> str:
    if not params.file_name:
        return _error_payload("file_name is required for query_type=validate_links")
    from cortex.tools.linking.validation_operations import validate_links

    return await validate_links(file_name=params.file_name, ctx=ctx)


async def _run_resolve_transclusions(
    params: QueryMemoryBankParams, ctx: MCPContext | None
) -> str:
    if not params.file_name:
        return _error_payload(
            "file_name is required for query_type=resolve_transclusions"
        )
    from cortex.tools.linking.transclusion_operations import resolve_transclusions

    return await resolve_transclusions(
        file_name=params.file_name,
        max_depth=params.max_depth,
        ctx=ctx,
    )


_Handler = Callable[[QueryMemoryBankParams, MCPContext | None], Awaitable[str]]
_MEMORY_BANK_HANDLERS: dict[str, _Handler] = {
    "stats": _run_stats,
    "version_history": _run_version_history,
    "dependency_graph": _run_dependency_graph,
    "link_graph": _run_link_graph,
    "parse_links": _run_parse_links,
    "validate_links": _run_validate_links,
    "resolve_transclusions": _run_resolve_transclusions,
}


@contextmanager
def replace_handler_for_test(query_type: str, handler: _Handler):
    """Temporarily replace a handler for testing. Restores on exit."""
    original = _MEMORY_BANK_HANDLERS[query_type]
    _MEMORY_BANK_HANDLERS[query_type] = handler
    try:
        yield
    finally:
        _MEMORY_BANK_HANDLERS[query_type] = original


def _build_memory_bank_params(
    file_name: str | None,
    limit: int,
    format: str,
    include_transclusions: bool,
    max_depth: int,
    include_token_budget: bool,
    include_refactoring_history: bool,
    refactoring_days: int,
    response_format: ResponseFormat,
) -> QueryMemoryBankParams:
    """Build params model for memory bank query."""
    return QueryMemoryBankParams(
        file_name=file_name,
        limit=limit,
        format=format,
        include_transclusions=include_transclusions,
        max_depth=max_depth,
        include_token_budget=include_token_budget,
        include_refactoring_history=include_refactoring_history,
        refactoring_days=refactoring_days,
        response_format=response_format,
    )


async def _query_memory_bank_impl(
    query_type: str,
    params: QueryMemoryBankParams,
    ctx: MCPContext | None,
) -> str:
    """Dispatch to the handler for query_type; catch and return errors as JSON."""
    handler = _MEMORY_BANK_HANDLERS.get(query_type)
    if handler is None:
        return _error_payload(f"Unknown query_type: {query_type}")
    try:
        return await handler(params, ctx)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Query Memory Bank"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def query_memory_bank(
    query_type: str,
    file_name: str | None = None,
    limit: int = 10,
    format: str = "json",
    include_transclusions: bool = True,
    max_depth: int = 5,
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
    response_format: str = "concise",
    ctx: MCPContext | None = None,
) -> str:
    """Query Memory Bank for stats, version history, graphs, links, or transclusions.

    USE WHEN: User needs memory bank stats, version history, dependency/link
    graph, link parsing/validation, or transclusion resolution.

    EXAMPLES: 'query_memory_bank(query_type="stats")', 'get memory bank stats',
    'query_memory_bank(query_type="version_history", file_name="roadmap.md")',
    'get link graph', 'validate links in activeContext.md'.

    DO NOT:
    - Use this tool to mutate Memory Bank content; it is strictly read-only.
      For writes, use manage_file or update_memory_bank instead.
    - Treat this as a generic text search over the repository; it operates on
      Memory Bank metadata and link structures only.

    RETURNS: JSON (or format) with result for query_type: stats,
    version_history, dependency_graph, link_graph, parse_links,
    validate_links, resolve_transclusions.

    Args:
        query_type: stats, version_history, dependency_graph, link_graph,
            parse_links, validate_links, or resolve_transclusions.
        file_name: Optional file for version_history, parse_links, etc.
        limit, format, include_transclusions: Query-specific options.
    """
    await log_client(
        ctx,
        "info",
        f"query_memory_bank: starting query_type={query_type}",
        logger_name=__name__,
    )
    params = _build_memory_bank_params(
        file_name,
        limit,
        format,
        include_transclusions,
        max_depth,
        include_token_budget,
        include_refactoring_history,
        refactoring_days,
        ResponseFormat(response_format),
    )
    return await _query_memory_bank_impl(query_type, params, ctx)
