"""Tool search for deferred tool discovery (Phase 49).

When tool_search is enabled, clients receive only always_loaded tools initially.
This tool allows discovering deferred tools by query (regex over name and rationale).
"""

from __future__ import annotations

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp
from cortex.tools.categories import (
    ToolCategory,
    ToolCategoryName,
    get_tools_by_category,
    search_deferred_tools,
)


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=read_only_annotations(
        "Search Deferred Tools",
        idempotent=True,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def search_tools(
    query: str,
    category: str | None = None,
    limit: int = 20,
) -> str:
    """Search deferred tools by query (case-insensitive substring over name and rationale).

    USE WHEN: User wants to find a deferred tool by name or purpose,
    user needs to discover tools when tool search (defer_loading) is enabled.

    EXAMPLES: 'search_tools(query="refactor")', 'search_tools(query="usage", category="deferred_low")'.

    RETURNS: JSON with status, query, and matches (name, category, rationale per tool).

    Args:
        query: Search string (matched case-insensitively against tool name and rationale).
        category: Optional filter: "deferred_medium" or "deferred_low".
        limit: Maximum number of results (default 20).

    Returns:
        JSON string with status, query, and list of matches.

    Example:
        >>> search_tools(query="refactor", limit=5)
        {"status": "success", "query": "refactor", "count": 2, "tools": [
          {"name": "apply_refactoring", "category": "deferred_medium", "rationale": "Apply refactoring..."},
          {"name": "suggest_refactoring", "category": "deferred_low", "rationale": "Suggest refactoring..."}
        ]}
    """
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50
    cat: ToolCategoryName | None = (
        ToolCategoryName(category)
        if category in ("deferred_medium", "deferred_low")
        else None
    )
    matches = search_deferred_tools(query, category=cat, limit=limit)
    return json.dumps(
        {
            "status": "success",
            "query": query,
            "count": len(matches),
            "tools": [
                {
                    "name": m.name,
                    "category": m.category.value,
                    "rationale": m.rationale,
                }
                for m in matches
            ],
        },
        indent=2,
    )


def _list_tools_invalid_category(category: str) -> str:
    """Return error JSON for invalid category."""
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid category: {category!r}. Use always_loaded, deferred_medium, or deferred_low.",
        },
        indent=2,
    )


def _list_tools_by_category_all() -> str:
    """Build JSON for list_available_tools when no category filter."""
    by_category: dict[str, list[dict[str, str]]] = {}
    summary: dict[str, int] = {}
    for cat in ToolCategory:
        entries = get_tools_by_category(cat)
        by_category[cat.value] = [
            {"name": e.name, "rationale": e.rationale} for e in entries
        ]
        summary[cat.value] = len(entries)
    return json.dumps(
        {"status": "success", "by_category": by_category, "summary": summary},
        indent=2,
    )


# Internalized for tool budget reduction (2026-02-26). Use search_tools for discovery.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_available_tools(
    category: str | None = None,
) -> str:
    """List MCP tools by loading tier (core vs extended).

    USE WHEN: Agent wants to discover which tools exist, or filter by
    category (always_loaded, deferred_medium, deferred_low).

    EXAMPLES: list_available_tools(), list_available_tools(category="always_loaded").

    RETURNS: JSON with status and tools (name, category, rationale). If category
    is omitted, returns all tools grouped by category and a summary count.

    Args:
        category: Optional filter: "always_loaded", "deferred_medium", or "deferred_low".
            If None, returns all tools with by_category and summary.

    Returns:
        JSON string with status and tool list or by_category map.

    Example (no category — all tools):
        >>> list_available_tools()
        {"status": "success", "by_category": {"always_loaded": [{"name": "session_start", "rationale": "..."}], ...}, "summary": {"always_loaded": 25, "deferred_medium": 30, "deferred_low": 46}}

    Example (with category):
        >>> list_available_tools(category="always_loaded")
        {"status": "success", "category": "always_loaded", "count": 25, "tools": [{"name": "session_start", "category": "always_loaded", "rationale": "..."}, ...]}
    """
    if category is not None and category not in (
        "always_loaded",
        "deferred_medium",
        "deferred_low",
    ):
        return _list_tools_invalid_category(category)
    if category is not None:
        cat = ToolCategory(category)
        entries = get_tools_by_category(cat)
        return json.dumps(
            {
                "status": "success",
                "category": category,
                "count": len(entries),
                "tools": [
                    {
                        "name": e.name,
                        "category": e.category.value,
                        "rationale": e.rationale,
                    }
                    for e in entries
                ],
            },
            indent=2,
        )
    return _list_tools_by_category_all()
