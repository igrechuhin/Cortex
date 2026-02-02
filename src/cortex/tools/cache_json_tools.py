"""
Cache JSON Tools

MCP tools for concurrent-safe read/write of JSON files under .cortex/.cache.
Agents MUST use these tools (not direct file access) when reading or writing
cache JSON so that multiple chat sessions do not corrupt data.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.cache_json_access import (
    read_cache_json as _read_cache_json,
)
from cortex.core.cache_json_access import (
    write_cache_json as _write_cache_json,
)
from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations, safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.managers.initialization import get_project_root
from cortex.server import mcp


def _resolve_root(project_root: str | None) -> Path:
    """Resolve project root path."""
    if project_root:
        return Path(project_root).resolve()
    return get_project_root()


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


@mcp.tool(annotations=read_only_annotations("Read Cache JSON"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def read_cache_json(
    relative_path: str,
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Read a JSON file from .cortex/.cache with concurrent-safe locking.

    USE WHEN: You need to read any JSON under .cortex/.cache (e.g. usage
    events, markdown-lint index). Do NOT read cache JSON files directly;
    use this tool so access is serialized across chat sessions.

    relative_path: Path under .cortex/.cache, e.g. "usage/events/2026-02-02.json"
    or "markdown-lint-index.json". No leading slash, no "..".

    Returns: JSON string (file content) or {"status":"error","message":"..."}.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "read_cache_json: starting")
    try:
        root = _resolve_root(project_root)
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


@mcp.tool(annotations=safe_write_annotations("Write Cache JSON"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def write_cache_json(
    relative_path: str,
    content: str,
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Write a JSON file under .cortex/.cache with concurrent-safe locking.

    USE WHEN: You need to write any JSON under .cortex/.cache. Do NOT write
    cache JSON files directly; use this tool so access is serialized.

    relative_path: Path under .cortex/.cache (e.g. "usage/events/2026-02-02.json").
    content: JSON string (object or array).

    Returns: {"status":"success"} or {"status":"error","message":"..."}.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "write_cache_json: starting")
    try:
        root = _resolve_root(project_root)
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
