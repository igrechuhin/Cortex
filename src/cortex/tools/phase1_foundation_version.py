"""
Version History Tool

This module provides the get_version_history tool for retrieving
version history of Memory Bank files.
"""

import json
from typing import cast

from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.managers import initialization
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


@mcp.tool()
async def get_version_history(
    file_name: str, project_root: str | None = None, limit: int = 10
) -> str:
    """Get version history for a Memory Bank file.

    Returns list of versions with timestamps, change types, and descriptions.
    Versions are sorted by version number in descending order (newest first).

    Args:
        file_name: Name of the file (e.g., "projectBrief.md")
        project_root: Optional path to project root directory
        limit: Maximum number of versions to return (default: 10, max: 100)

    Returns:
        JSON string with version history containing version numbers,
        timestamps, change types, descriptions, file sizes, and token counts.

    Example:
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

    Note:
        Version history is stored in .cortex/history/ and includes
        automatic snapshots created on each file modification.
    """
    try:
        file_meta = await _get_file_metadata_for_history(file_name, project_root)
        if not file_meta:
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

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _get_file_metadata_for_history(
    file_name: str, project_root: str | None
) -> ModelDict | None:
    """Get file metadata for version history.

    Args:
        file_name: Name of the file
        project_root: Optional path to project root

    Returns:
        File metadata dict or None if not found
    """
    root = initialization.get_project_root(project_root)
    mgrs = await initialization.get_managers(root)
    metadata_index = await get_manager(mgrs, "index", MetadataIndex)
    file_meta = await metadata_index.get_file_metadata(file_name)
    return cast(ModelDict | None, file_meta)


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
