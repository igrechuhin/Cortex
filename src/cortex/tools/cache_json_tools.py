"""
Cache JSON Tools

Single MCP tool cache_json(operation="read"|"write") for concurrent-safe
read/write of JSON files under .cortex/.cache. Agents MUST use this tool
(not direct file access) when reading or writing cache JSON so that
multiple chat sessions do not corrupt data. Consolidated to keep tool
count within MAX_REGISTERED_TOOLS without raising the limit.
"""

import json
from pathlib import Path
from typing import Literal, cast

from cortex.core.cache_json_access import (
    read_cache_json as _read_cache_json,
)
from cortex.core.cache_json_access import (
    write_cache_json as _write_cache_json,
)
from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp


def _parse_write_content(
    content: str,
) -> tuple[dict[str, object] | list[object] | None, str | None]:
    """Parse content as JSON object/array. Returns (payload, None) or (None, error_message)."""
    try:
        data = json.loads(content)
        if not isinstance(data, (dict, list)):
            return (None, "Content must be a JSON object or array")
        if isinstance(data, dict):
            payload: dict[str, object] | list[object] = {
                str(k): v for k, v in cast(dict[str, object], data).items()
            }
        else:
            payload = list(cast(list[object], data))
        return (payload, None)
    except json.JSONDecodeError as e:
        return (None, f"Invalid JSON: {e!s}")


def parse_write_content(
    content: str,
) -> tuple[dict[str, object] | list[object] | None, str | None]:
    """Public wrapper around _parse_write_content for testing and callers."""
    return _parse_write_content(content)


def _error_response(
    message: str,
    relative_path: str,
    error_type: str | None = None,
) -> str:
    """Build JSON error response for cache tool."""
    out: dict[str, object] = {
        "status": "error",
        "message": message,
        "relative_path": relative_path,
    }
    if error_type:
        out["error_type"] = error_type
    return json.dumps(out, indent=2)


def error_response(
    message: str,
    relative_path: str,
    error_type: str | None = None,
) -> str:
    """Public wrapper around _error_response for testing and callers."""
    return _error_response(message, relative_path, error_type)


async def _cache_json_read(root: Path, relative_path: str) -> str:
    """Perform cache read; return JSON string."""
    try:
        data = await _read_cache_json(root, relative_path)
        if data is None:
            return json.dumps({"status": "missing", "relative_path": relative_path})
        return json.dumps(data, indent=2)
    except ValueError as e:
        return json.dumps(
            {"status": "error", "message": str(e), "relative_path": relative_path},
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": str(e),
                "error_type": type(e).__name__,
                "relative_path": relative_path,
            },
            indent=2,
        )


async def _cache_json_write(root: Path, relative_path: str, content: str) -> str:
    """Perform cache write; return JSON string."""
    if not content.strip():
        return _error_response(
            "content required when operation is write", relative_path
        )
    try:
        payload, err_msg = _parse_write_content(content)
        if err_msg is not None:
            return _error_response(err_msg, relative_path)
        if payload is None:
            return _error_response(
                "Content must be a JSON object or array", relative_path
            )
        await _write_cache_json(root, relative_path, payload)
        return json.dumps(
            {"status": "success", "relative_path": relative_path}, indent=2
        )
    except ValueError as e:
        return _error_response(str(e), relative_path)
    except Exception as e:
        return _error_response(str(e), relative_path, type(e).__name__)


@mcp.tool(annotations=safe_write_annotations("Cache JSON (read/write)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def cache_json(
    operation: Literal["read", "write"],
    relative_path: str,
    content: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Read or write a JSON file under .cortex/.cache with concurrent-safe locking.

    USE WHEN: You need to read or write any JSON under .cortex/.cache (e.g.
    usage events, markdown-lint index, session handoff). Do NOT access
    cache JSON files directly; use this tool so access is serialized.

    EXAMPLES: cache_json(operation="read", relative_path="usage/events/2026-02-24.json"),
    cache_json(operation="write", relative_path="session/last_handoff.json", content="{}").

    RETURNS: For read — JSON string (file content) or {"status":"missing"|"error",...}.
    For write — {"status":"success"} or {"status":"error",...}.

    Args:
        operation: "read" to load file content, "write" to save content.
        relative_path: Path under .cortex/.cache (e.g. "usage/events/2026-02-02.json").
            No leading slash, no "..".
        content: Required when operation is "write"; JSON string (object or array).
        ctx: MCP context (automatically provided).

    Returns:
        JSON string: for read, file content or status; for write, success or error.
    """
    if ctx is not None:
        await log_client(ctx, "debug", f"cache_json({operation}): starting")
    root = await resolve_project_root_async(None, ctx)
    if operation == "read":
        return await _cache_json_read(root, relative_path)
    if operation == "write":
        return await _cache_json_write(root, relative_path, content or "")
    return _error_response(f"Unknown operation: {operation}", relative_path)
