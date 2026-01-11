"""
Version History Tool

This module provides the get_version_history tool for retrieving
version history of Memory Bank files.
"""

import json
from typing import cast

from cortex.core.metadata_index import MetadataIndex
from cortex.managers.initialization import get_managers, get_project_root
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
) -> dict[str, object] | None:
    """Get file metadata for version history.

    Args:
        file_name: Name of the file
        project_root: Optional path to project root

    Returns:
        File metadata dictionary or None if not found
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    metadata_index = cast(MetadataIndex, mgrs["index"])
    return await metadata_index.get_file_metadata(file_name)


def extract_version_history(file_meta: dict[str, object]) -> list[dict[str, object]]:
    """Extract version history list from file metadata.

    Args:
        file_meta: File metadata dictionary

    Returns:
        List of version dictionaries
    """
    version_history_raw = file_meta.get("version_history", [])
    if not isinstance(version_history_raw, list):
        return []

    version_list: list[dict[str, object]] = []
    version_history_list = cast(list[object], version_history_raw)
    for version_item_raw in version_history_list:
        if isinstance(version_item_raw, dict):
            version_item: dict[str, object] = cast(dict[str, object], version_item_raw)
            version_list.append(version_item)
    return version_list


def sort_and_limit_versions(
    version_list: list[dict[str, object]], limit: int
) -> list[dict[str, object]]:
    """Sort versions by version number and limit results.

    Args:
        version_list: List of version dictionaries
        limit: Maximum number of versions to return

    Returns:
        Sorted and limited version list
    """

    def get_version(v: dict[str, object]) -> int:
        version_val = v.get("version", 0)
        if isinstance(version_val, (int, float)):
            return int(version_val)
        return 0

    return sorted(version_list, key=get_version, reverse=True)[:limit]


def format_versions_for_export(
    sorted_history: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Format versions for export.

    Args:
        sorted_history: Sorted list of version dictionaries

    Returns:
        Formatted list of version dictionaries
    """
    versions: list[dict[str, object]] = []
    for version_meta in sorted_history:
        formatted: dict[str, object] = {
            "version": version_meta.get("version", 0),
            "timestamp": str(version_meta.get("timestamp", "")),
            "change_type": str(version_meta.get("change_type", "unknown")),
        }
        if "change_description" in version_meta:
            formatted["change_description"] = version_meta["change_description"]
        if "size_bytes" in version_meta:
            formatted["size_bytes"] = version_meta["size_bytes"]
        if "token_count" in version_meta:
            formatted["token_count"] = version_meta["token_count"]
        versions.append(formatted)
    return versions
