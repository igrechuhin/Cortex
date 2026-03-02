"""Handlers and dispatch for manage_session_scripts consolidated tool."""

import json
from collections.abc import Awaitable, Callable
from typing import cast

from cortex.core.context_logging import MCPContext


async def _session_scripts_capture_handler(
    *,
    script_path: str | None = None,
    script_content: str | None = None,
    task_description: str | None = None,
    script_type: str = "python",
    purpose: str = "utility",
    ctx: MCPContext | None = None,
    **_: object,
) -> str:
    if script_path is None or script_content is None or task_description is None:
        error_payload = {
            "status": "error",
            "error": (
                "script_path, script_content, and task_description are required for "
                "operation 'capture'"
            ),
        }
        return json.dumps(error_payload, indent=2)
    from cortex.tools.session.script_capture_tools import capture_session_script

    return await capture_session_script(
        script_path=script_path,
        script_content=script_content,
        task_description=task_description,
        script_type=script_type,
        purpose=purpose,
        ctx=ctx,
    )


async def _session_scripts_list_handler(
    *,
    ctx: MCPContext | None = None,
    **_: object,
) -> str:
    from cortex.tools.session.script_capture_tools import list_session_scripts

    return await list_session_scripts(ctx=ctx)


async def _session_scripts_analyze_handler(
    *,
    ctx: MCPContext | None = None,
    **_: object,
) -> str:
    from cortex.tools.session.script_capture_tools import analyze_session_scripts

    return await analyze_session_scripts(ctx=ctx)


async def _session_scripts_suggest_handler(
    *,
    task_description: str | None = None,
    max_results: int = 15,
    ctx: MCPContext | None = None,
    **_: object,
) -> str:
    if task_description is None:
        error_payload = {
            "status": "error",
            "error": "task_description is required for operation 'suggest'",
        }
        return json.dumps(error_payload, indent=2)
    from cortex.tools.session.script_capture_tools import suggest_tool_improvements

    return await suggest_tool_improvements(
        task_description=task_description,
        max_results=max_results,
        ctx=ctx,
    )


async def _session_scripts_promote_handler(
    *,
    script_id: str | None = None,
    output_type: str = "tool",
    ctx: MCPContext | None = None,
    **_: object,
) -> str:
    if script_id is None:
        error_payload = {
            "status": "error",
            "error": "script_id is required for operation 'promote'",
        }
        return json.dumps(error_payload, indent=2)
    from cortex.tools.session.script_capture_tools import promote_session_script

    return await promote_session_script(
        script_id=script_id,
        output_type=output_type,
        ctx=ctx,
    )


_SESSION_SCRIPTS_HANDLERS: dict[str, Callable[..., Awaitable[str]]] = {
    "capture": cast(Callable[..., Awaitable[str]], _session_scripts_capture_handler),
    "list": cast(Callable[..., Awaitable[str]], _session_scripts_list_handler),
    "analyze": cast(Callable[..., Awaitable[str]], _session_scripts_analyze_handler),
    "suggest": cast(Callable[..., Awaitable[str]], _session_scripts_suggest_handler),
    "promote": cast(Callable[..., Awaitable[str]], _session_scripts_promote_handler),
}


async def dispatch_session_scripts(
    operation: str,
    script_path: str | None,
    script_content: str | None,
    task_description: str | None,
    script_type: str,
    purpose: str,
    script_id: str | None,
    max_results: int,
    output_type: str,
    ctx: MCPContext | None,
) -> str:
    """Route manage_session_scripts operation to the appropriate handler."""
    handler = _SESSION_SCRIPTS_HANDLERS.get(operation.lower())
    if handler is None:
        error_message = (
            f"Unsupported operation '{operation}'. "
            + "Expected one of: capture, list, analyze, suggest, promote."
        )
        return json.dumps({"status": "error", "error": error_message}, indent=2)

    kwargs = {
        "script_path": script_path,
        "script_content": script_content,
        "task_description": task_description,
        "script_type": script_type,
        "purpose": purpose,
        "script_id": script_id,
        "max_results": max_results,
        "output_type": output_type,
        "ctx": ctx,
    }
    return await handler(**kwargs)
