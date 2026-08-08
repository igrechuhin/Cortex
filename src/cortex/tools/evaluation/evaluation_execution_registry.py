"""Registry of tool name -> async invoker for execution-based evals.

Invokers are async callables (arguments: dict) -> str (JSON or text output).
Tools are invoked with ctx=None; they resolve project root via fallback.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

_TOOL_INVOKERS: dict[
    str,
    Callable[[dict[str, object]], Awaitable[str]],
] = {}


def _register_get_structure_info() -> None:
    """Register get_structure_info for execution evals."""
    from cortex.tools.structure import get_structure_info_impl as get_structure_info

    async def invoker(arguments: dict[str, object]) -> str:
        _ = arguments  # get_structure_info takes no args from payload
        return await get_structure_info(ctx=None)

    _TOOL_INVOKERS["get_structure_info"] = invoker


def get_tool_invoker(
    tool_name: str,
) -> Callable[[dict[str, object]], Awaitable[str]] | None:
    """Return the async invoker for tool_name, or None if not registered."""
    if not _TOOL_INVOKERS:
        _register_get_structure_info()
    return _TOOL_INVOKERS.get(tool_name)
