"""In-process tool session exposing Cortex's registered tools to the model.

The agentic eval measures whether a tool's *registered* name, description, and
parameter schema are enough for a model to pick it, so schemas are read from
the live FastMCP registration rather than from a hand-maintained list.

Execution is deliberately best-effort: for a selection eval what matters is
which tool the model chose, not that the call succeeded, so tools without a
registered eval invoker return an explanatory string instead of raising.
"""

from __future__ import annotations

import importlib
from typing import cast

from fastmcp.tools import Tool

from ._agentic_models import ModelToolSchema

UNAVAILABLE_TEMPLATE = (
    "tool '{name}' is not executable in the evaluation sandbox; "
    "its selection has been recorded"
)


def to_tool_schema(tool: Tool) -> ModelToolSchema:
    """Project one registered FastMCP tool onto the model-facing schema."""
    return ModelToolSchema(
        name=tool.name,
        description=tool.description or "",
        input_schema=dict(tool.parameters or {}),
    )


async def load_registered_tool_schemas() -> list[ModelToolSchema]:
    """Read every visible Cortex MCP tool schema from the live server.

    ``list_tools()`` returns a *list* of tool objects and applies the server's
    visibility filtering, so it yields exactly the surface a client actually
    sees. Tools gated behind an authenticated context are therefore absent when
    this runs without one; ``missing_published_tools`` reports that gap and
    ``select_agentic_tasks`` drops tasks whose tools are not exposed, rather
    than scoring them against a surface the model was never shown.
    """
    # AI: imported inside the function so importing this module never pulls in the
    # whole server and its @mcp.tool registrations as an import side effect.
    from cortex.server import mcp

    # AI: pulled in via importlib rather than a plain import because the module is
    # wanted only for its @mcp.tool registration side effect, and a bound name that
    # nothing reads trips the unused-import check.
    _ = importlib.import_module("cortex.tools")

    tools = await mcp.list_tools()
    schemas = [to_tool_schema(tool) for tool in tools]
    return sorted(schemas, key=lambda schema: schema.name)


def missing_published_tools(schemas: list[ModelToolSchema]) -> list[str]:
    """Published tool names absent from ``schemas`` (visibility-gated tools)."""
    from cortex.discovery.published_inventory import published_inventory_payload

    published = published_inventory_payload()["tool_names"]
    names = cast(list[str], published) if isinstance(published, list) else []
    exposed = {schema.name for schema in schemas}
    return sorted(name for name in names if name not in exposed)


class LocalToolSession:
    """``ToolSessionProtocol`` implementation over the in-process registry."""

    def __init__(self, schemas: list[ModelToolSchema]) -> None:
        self._schemas = schemas

    async def list_tool_schemas(self) -> list[ModelToolSchema]:
        """Return the registered tool schemas exposed to the model."""
        return self._schemas

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        """Invoke a tool when an eval invoker exists; otherwise explain politely."""
        from .evaluation_execution_registry import get_tool_invoker

        invoker = get_tool_invoker(name)
        if invoker is None:
            return UNAVAILABLE_TEMPLATE.format(name=name)
        return await invoker(arguments)


async def build_local_session() -> LocalToolSession:
    """Build a session backed by the live Cortex tool registration."""
    return LocalToolSession(await load_registered_tool_schemas())
