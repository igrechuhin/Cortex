"""
Plan Completion Tool

Moves a completed plan from roadmap.md to activeContext.md so that
roadmap stays future/upcoming only and completed work is recorded in activeContext.
When plan_file_name is provided, also moves (archives) the plan file to the
appropriate archive directory and removes any duplicate from the plans root.
"""

__all__ = [
    "CompletePlanResult",
    "append_active_context_entry",
    "append_progress_entry",
    "complete_plan",
]

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import destructive_annotations, safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.models import (
    AppendActiveContextEntryResult,
    AppendProgressEntryResult,
)
from cortex.tools.plan_completion_content import today_iso
from cortex.tools.plan_completion_models import CompletePlanResult
from cortex.tools.plan_completion_ops import (
    apply_progress_and_archive,
    complete_plan_invalid_date_json,
    do_complete_plan,
    execute_append_active_context,
    execute_append_progress,
)
from cortex.tools.plan_completion_validation import validate_date_str


async def _complete_plan_impl(
    plan_title: str,
    summary: str,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    ctx: MCPContext | None,
) -> str:
    """Implementation of complete_plan: roadmap + activeContext, optional progress, optional archive."""
    await log_client(ctx, "info", "complete_plan: starting", logger_name=__name__)
    date_str = (completion_date or today_iso()).strip()
    if date_err := validate_date_str(date_str):
        return complete_plan_invalid_date_json(date_err)
    root = await resolve_project_root_async(None, ctx)
    result = await do_complete_plan(root, plan_title, summary, date_str)
    if result.status != OperationStatus.SUCCESS:
        await log_client(
            ctx, "warning", f"complete_plan: {result.status}", logger_name=__name__
        )
        return result.model_dump_json()
    await apply_progress_and_archive(
        root, date_str, progress_entry, plan_file_name, result
    )
    await log_client(
        ctx, "info", f"complete_plan: {result.status}", logger_name=__name__
    )
    return result.model_dump_json()


@mcp.tool(annotations=destructive_annotations("Complete Plan"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def complete_plan(
    plan_title: str,
    summary: str,
    completion_date: str | None = None,
    progress_entry: str | None = None,
    plan_file_name: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Move a completed plan from roadmap to activeContext; optionally append progress and archive plan file.

    USE WHEN: A plan has been finished and should be recorded as completed
    in activeContext.md and removed from roadmap.md (roadmap = future only).
    When the step references a plan file, pass plan_file_name so the tool
    also moves (archives) the plan file to the correct archive directory.

    EXAMPLES: 'complete_plan(plan_title="Session improvements", summary="Tools optimization.", plan_file_name="session-optimization-2026-02-23.md")',
    'complete plan Anthropic alignment Step 1'.

    RETURNS: JSON with status, roadmap_line_removed, active_context_line_inserted,
    optional progress_line_inserted, optional archive_path.

    - Removes the first roadmap bullet that contains plan_title.
    - Appends a completed entry to activeContext under ## Completed Work (date).
    - If progress_entry is provided, appends that line to progress.md under the date.
    - If plan_file_name is provided, moves the plan file to archive (SessionOptimization/,
      PhaseN/, Investigations/YYYY-MM-DD/, or Other/) and removes any duplicate from plans root.
    - completion_date: YYYY-MM-DD (default: today UTC).
    """
    try:
        return await _complete_plan_impl(
            plan_title,
            summary,
            completion_date,
            progress_entry,
            plan_file_name,
            ctx,
        )
    except Exception as e:
        await log_client(ctx, "error", f"complete_plan: {e}", logger_name=__name__)
        return CompletePlanResult(
            status=OperationStatus.ERROR,
            message="Unexpected error",
            roadmap_line_removed=None,
            active_context_line_inserted=None,
            progress_line_inserted=None,
            archive_path=None,
            error=str(e),
        ).model_dump_json()


async def _append_progress_entry_impl(
    date_str: str,
    entry_text: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of append_progress_entry."""
    await log_client(
        ctx, "info", "append_progress_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = await execute_append_progress(root, date_str, entry_text)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"append_progress_entry: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Append Progress Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def append_progress_entry(
    date_str: str,
    entry_text: str,
    ctx: MCPContext | None = None,
) -> str:
    """Append a single entry to progress.md under the given date section.

    USE WHEN: Implement Step 5 needs to add one progress entry without
    building or writing full progress content (safe update).

    EXAMPLES: 'append_progress_entry(date_str="2026-02-24", entry_text="**Phase X** - COMPLETE. Done.")',
    'append progress entry for today'.

    date_str: YYYY-MM-DD. entry_text: one bullet line (e.g. "**Title** - COMPLETE. ...").
    RETURNS: JSON with status, line_inserted, or error.
    """
    try:
        return await _append_progress_entry_impl(date_str, entry_text, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"append_progress_entry: {e}", logger_name=__name__
        )
        return AppendProgressEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.PROGRESS,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()


async def _append_active_context_entry_impl(
    date_str: str,
    title: str,
    summary: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of append_active_context_entry."""
    await log_client(
        ctx, "info", "append_active_context_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = await execute_append_active_context(root, date_str, title, summary)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"append_active_context_entry: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Append Active Context Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def append_active_context_entry(
    date_str: str,
    title: str,
    summary: str,
    ctx: MCPContext | None = None,
) -> str:
    """Append a single completed entry to activeContext.md.

    USE WHEN: Implement Step 5 needs to add completed work without
    building or writing full activeContext content (safe update).

    EXAMPLES: 'append_active_context_entry(date_str="2026-02-24", title="Step 1", summary="Rubric added.")',
    'append active context entry for completed work'.

    date_str: YYYY-MM-DD. title/summary: entry content.
    RETURNS: JSON with status, line_inserted, or error.
    """
    try:
        return await _append_active_context_entry_impl(date_str, title, summary, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"append_active_context_entry: {e}",
            logger_name=__name__,
        )
        return AppendActiveContextEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()
