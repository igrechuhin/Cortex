#!/usr/bin/env python3
"""MCP server instance for Cortex."""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.prompts.base import Prompt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.transforms import Transform
from fastmcp.server.transforms.prompts_as_tools import PromptsAsTools
from fastmcp.server.transforms.resources_as_tools import ResourcesAsTools

from cortex.server_middleware import create_server_middleware


def _extract_client_name(ctx: object) -> str:
    """Extract client name from FastMCP auth context when available."""
    direct_client = getattr(ctx, "client_info", None)
    if direct_client is not None:
        direct_name = getattr(direct_client, "name", None)
        if isinstance(direct_name, str):
            return direct_name.lower()
    session = getattr(ctx, "session", None)
    client_params = getattr(session, "client_params", None)
    for attr_name in ("client_info", "clientInfo"):
        info_obj = getattr(client_params, attr_name, None)
        if info_obj is None:
            continue
        info_name = getattr(info_obj, "name", None)
        if isinstance(info_name, str):
            return info_name.lower()
    return ""


def _is_trusted_client_name(client_name: str) -> bool:
    trusted_prefixes = (
        "cortex",
        "codex",
        "claude",
    )
    return any(client_name.startswith(prefix) for prefix in trusted_prefixes)


def cortex_agent_only_auth(ctx: object) -> bool:
    """Allow trusted agent clients for write-sensitive operations."""
    return _is_trusted_client_name(_extract_client_name(ctx))


def ingest_caller_auth(ctx: object) -> bool:
    """Allow trusted agents and commit-pipeline callers for ingest operations."""
    client_name = _extract_client_name(ctx)
    return _is_trusted_client_name(client_name) or "commit" in client_name


def build_transforms_for_tool_compat() -> list[Transform]:
    config_path = Path.cwd() / ".cortex" / "config" / "optimization.json"
    config: dict[str, object] = {}
    if config_path.exists():
        try:
            raw: object = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config = cast(dict[str, object], raw)
        except (OSError, ValueError):
            config = {}
    tool_compat_cfg_obj = config.get("tool_compat")
    tool_compat_cfg = (
        cast(dict[str, object], tool_compat_cfg_obj)
        if isinstance(tool_compat_cfg_obj, dict)
        else {}
    )
    transforms: list[Transform] = []
    if bool(tool_compat_cfg.get("expose_resources_as_tools", False)):
        transforms.append(cast(Transform, ResourcesAsTools))
    if bool(tool_compat_cfg.get("expose_prompts_as_tools", False)):
        transforms.append(cast(Transform, PromptsAsTools))
    return transforms


@asynccontextmanager
async def server_lifespan(_server: FastMCP):
    # AI: Keep one-time DI setup in server lifespan so every run path is consistent.
    from cortex.tools.session.sequential_thinking import (
        SequentialThinkingCore,
        configure_sequential_thinking_core,
    )

    configure_sequential_thinking_core(SequentialThinkingCore())
    yield


mcp = FastMCP(
    "cortex",
    lifespan=server_lifespan,
    transforms=build_transforms_for_tool_compat(),
)


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
