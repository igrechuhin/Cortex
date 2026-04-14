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

from collections.abc import Sequence

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.prompts.base import Prompt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

# FastMCP server instance (framework requirement)
# This is an acceptable exception to the no-global-state rule
mcp = FastMCP("cortex")


# ---------------------------------------------------------------------------
# Lazy-registration middleware
#
# FastMCP v3 routes `prompts/list` requests through the registered middleware
# chain before calling the actual list handler.  We use `on_list_prompts` to
# trigger lazy prompt registration on the first call.
#
# This replaces the previous approach of patching low-level request handler
# maps directly, which relied on FastMCP internals and type suppressions.
# ---------------------------------------------------------------------------


class _LazyPromptsMiddleware(Middleware):
    """Trigger lazy prompt registration before each prompts/list response."""

    async def on_list_prompts(
        self,
        context: MiddlewareContext[mt.ListPromptsRequest],
        call_next: CallNext[mt.ListPromptsRequest, Sequence[Prompt]],
    ) -> Sequence[Prompt]:
        from cortex.setup.lazy_prompt_registration import ensure_prompts_registered

        await ensure_prompts_registered(None)
        return await call_next(context)


mcp.add_middleware(_LazyPromptsMiddleware())
