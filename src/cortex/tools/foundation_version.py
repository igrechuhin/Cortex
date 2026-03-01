"""
Version History Tool

This module provides the get_version_history tool for retrieving
version history of Memory Bank files.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers import initialization
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


# Tool consolidated into query_memory_bank (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_version_history(
    file_name: str,
    limit: int = 10,
    ctx: MCPContext | None = None,
) -> str:
    """Get version history for a Memory Bank file.

    USE WHEN: User asks about file history, user needs to see previous
    versions, user wants to track changes to a file, user requests version
    information.

    EXAMPLES: 'get version history for projectBrief.md', 'show changes to
    activeContext.md', 'what versions exist for roadmap.md'.

    RETURNS: JSON array of version objects with timestamps, change
    descriptions, and version numbers.

    Returns list of versions with timestamps, change types, and descriptions.
    Versions are sorted by version number in descending order (newest first).

    Args:
        file_name: Name of the file (e.g., "projectBrief.md")
        limit: Maximum number of versions to return (default: 10, max: 100)

    Returns:
        JSON string with version history containing version numbers,
        timestamps, change types, descriptions, file sizes, and token counts.

    Example (Success):
        ```json
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "total_versions": 5,
          "versions": [
            {
              "version": 5,
              "timestamp": "2026-01-04T10:30:00",
              "change_type": "update",
              "change_description": "Added new feature requirements",
              "size_bytes": 2048,
              "token_count": 512
            },
            {
              "version": 4,
              "timestamp": "2026-01-03T14:20:00",
              "change_type": "rollback",
              "change_description": "Rolled back to version 3",
              "size_bytes": 1950,
              "token_count": 490
            }
          ]
        }
        ```

    Example (Error - file not found):
        ```json
        {
          "status": "error",
          "error": "File 'missing.md' not found in memory bank",
          "error_type": "FileNotFoundError"
        }
        ```

    Note:
        Version history is stored in .cortex/history/ and includes
        automatic snapshots created on each file modification.
    """
    await log_client(ctx, "info", "get_version_history: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        out = await _get_version_history_impl(file_name, root, limit, ctx)
        await log_client(
            ctx, "info", "get_version_history: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"get_version_history: failed: {e}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.resource(uri="cortex://memory-bank/version-history/{file_name}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_version_history_resource(file_name: str) -> str:
    """Resource: Version history for a file. Read via cortex://memory-bank/version-history/{file_name}."""
    return await get_version_history(file_name=file_name, limit=10)


async def _get_version_history_impl(
    file_name: str,
    root: Path,
    limit: int,
    ctx: MCPContext | None,
) -> str:
    """Load version history and return JSON string."""
    file_meta = await _get_file_metadata_for_history(file_name, root)
    if not file_meta:
        await log_client(
            ctx, "warning", f"get_version_history: file '{file_name}' not found"
        )
        return json.dumps(
            {"status": "error", "error": f"File '{file_name}' not found in index"},
            indent=2,
        )
    version_history = extract_version_history(file_meta)
    sorted_history = sort_and_limit_versions(version_history, limit)
    versions = format_versions_for_export(sorted_history)
    return json.dumps(
        {
            "status": "success",
            "file_name": file_name,
            "versions": versions,
            "total_versions": len(versions),
        },
        indent=2,
    )


async def _get_file_metadata_for_history(
    file_name: str, root: Path
) -> ModelDict | None:
    """Get file metadata for version history.

    Args:
        file_name: Name of the file
        root: Project root path

    Returns:
        File metadata dict or None if not found
    """
    mgrs = await initialization.get_managers(root)
    metadata_index = await get_manager(mgrs, "index", MetadataIndex)
    file_meta = await metadata_index.get_file_metadata(file_name)
    return cast(
        ModelDict | None,
        file_meta.model_dump(mode="json") if file_meta else None,
    )


def extract_version_history(file_meta: ModelDict) -> list[ModelDict]:
    """Extract version history list from dict-shaped file metadata."""
    history_raw = file_meta.get("version_history", [])
    if not isinstance(history_raw, list):
        return []
    return [cast(ModelDict, item) for item in history_raw if isinstance(item, dict)]


def sort_and_limit_versions(
    version_list: list[ModelDict], limit: int
) -> list[ModelDict]:
    """Sort dict versions by version number (desc) and apply limit."""
    with_version: list[ModelDict] = []
    without_version: list[ModelDict] = []
    for item in version_list:
        version = item.get("version")
        if isinstance(version, (int, float)):
            with_version.append(item)
        else:
            without_version.append(item)

    sorted_with_version = sorted(
        with_version,
        key=lambda v: cast(float, v.get("version", 0.0)),
        reverse=True,
    )
    combined = [*sorted_with_version, *without_version]
    return combined[: max(0, int(limit))]


def format_versions_for_export(
    sorted_history: list[ModelDict],
) -> list[ModelDict]:
    """Format dict versions for export with defaults."""
    exported: list[ModelDict] = []
    for version_meta in sorted_history:
        version_raw = version_meta.get("version")
        timestamp_raw = version_meta.get("timestamp")
        if not isinstance(version_raw, (int, float)) or not isinstance(
            timestamp_raw, str
        ):
            continue

        out: ModelDict = {
            "version": version_raw,
            "timestamp": timestamp_raw,
            "change_type": (
                version_meta.get("change_type", "unknown")
                if isinstance(version_meta.get("change_type"), str)
                else "unknown"
            ),
        }
        change_description = version_meta.get("change_description")
        if isinstance(change_description, str) and change_description:
            out["change_description"] = change_description

        size_bytes = version_meta.get("size_bytes")
        if isinstance(size_bytes, int):
            out["size_bytes"] = size_bytes

        token_count = version_meta.get("token_count")
        if isinstance(token_count, int):
            out["token_count"] = token_count

        exported.append(out)

    return exported
