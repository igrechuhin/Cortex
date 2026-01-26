"""
Metadata Index Cleanup Tool

This module provides the cleanup_metadata_index tool for cleaning up
stale entries from the metadata index.
"""

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


async def _process_stale_entries(
    metadata_index: MetadataIndex, stale_files: list[str], dry_run: bool
) -> CleanupMetadataIndexResult:
    """Process stale entries and return cleanup result."""
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


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def cleanup_metadata_index(
    project_root: str | None = None, dry_run: bool = False
) -> CleanupMetadataIndexResultUnion:
    """Clean up stale entries from metadata index.

    Validates index consistency with filesystem and removes entries for files
    that no longer exist on disk. Supports dry-run mode.
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        metadata_index: MetadataIndex = mgrs.index
        stale_files = await metadata_index.validate_index_consistency()
        if not stale_files:
            return CleanupMetadataIndexResult(
                dry_run=dry_run,
                stale_files_found=0,
                stale_files=[],
                entries_cleaned=0,
                message="No stale entries found",
            )
        return await _process_stale_entries(metadata_index, stale_files, dry_run)
    except Exception as e:
        return CleanupMetadataIndexErrorResult(
            error=str(e), error_type=type(e).__name__
        )
