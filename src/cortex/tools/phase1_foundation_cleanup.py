"""
Metadata Index Cleanup Tool

This module provides the cleanup_metadata_index tool for cleaning up
stale entries from the metadata index.
"""

from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.initialization import get_managers, get_project_root
from cortex.server import mcp
from cortex.tools.models import (
    CleanupMetadataIndexErrorResult,
    CleanupMetadataIndexResult,
    CleanupMetadataIndexResultUnion,
)


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def cleanup_metadata_index(
    project_root: str | None = None,
    dry_run: bool = False,
) -> CleanupMetadataIndexResultUnion:
    """Clean up stale entries from metadata index.

    Validates index consistency with filesystem and removes entries
    for files that no longer exist on disk. Supports dry-run mode to
    preview what would be cleaned without making changes.

    Args:
        project_root: Optional path to project root directory.
            Defaults to current working directory if not specified.
            Example: "/Users/username/projects/my-app"
        dry_run: If True, only report what would be cleaned without
            making changes. If False, actually remove stale entries.
            Default: False

    Returns:
        Pydantic model containing cleanup results with:
        - status: "success" or "error"
        - dry_run: Whether this was a dry run
        - stale_files_found: Number of stale files found
        - stale_files: List of stale file names
        - entries_cleaned: Number of entries actually cleaned (0 if dry_run=True)
        - message: Summary message

    Example (Dry run):
        CleanupMetadataIndexResult(
            status="success",
            dry_run=True,
            stale_files_found=2,
            stale_files=["test_verification.md", "test_links.md"],
            entries_cleaned=0,
            message="Would clean 2 stale entries"
        )

    Example (Actual cleanup):
        CleanupMetadataIndexResult(
            status="success",
            dry_run=False,
            stale_files_found=2,
            stale_files=["test_verification.md", "test_links.md"],
            entries_cleaned=2,
            message="Cleaned 2 stale entries"
        )

    Note:
        - Stale entries are files that exist in the metadata index
          but no longer exist on the filesystem
        - Use dry_run=True to preview changes before cleaning
        - Cleanup automatically recalculates index totals after removal
        - This tool helps maintain index consistency and prevents
          retry errors when reading non-existent files
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        metadata_index = cast(MetadataIndex, mgrs["index"])

        # Validate index consistency to find stale entries
        stale_files = await metadata_index.validate_index_consistency()

        if not stale_files:
            return CleanupMetadataIndexResult(
                dry_run=dry_run,
                stale_files_found=0,
                stale_files=[],
                entries_cleaned=0,
                message="No stale entries found",
            )

        # Clean up stale entries
        entries_cleaned = await metadata_index.cleanup_stale_entries(dry_run=dry_run)

        message = (
            f"Would clean {len(stale_files)} stale entries"
            if dry_run
            else f"Cleaned {entries_cleaned} stale entries"
        )

        return CleanupMetadataIndexResult(
            dry_run=dry_run,
            stale_files_found=len(stale_files),
            stale_files=stale_files,
            entries_cleaned=entries_cleaned,
            message=message,
        )
    except Exception as e:
        return CleanupMetadataIndexErrorResult(
            error=str(e),
            error_type=type(e).__name__,
        )
