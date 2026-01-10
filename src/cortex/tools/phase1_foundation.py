"""
Phase 1: Foundation Tools

This module contains the core Memory Bank tools for versioning,
dependency management, and statistics.

Total: 4 tools
- get_dependency_graph
- get_version_history
- rollback_file_version
- get_memory_bank_stats

Note: initialize_memory_bank, check_migration_status, and migrate_memory_bank
have been replaced by prompt templates in docs/prompts/
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.dependency_graph import DependencyGraph, FileDependencyInfo
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.initialization import get_managers, get_project_root
from cortex.server import mcp


@mcp.tool()
async def get_dependency_graph(
    project_root: str | None = None, format: str = "json"
) -> str:
    """Get the Memory Bank dependency graph.

    Shows relationships between files and their loading priority. The graph
    is built from static dependencies (projectBrief → other files) and
    dynamic dependencies (markdown links and transclusions).

    Args:
        project_root: Optional path to project root directory
        format: Output format - "json" or "mermaid" (default: "json")
            - "json": Structured data with files, dependencies, and loading order
            - "mermaid": Mermaid diagram syntax for visualization

    Returns:
        JSON string with dependency graph in requested format.

    Example (JSON format):
        ```json
        {
          "status": "success",
          "format": "json",
          "graph": {
            "files": {
              "projectBrief.md": {
                "priority": 1,
                "dependencies": []
              },
              "activeContext.md": {
                "priority": 2,
                "dependencies": ["projectBrief.md"]
              }
            }
          },
          "loading_order": ["projectBrief.md", "activeContext.md", ...]
        }
        ```

    Example (Mermaid format):
        ```json
        {
          "status": "success",
          "format": "mermaid",
          "diagram": "graph TD\n  projectBrief.md --> activeContext.md\n  ..."
        }
        ```

    Note:
        The loading order is computed using topological sort and respects
        both static priorities and dependency relationships.
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        dep_graph = cast(DependencyGraph, mgrs["graph"])

        if format == "mermaid":
            diagram = dep_graph.to_mermaid()
            return json.dumps(
                {"status": "success", "format": "mermaid", "diagram": diagram}, indent=2
            )
        else:
            graph_data = build_graph_data(dep_graph.static_deps)
            return json.dumps(
                {
                    "status": "success",
                    "format": "json",
                    "graph": graph_data,
                    "loading_order": dep_graph.compute_loading_order(),
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


def build_graph_data(static_deps: dict[str, FileDependencyInfo]) -> dict[str, object]:
    """Build graph data dictionary from static dependencies.

    Args:
        static_deps: Static dependencies dictionary

    Returns:
        Graph data dictionary
    """
    return {
        "files": {
            name: {
                "priority": info.get("priority", 0),
                "dependencies": list(info.get("depends_on", [])),
            }
            for name, info in static_deps.items()
        }
    }


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
        Version history is stored in .memory-bank-history/ and includes
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


@mcp.tool()
async def rollback_file_version(
    file_name: str, version: int, project_root: str | None = None
) -> str:
    """Rollback a Memory Bank file to a previous version.

    Restores content from a snapshot and creates a new version entry.
    This is a safe operation that preserves history - the rollback itself
    becomes a new version, allowing you to undo the rollback if needed.

    Args:
        file_name: Name of the file (e.g., "projectBrief.md")
        version: Version number to rollback to (must exist in history)
        project_root: Optional path to project root directory

    Returns:
        JSON string with rollback status including the new version number
        created by the rollback operation.

    Example (Success):
        ```json
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "rolled_back_from_version": 3,
          "new_version": 6,
          "token_count": 490
        }
        ```

    Example (Error - version not found):
        ```json
        {
          "status": "error",
          "error": "Version 10 not found for 'projectBrief.md'",
          "error_type": "ValueError"
        }
        ```

    Note:
        - Rollback creates a new version (doesn't delete history)
        - Original content is restored from snapshot
        - Metadata (tokens, size, hash) is recalculated
        - Change type is marked as "rollback" in version history
        - To undo a rollback, use get_version_history to find the
          version before rollback, then rollback to that version
    """
    try:
        result = await _execute_rollback(file_name, version, project_root)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            build_rollback_error_response(str(e), type(e).__name__), indent=2
        )


async def _execute_rollback(
    file_name: str, version: int, project_root: str | None
) -> dict[str, object]:
    """Execute rollback workflow.

    Args:
        file_name: Name of file to rollback
        version: Version number to rollback to
        project_root: Optional project root path

    Returns:
        Result dictionary (success or error)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    managers = _extract_rollback_managers(mgrs)

    validation_result = await _validate_and_get_snapshot(
        managers, root, file_name, version
    )
    if isinstance(validation_result, dict):
        return validation_result

    file_path, content = validation_result
    return await _process_and_finalize_rollback(
        managers, file_name, file_path, content, version
    )


async def _validate_and_get_snapshot(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    root: Path,
    file_name: str,
    version: int,
) -> tuple[Path, str] | dict[str, object]:
    """Validate file and get snapshot content.

    Args:
        managers: Managers dictionary
        root: Project root path
        file_name: Name of file
        version: Version number

    Returns:
        Tuple of (file_path, content) or error dict
    """
    file_path = await _validate_rollback_file(
        cast(FileSystemManager, managers["fs_manager"]), root, file_name
    )
    if isinstance(file_path, dict):
        return cast(dict[str, object], file_path)

    content = await _get_rollback_snapshot(
        cast(VersionManager, managers["version_manager"]), file_name, version
    )
    if isinstance(content, dict):
        return cast(dict[str, object], content)

    return (file_path, content)


async def _process_and_finalize_rollback(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    file_name: str,
    file_path: Path,
    content: str,
    version: int,
) -> dict[str, object]:
    """Process content and finalize rollback.

    Args:
        managers: Managers dictionary
        file_name: Name of file
        file_path: Path to file
        content: File content
        version: Version rolled back from

    Returns:
        Success response dict
    """
    rollback_data = await _process_rollback_content(
        cast(FileSystemManager, managers["fs_manager"]),
        cast(TokenCounter, managers["token_counter"]),
        file_path,
        content,
    )

    new_version = await _update_rollback_metadata(
        cast(MetadataIndex, managers["metadata_index"]),
        file_name,
        file_path,
        content,
        rollback_data,
    )

    await _complete_rollback_finalization(
        managers, file_name, file_path, content, rollback_data, new_version, version
    )

    return build_rollback_success_response(
        file_name, version, new_version, cast(int, rollback_data["token_count"])
    )


async def _complete_rollback_finalization(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
    new_version: int,
    version: int,
) -> None:
    """Complete rollback finalization.

    Args:
        managers: Managers dictionary
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data
        new_version: New version number
        version: Version rolled back from
    """
    await _finalize_rollback(
        cast(VersionManager, managers["version_manager"]),
        cast(MetadataIndex, managers["metadata_index"]),
        file_name,
        file_path,
        content,
        rollback_data,
        new_version,
        version,
    )


def _extract_rollback_managers(
    mgrs: dict[str, object],
) -> dict[str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager]:
    """Extract managers for rollback operation.

    Args:
        mgrs: Managers dictionary

    Returns:
        Dictionary with extracted managers
    """
    return {
        "fs_manager": cast(FileSystemManager, mgrs["fs"]),
        "token_counter": cast(TokenCounter, mgrs["tokens"]),
        "metadata_index": cast(MetadataIndex, mgrs["index"]),
        "version_manager": cast(VersionManager, mgrs["versions"]),
    }


async def _validate_rollback_file(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> Path | dict[str, str]:
    """Validate file name for rollback.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Name of file to rollback

    Returns:
        File path or error dict
    """
    memory_bank_dir = root / "memory-bank"
    try:
        return fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return {"status": "error", "error": f"Invalid file name: {e}"}


async def _get_rollback_snapshot(
    version_manager: VersionManager, file_name: str, version: int
) -> str | dict[str, str]:
    """Get snapshot content for rollback.

    Args:
        version_manager: Version manager
        file_name: Name of file
        version: Version number to rollback to

    Returns:
        Content string or error dict
    """
    snapshot_path = version_manager.get_snapshot_path(file_name, version)
    if not snapshot_path.exists():
        return {
            "status": "error",
            "error": f"Version {version} not found for '{file_name}'",
        }

    return await version_manager.get_snapshot_content(snapshot_path)


async def _process_rollback_content(
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_path: Path,
    content: str,
) -> dict[str, object]:
    """Process rollback content: write, parse, and count tokens.

    Args:
        fs_manager: File system manager
        token_counter: Token counter
        file_path: Path to file
        content: Content to write

    Returns:
        Dictionary with processing results
    """
    new_hash = await fs_manager.write_file(file_path, content)

    sections_raw = fs_manager.parse_sections(content)
    sections = cast(
        list[dict[str, object]],
        [{k: v for k, v in section.items()} for section in sections_raw],
    )

    token_count = token_counter.count_tokens(content)

    return {
        "content_hash": new_hash,
        "sections": sections,
        "token_count": token_count,
        "size_bytes": len(content.encode("utf-8")),
    }


async def _update_rollback_metadata(
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
) -> int:
    """Update metadata after rollback.

    Args:
        metadata_index: Metadata index
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data

    Returns:
        New version number
    """
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=cast(int, rollback_data["size_bytes"]),
        token_count=cast(int, rollback_data["token_count"]),
        content_hash=cast(str, rollback_data["content_hash"]),
        sections=cast(list[dict[str, object]], rollback_data["sections"]),
        change_source="rollback",
    )

    file_meta = await metadata_index.get_file_metadata(file_name)
    return cast(int, file_meta.get("current_version", 0)) + 1 if file_meta else 1


async def _finalize_rollback(
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
    new_version: int,
    rolled_back_from_version: int,
) -> None:
    """Finalize rollback by creating version snapshot and saving metadata.

    Args:
        version_manager: Version manager
        metadata_index: Metadata index
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data
        new_version: New version number
        rolled_back_from_version: Version rolled back from
    """
    version_meta = await version_manager.create_snapshot(
        file_path=file_path,
        version=new_version,
        content=content,
        size_bytes=cast(int, rollback_data["size_bytes"]),
        token_count=cast(int, rollback_data["token_count"]),
        content_hash=cast(str, rollback_data["content_hash"]),
        change_type="rollback",
        change_description=f"Rolled back to version {rolled_back_from_version}",
    )

    await metadata_index.add_version_to_history(file_name, version_meta)
    await metadata_index.save()


def build_rollback_success_response(
    file_name: str, rolled_back_from_version: int, new_version: int, token_count: int
) -> dict[str, object]:
    """Build success response for rollback.

    Args:
        file_name: Name of file
        rolled_back_from_version: Version rolled back from
        new_version: New version number
        token_count: Token count

    Returns:
        Success response dict
    """
    return {
        "status": "success",
        "file_name": file_name,
        "rolled_back_from_version": rolled_back_from_version,
        "new_version": new_version,
        "token_count": token_count,
    }


def build_rollback_error_response(
    error_message: str, error_type: str
) -> dict[str, object]:
    """Build error response for rollback.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response dict
    """
    return {"status": "error", "error": error_message, "error_type": error_type}


async def _get_history_size(root: Path, version_manager: VersionManager) -> int:
    """Get total disk usage of version history directory."""
    history_dir = root / ".memory-bank-history"
    if not history_dir.exists():
        return 0
    disk_usage = await version_manager.get_disk_usage()
    return disk_usage.get("total_bytes", 0)


def sum_file_field(
    files_metadata: dict[str, dict[str, object]], field_name: str
) -> int:
    """Sum a numeric field across all files metadata."""
    total = 0
    for file_data in files_metadata.values():
        value = file_data.get(field_name, 0)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def extract_last_updated(index_stats: dict[str, object]) -> str | None:
    """Extract last_full_scan timestamp from index stats."""
    totals = index_stats.get("totals")
    if isinstance(totals, dict):
        totals_dict = cast(dict[str, object], totals)
        last_scan = totals_dict.get("last_full_scan")
        if isinstance(last_scan, str):
            return last_scan
    return None


def build_summary_dict(
    files_metadata: dict[str, dict[str, object]],
    total_tokens: int,
    total_size: int,
    total_reads: int,
    history_size: int,
) -> dict[str, object]:
    """Build summary dictionary with calculated totals."""
    return {
        "total_files": len(files_metadata),
        "total_tokens": total_tokens,
        "total_size_bytes": total_size,
        "total_size_kb": round(total_size / 1024, 2),
        "total_reads": total_reads,
        "history_size_bytes": history_size,
        "history_size_kb": round(history_size / 1024, 2),
    }


def calculate_token_status(
    total_tokens: int, max_tokens: int, warn_threshold: float
) -> str:
    """Calculate token budget status based on usage."""
    warn_threshold_tokens = int(max_tokens * (warn_threshold / 100))
    if total_tokens >= max_tokens:
        return "over_budget"
    elif total_tokens >= warn_threshold_tokens:
        return "warning"
    else:
        return "healthy"


async def _build_token_budget_dict(root: Path, total_tokens: int) -> dict[str, object]:
    """Build token budget analysis dictionary."""
    from cortex.validation.validation_config import ValidationConfig

    validation_config = ValidationConfig(root)
    max_tokens = validation_config.get_token_budget_max()
    warn_threshold = validation_config.get_token_budget_warn_threshold()

    usage_percentage = (total_tokens / max_tokens * 100) if max_tokens > 0 else 0
    remaining_tokens = max_tokens - total_tokens
    status = calculate_token_status(total_tokens, max_tokens, warn_threshold)

    return {
        "status": status,
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "remaining_tokens": remaining_tokens,
        "usage_percentage": round(usage_percentage, 2),
        "warn_threshold": warn_threshold,
    }


async def _build_refactoring_history_dict(
    mgrs: dict[str, object], refactoring_days: int
) -> dict[str, object]:
    """Build refactoring history dictionary."""
    from cortex.refactoring.refactoring_executor import RefactoringExecutor

    refactoring_executor = cast(RefactoringExecutor, mgrs.get("refactoring_executor"))
    if refactoring_executor:
        history = await refactoring_executor.get_execution_history(
            time_range_days=refactoring_days, include_rollbacks=True
        )
        return history
    else:
        return {
            "status": "unavailable",
            "message": "Refactoring executor not initialized",
        }


def calculate_totals(
    files_metadata: dict[str, dict[str, object]],
) -> tuple[int, int, int]:
    """Calculate totals for tokens, size, and reads.

    Args:
        files_metadata: Dictionary of file metadata

    Returns:
        Tuple of (total_tokens, total_size, total_reads)
    """
    total_tokens = sum_file_field(files_metadata, "token_count")
    total_size = sum_file_field(files_metadata, "size_bytes")
    total_reads = sum_file_field(files_metadata, "read_count")
    return total_tokens, total_size, total_reads


def _build_base_stats_result(
    root: Path,
    files_metadata: dict[str, dict[str, object]],
    totals: tuple[int, int, int],
    history_size: int,
    index_stats: dict[str, object],
) -> dict[str, object]:
    """Build base statistics result dictionary.

    Args:
        root: Project root path
        files_metadata: Dictionary of file metadata
        totals: Tuple of (total_tokens, total_size, total_reads)
        history_size: Size of version history in bytes
        index_stats: Index statistics dictionary

    Returns:
        Base statistics result dictionary
    """
    total_tokens, total_size, total_reads = totals
    summary = build_summary_dict(
        files_metadata, total_tokens, total_size, total_reads, history_size
    )
    last_updated = extract_last_updated(index_stats)

    return {
        "status": "success",
        "project_root": str(root),
        "summary": summary,
        "last_updated": last_updated,
        "index_stats": index_stats,
    }


async def _add_optional_stats(
    result: dict[str, object],
    include_token_budget: bool,
    include_refactoring_history: bool,
    root: Path,
    total_tokens: int,
    mgrs: dict[str, object],
    refactoring_days: int,
) -> None:
    """Add optional statistics to result dictionary.

    Args:
        result: Result dictionary to update
        include_token_budget: Whether to include token budget
        include_refactoring_history: Whether to include refactoring history
        root: Project root path
        total_tokens: Total token count
        mgrs: Managers dictionary
        refactoring_days: Days of refactoring history to include
    """
    if include_token_budget:
        result["token_budget"] = await _build_token_budget_dict(root, total_tokens)

    if include_refactoring_history:
        result["refactoring_history"] = await _build_refactoring_history_dict(
            mgrs, refactoring_days
        )


@mcp.tool()
async def get_memory_bank_stats(
    project_root: str | None = None,
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
) -> str:
    """Get overall Memory Bank statistics and analytics.

    Returns comprehensive statistics about token usage, file sizes,
    version history, usage patterns, token budget status, and optionally
    refactoring history. This is the primary tool for monitoring Memory
    Bank health and usage.

    Args:
        project_root: Optional path to project root directory
        include_token_budget: Include token budget analysis (default: True)
            Shows usage percentage, remaining tokens, and status
        include_refactoring_history: Include refactoring history (default: False)
            Shows recent refactorings, rollbacks, and success rates
        refactoring_days: Days of refactoring history to include (default: 90)
            Only used when include_refactoring_history=True

    Returns:
        JSON string with detailed statistics including:
        - summary: Total files, tokens, size, reads, history size
        - token_budget: Usage percentage, remaining tokens, status
        - refactoring_history: Recent refactorings and rollbacks (optional)
        - index_stats: Metadata index statistics

    Example (Basic stats):
        ```json
        {
          "status": "success",
          "project_root": "/path/to/project",
          "summary": {
            "total_files": 7,
            "total_tokens": 45120,
            "total_size_bytes": 180480,
            "total_size_kb": 176.25,
            "total_reads": 142,
            "history_size_bytes": 2048000,
            "history_size_kb": 2000.0
          },
          "token_budget": {
            "status": "healthy",
            "total_tokens": 45120,
            "max_tokens": 100000,
            "remaining_tokens": 54880,
            "usage_percentage": 45.12,
            "warn_threshold": 80.0
          },
          "last_updated": "2026-01-04T10:30:00",
          "index_stats": { ... }
        }
        ```

    Example (With refactoring history):
        When include_refactoring_history=True, adds:
        ```json
        {
          ...
          "refactoring_history": {
            "total_refactorings": 12,
            "successful": 10,
            "rolled_back": 2,
            "recent": [
              {
                "type": "consolidation",
                "timestamp": "2026-01-03T14:00:00",
                "files_affected": ["file1.md", "file2.md"],
                "status": "success"
              }
            ]
          }
        }
        ```

    Note:
        This tool replaces the deprecated check_token_budget and
        get_refactoring_history tools. Use include_token_budget=True and
        include_refactoring_history=True to get all information in one call.

        Token budget status values:
        - "healthy": Usage < warning threshold (default 80%)
        - "warning": Usage >= warning threshold but < max
        - "over_budget": Usage >= max tokens
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        metadata_index = cast(MetadataIndex, mgrs["index"])
        version_manager = cast(VersionManager, mgrs["versions"])

        index_stats = await metadata_index.get_stats()
        files_metadata = await metadata_index.get_all_files_metadata()
        history_size = await _get_history_size(root, version_manager)

        totals = calculate_totals(files_metadata)
        result = _build_base_stats_result(
            root, files_metadata, totals, history_size, index_stats
        )

        await _add_optional_stats(
            result,
            include_token_budget,
            include_refactoring_history,
            root,
            totals[0],
            mgrs,
            refactoring_days,
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )
