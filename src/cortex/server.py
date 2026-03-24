#!/usr/bin/env python3
"""MCP server instance for Cortex.

This module provides the FastMCP server instance. While this is technically
global state, it's an acceptable exception as:
1. The FastMCP framework requires a module-level server for tool registration
2. MCP tools are stateless functions that only use this for routing
3. The server itself doesn't hold application state - managers are injected

For proper dependency injection in your own code, use ManagerRegistry instead
of relying on global state.

Deferred tool loading (Phase 49): When tool_search.enabled is true in
.cortex/config/optimization.json, categorization is used by the search_tools
tool for discovery. Full list_tools filtering requires MCP SDK support for
defer_loading; until then, all tools are registered and search_tools allows
clients to discover deferred tools by query.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import Prompt as MCPPrompt

# FastMCP server instance (framework requirement)
# This is an acceptable exception to the no-global-state rule
mcp = FastMCP("cortex")


# ---------------------------------------------------------------------------
# Lazy-registration hook
#
# FastMCP calls ``list_prompts()`` on every client request for the prompt list.
# We intercept it to trigger :mod:`cortex.setup.lazy_prompt_registration` on
# the *first* call, which resolves the correct project root via the MCP
# ``roots/list`` capability and registers synapse / setup prompts with that
# root.  All subsequent calls hit the short-circuit ``_registered`` flag and
# pay only a single attribute lookup.
# ---------------------------------------------------------------------------


_list_prompts_original = mcp.list_prompts


async def _list_prompts_with_lazy_registration() -> list[MCPPrompt]:
    """Wrap FastMCP list_prompts to trigger lazy prompt registration on first call."""
    from cortex.core.context_logging import MCPContext
    from cortex.setup.lazy_prompt_registration import ensure_prompts_registered

    ctx: MCPContext | None
    try:
        ctx = mcp.get_context()  # type: ignore[assignment]
    except Exception:
        ctx = None

    await ensure_prompts_registered(ctx)
    return await _list_prompts_original()


mcp.list_prompts = _list_prompts_with_lazy_registration  # type: ignore[method-assign]
