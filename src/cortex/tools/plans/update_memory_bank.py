"""
Unified memory bank mutation tool: roadmap and append operations.

Consolidates roadmap (add/remove entry/section) and append_entry
(progress/active_context) into a single operation-based dispatcher.
Reduces tool count by 1.
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp

# Operation name constants for validation
_ROADMAP_OPS = frozenset({"roadmap_add", "roadmap_remove", "roadmap_remove_section"})
_APPEND_OPS = frozenset({"progress_append", "active_context_append"})
_VALID_OPS = _ROADMAP_OPS | _APPEND_OPS


def _error_invalid_operation(operation: str) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Invalid operation '{operation}'. Use: roadmap_add, roadmap_remove, roadmap_remove_section, progress_append, active_context_append.",
        line_inserted=None,
        section=None,
        error="Invalid operation",
    ).model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Update Memory Bank (Roadmap & Append)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def update_memory_bank(
    operation: str = "roadmap_add",
    # roadmap_add
    section: str | None = None,
    entry_text: str | None = None,
    position: str = "last",
    change_description: str | None = None,
    # roadmap_remove
    entry_contains: str | None = None,
    # roadmap_remove_section
    section_heading_contains: str | None = None,
    # progress_append / active_context_append
    date_str: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Add/remove roadmap entries, append to progress or activeContext (single memory-bank mutation tool).

    USE WHEN: Adding or removing roadmap entries, or appending a single entry
    to progress.md or activeContext.md. Prefer over manage_file(write) for
    targeted mutations to avoid truncation and corruption.

    DO NOT:
    - Use manage_file(write) directly on roadmap.md, progress.md, or
      activeContext.md when you can express the change as a single bullet or
      entry; prefer this tool instead.
    - Use this tool for generic search/replace or bulk edits across Memory
      Bank files; it is designed for small, structured mutations only.

    EXAMPLES:
    - update_memory_bank(operation="roadmap_add", section="pending", entry_text="- Plan: .cortex/plans/foo.md")
    - update_memory_bank(operation="roadmap_remove", entry_contains="Plan: .cortex/plans/foo.md")
    - update_memory_bank(operation="roadmap_remove_section", section_heading_contains="Session Optimization")
    - update_memory_bank(operation="progress_append", date_str="2026-02-24", entry_text="**Phase X** - COMPLETE. Done.")
    - update_memory_bank(operation="active_context_append", date_str="2026-02-24", title="Step 1", summary="Rubric added.")

    RETURNS: JSON per operation (AddRoadmapEntryResult, RemoveRoadmapEntryResult,
    RemoveRoadmapSectionResult, AppendProgressEntryResult, or AppendActiveContextEntryResult).

    Parameters:
    - operation: roadmap_add | roadmap_remove | roadmap_remove_section | progress_append | active_context_append
    - roadmap_add: section, entry_text required; position (default 'last'), change_description optional
    - roadmap_remove: entry_contains required (unique substring of bullet)
    - roadmap_remove_section: section_heading_contains required
    - progress_append: date_str (YYYY-MM-DD), entry_text required
    - active_context_append: date_str (YYYY-MM-DD), title, summary required
    """
    if operation not in _VALID_OPS:
        return _error_invalid_operation(operation)
    return await _dispatch_update_memory_bank(
        operation,
        section,
        entry_text,
        position,
        change_description,
        entry_contains,
        section_heading_contains,
        date_str,
        title,
        summary,
        ctx,
    )


async def _handle_roadmap_op(
    operation: str,
    section: str | None,
    entry_text: str | None,
    position: str,
    change_description: str | None,
    entry_contains: str | None,
    section_heading_contains: str | None,
    ctx: MCPContext | None,
) -> str:
    """Delegate roadmap operations to roadmap_impl."""
    from cortex.tools.plans.roadmap import roadmap_impl

    op_map = {
        "roadmap_add": "add_entry",
        "roadmap_remove": "remove_entry",
        "roadmap_remove_section": "remove_section",
    }
    return await roadmap_impl(
        operation=op_map[operation],
        section=section,
        entry_text=entry_text,
        position=position,
        change_description=change_description,
        entry_contains=entry_contains,
        section_heading_contains=section_heading_contains,
        ctx=ctx,
    )


async def _handle_append_op(
    operation: str,
    date_str: str | None,
    entry_text: str | None,
    title: str | None,
    summary: str | None,
    ctx: MCPContext | None,
) -> str:
    """Delegate append operations to append_entry_impl."""
    from cortex.tools.plans.append_entry_dispatcher import append_entry_impl

    op_map = {
        "progress_append": "progress",
        "active_context_append": "active_context",
    }
    return await append_entry_impl(
        operation=op_map[operation],
        date_str=date_str,
        entry_text=entry_text,
        title=title,
        summary=summary,
        ctx=ctx,
    )


async def _dispatch_update_memory_bank(
    operation: str,
    section: str | None,
    entry_text: str | None,
    position: str,
    change_description: str | None,
    entry_contains: str | None,
    section_heading_contains: str | None,
    date_str: str | None,
    title: str | None,
    summary: str | None,
    ctx: MCPContext | None,
) -> str:
    """Route to roadmap_impl or append_entry_impl based on operation."""
    if operation in _ROADMAP_OPS:
        return await _handle_roadmap_op(
            operation,
            section,
            entry_text,
            position,
            change_description,
            entry_contains,
            section_heading_contains,
            ctx,
        )
    return await _handle_append_op(operation, date_str, entry_text, title, summary, ctx)
