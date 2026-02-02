"""
Metadata Index Cleanup Tool

This module provides the cleanup_metadata_index tool for cleaning up
stale entries from the metadata index.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
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
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def cleanup_metadata_index(
    project_root: str | None = None,
    dry_run: bool = False,
    ctx: MCPContext | None = None,
) -> CleanupMetadataIndexResultUnion:
    """Clean up stale entries from metadata index.

    USE WHEN: User reports index corruption, user needs to fix stale
    metadata, user wants to clean up index, user requests index maintenance.

    EXAMPLES: 'cleanup metadata index', 'fix stale index entries', 'repair
    corrupted index'.

    RETURNS: JSON with cleanup results: entries removed, entries kept, and
    dry-run preview if enabled.

    Validates index consistency with filesystem and removes entries for
    files that no longer exist on disk. Supports dry-run mode.
    """
    await log_client(
        ctx, "info", "cleanup_metadata_index: starting", logger_name=__name__
    )
    try:
        result = await _cleanup_metadata_index_impl(project_root, dry_run)
        await log_client(
            ctx, "info", "cleanup_metadata_index: completed", logger_name=__name__
        )
        return result
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"cleanup_metadata_index: failed: {e}",
            logger_name=__name__,
        )
        return CleanupMetadataIndexErrorResult(
            error=str(e), error_type=type(e).__name__
        )


async def _cleanup_metadata_index_impl(
    project_root: str | None, dry_run: bool
) -> CleanupMetadataIndexResultUnion:
    """Run cleanup logic and return result."""
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
