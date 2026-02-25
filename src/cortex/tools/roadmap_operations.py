"""
Roadmap Operations Tools

This module contains MCP tools and helpers for roadmap manipulation,
including adding entries deterministically to avoid truncation issues.
"""

__all__ = [
    "add_roadmap_entry",
    "entry_text_looks_completed",
    "execute_roadmap_insertion",
    "execute_roadmap_removal",
    "execute_roadmap_section_removal",
    "find_bullet_line_containing",
    "find_section_range_by_heading",
    "get_section_bullet_lines",
    "insert_roadmap_entry",
    "parse_roadmap_sections",
    "remove_line_at",
    "remove_roadmap_entry",
    "remove_roadmap_section",
    "remove_section_range",
    "RoadmapSection",
    "validate_section_id",
]

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.models import (
    AddRoadmapEntryResult,
    RemoveRoadmapEntryResult,
    RemoveRoadmapSectionResult,
)
from cortex.tools.roadmap_operations_content import (
    entry_text_looks_completed,
    find_bullet_line_containing,
    find_section_range_by_heading,
    insert_roadmap_entry,
    remove_line_at,
    remove_section_range,
    validate_section_id,
)
from cortex.tools.roadmap_operations_insert import execute_roadmap_insertion
from cortex.tools.roadmap_operations_parsing import (
    RoadmapSection,
    get_section_bullet_lines,
    parse_roadmap_sections,
)
from cortex.tools.roadmap_operations_removal import (
    execute_roadmap_removal,
    execute_roadmap_section_removal,
)


async def _add_roadmap_entry_impl(
    section: str,
    entry_text: str,
    position: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of add_roadmap_entry logic."""
    await log_client(ctx, "info", "add_roadmap_entry: starting", logger_name=__name__)

    root = await resolve_project_root_async(None, ctx)
    result = await execute_roadmap_insertion(root, section, entry_text, position)

    await log_client(
        ctx,
        "info" if result.status == OperationStatus.SUCCESS else "warning",
        f"add_roadmap_entry: {result.status.value}",
        logger_name=__name__,
    )

    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Add Roadmap Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def add_roadmap_entry(
    section: str,
    entry_text: str,
    position: str = "last",
    change_description: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Add entry to roadmap section, avoiding truncation from full updates.

    USE WHEN: Create-plan Step 6 needs to register a new plan entry.

    EXAMPLES: 'add_roadmap_entry(section="pending", entry_text="- Plan: .cortex/plans/foo.md")',
    'add roadmap entry to future section'.

    RETURNS: JSON with operation status, line inserted, error if any.

    Sections supported: 'blockers', 'active_work', 'future', 'pending'.
    """
    try:
        return await _add_roadmap_entry_impl(section, entry_text, position, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"add_roadmap_entry: {e}",
            logger_name=__name__,
        )
        error_result = AddRoadmapEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ROADMAP,
            message="Unexpected error",
            line_inserted=None,
            section=None,
            error=str(e),
        )
        return error_result.model_dump_json()


async def _remove_roadmap_entry_impl(
    entry_contains: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of remove_roadmap_entry logic."""
    await log_client(
        ctx, "info", "remove_roadmap_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = await execute_roadmap_removal(root, entry_contains)
    await log_client(
        ctx,
        "info" if result.status == OperationStatus.SUCCESS else "warning",
        f"remove_roadmap_entry: {result.status.value}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Remove Roadmap Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def remove_roadmap_entry(
    entry_contains: str,
    ctx: MCPContext | None = None,
) -> str:
    """Remove a single roadmap entry (bullet) that contains the given text.

    USE WHEN: Implement Step 5 needs to remove the completed step from the
    roadmap without building or writing full roadmap content (safe update).

    EXAMPLES: 'remove_roadmap_entry(entry_contains="Plan: .cortex/plans/foo.md")',
    'remove roadmap entry containing phase-58'.

    RETURNS: JSON with status, line_removed (1-based), or error.
    """
    try:
        return await _remove_roadmap_entry_impl(entry_contains, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"remove_roadmap_entry: {e}",
            logger_name=__name__,
        )
        error_result = RemoveRoadmapEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ROADMAP,
            message="Unexpected error",
            line_removed=None,
            error=str(e),
        )
        return error_result.model_dump_json()


async def _remove_roadmap_section_impl(
    section_heading_contains: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of remove_roadmap_section logic."""
    await log_client(
        ctx,
        "info",
        "remove_roadmap_section: starting",
        logger_name=__name__,
    )
    root = await resolve_project_root_async(None, ctx)
    result = await execute_roadmap_section_removal(root, section_heading_contains)
    await log_client(
        ctx,
        "info" if result.status == OperationStatus.SUCCESS else "warning",
        f"remove_roadmap_section: {result.status.value}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Remove Roadmap Section"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def remove_roadmap_section(
    section_heading_contains: str,
    ctx: MCPContext | None = None,
) -> str:
    """Remove a roadmap section by heading text (and its content until next section).

    USE WHEN: After removing all bullets in a subsection with remove_roadmap_entry,
    use this to remove the orphan section header and optional intro paragraph
    without building or writing full roadmap content (avoids corruption risk).

    EXAMPLES: 'remove_roadmap_section(section_heading_contains="Session Optimization (2026-02-01)")',
    'remove empty roadmap section'.

    Matches ## or ### headings that contain the given text (case-sensitive).
    RETURNS: JSON with status, section_heading, lines_removed, or error.
    """
    try:
        return await _remove_roadmap_section_impl(section_heading_contains, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"remove_roadmap_section: {e}",
            logger_name=__name__,
        )
        error_result = RemoveRoadmapSectionResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ROADMAP,
            message="Unexpected error",
            section_heading=None,
            lines_removed=None,
            error=str(e),
        )
        return error_result.model_dump_json()
