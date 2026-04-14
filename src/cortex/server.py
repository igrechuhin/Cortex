#!/usr/bin/env python3
"""MCP server instance for Cortex."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.prompts.base import Prompt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from cortex.server_middleware import create_server_middleware

mcp = FastMCP("cortex")


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
for middleware in create_server_middleware(Path.cwd()):
    mcp.add_middleware(middleware)
