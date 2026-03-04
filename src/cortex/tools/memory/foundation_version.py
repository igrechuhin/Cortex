"""
Version History Tool

This module provides the get_version_history tool for retrieving
version history of Memory Bank files.

Version history is now derived from local `.cortex/history/`
snapshot files instead of being persisted in the tracked
`.cortex/index.json`. The index keeps only current file metadata;
history is local, ephemeral, and computed from disk when needed.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.response_builder import error_response, success_response


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
            error_response(error=str(e), error_type=type(e).__name__),
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
    """Load version history from on-disk snapshots and return JSON string."""
    version_history = _load_version_history_from_disk(file_name, root)
    sorted_history = sort_and_limit_versions(version_history, limit)
    versions = format_versions_for_export(sorted_history)
    return json.dumps(
        success_response(
            file_name=file_name,
            versions=cast(JsonValue, versions),
            total_versions=len(versions),
        ),
        indent=2,
    )


def _load_version_history_from_disk(file_name: str, root: Path) -> list[ModelDict]:
    """Scan `.cortex/history/` for snapshots and build version history."""
    history_dir = get_cortex_path(root, CortexResourceType.HISTORY)
    if not history_dir.exists():
        return []

    base_name = Path(file_name).name
    base_stem = base_name[:-3] if base_name.endswith(".md") else Path(base_name).stem
    pattern = f"{base_stem}_v*.md"

    versions: list[ModelDict] = []
    for snapshot in history_dir.glob(pattern):
        try:
            stat = snapshot.stat()
        except OSError:
            # Snapshot inaccessible; skip it.
            continue

        stem = snapshot.stem
        parts = stem.rsplit("_v", 1)
        if len(parts) != 2:
            continue

        try:
            version_number = int(parts[1])
        except ValueError:
            continue

        versions.append(
            {
                "version": version_number,
                "timestamp": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                "size_bytes": stat.st_size,
            }
        )

    return versions


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
