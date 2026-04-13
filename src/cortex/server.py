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

from fastmcp import FastMCP
from mcp.types import ListPromptsRequest, RootsListChangedNotification, ServerResult

from cortex.core.project_root_resolver import handle_roots_list_changed

# FastMCP server instance (framework requirement)
# This is an acceptable exception to the no-global-state rule
mcp = FastMCP("cortex")


# ---------------------------------------------------------------------------
# Lazy-registration hook
#
# The MCP protocol calls ``list_prompts`` on every client request for the
# prompt list.  We intercept the *low-level request handler* (the entry in
# ``mcp._mcp_server.request_handlers``) to trigger lazy prompt registration
# on the first call.  Replacing ``mcp.list_prompts`` (the FastMCP method)
# does NOT work: FastMCP captures a bound-method reference to
# ``FastMCP.list_prompts`` in a closure when ``_setup_handlers()`` runs at
# ``__init__`` time, so a later attribute assignment on the instance is
# invisible to the already-registered low-level handler.
# ---------------------------------------------------------------------------

_original_list_prompts_handler = mcp._mcp_server.request_handlers[  # type: ignore[index]
    ListPromptsRequest
]


async def _lazy_list_prompts_handler(req: ListPromptsRequest) -> ServerResult:
    """Low-level list_prompts handler that triggers lazy registration first."""
    from cortex.setup.lazy_prompt_registration import ensure_prompts_registered

    await ensure_prompts_registered(None)
    return await _original_list_prompts_handler(req)  # type: ignore[arg-type]


mcp._mcp_server.request_handlers[ListPromptsRequest] = _lazy_list_prompts_handler  # type: ignore[index]


async def _roots_list_changed_notification_handler(
    _notification: RootsListChangedNotification,
) -> None:
    """Invalidate cached MCP root when the client sends roots/list_changed."""
    await handle_roots_list_changed()


mcp._mcp_server.notification_handlers[RootsListChangedNotification] = (  # type: ignore[index]
    _roots_list_changed_notification_handler
)
