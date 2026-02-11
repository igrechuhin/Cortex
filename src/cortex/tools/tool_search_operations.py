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
from cortex.tools.tool_categories import search_deferred_tools


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
    """
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50
    cat = category if category in ("deferred_medium", "deferred_low") else None
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
