"""
Append Entry dispatcher: unified append_entry(operation=...) MCP tool.

Consolidates append_progress_entry and append_active_context_entry into
a single operation-based dispatcher following the Phase 50 pattern.
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


def _append_entry_error_invalid_operation(operation: str) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendProgressEntryResult

    return AppendProgressEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.PROGRESS,
        message=f"Invalid operation '{operation}'. Use progress or active_context.",
        line_inserted=None,
        error="Invalid operation",
    ).model_dump_json()


def _append_entry_error_progress_missing() -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendProgressEntryResult

    return AppendProgressEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.PROGRESS,
        message="date_str and entry_text are required when operation is 'progress'",
        line_inserted=None,
        error="Missing date_str or entry_text",
    ).model_dump_json()


def _append_entry_error_active_context_missing() -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendActiveContextEntryResult

    return AppendActiveContextEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ACTIVE_CONTEXT,
        message="date_str, title, and summary are required when operation is 'active_context'",
        line_inserted=None,
        error="Missing date_str, title, or summary",
    ).model_dump_json()


async def _append_entry_handle_progress(
    date_str: str, entry_text: str, ctx: MCPContext | None
) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.context_logging import log_client
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendProgressEntryResult
    from cortex.tools.plan_completion import append_progress_entry_impl

    try:
        return await append_progress_entry_impl(date_str, entry_text, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"append_entry(progress): {e}", logger_name=__name__
        )
        return AppendProgressEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.PROGRESS,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()


async def _append_entry_handle_active_context(
    date_str: str, title: str, summary: str, ctx: MCPContext | None
) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.context_logging import log_client
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendActiveContextEntryResult
    from cortex.tools.plan_completion import append_active_context_entry_impl

    try:
        return await append_active_context_entry_impl(date_str, title, summary, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"append_entry(active_context): {e}",
            logger_name=__name__,
        )
        return AppendActiveContextEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()


@mcp.tool(
    annotations=safe_write_annotations("Append Entry (Progress or Active Context)")
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def append_entry(
    operation: str = "progress",
    # progress params
    date_str: str | None = None,
    entry_text: str | None = None,
    # active_context params
    title: str | None = None,
    summary: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Append a single entry to progress.md or activeContext.md (single memory-bank append tool).

    USE WHEN: Implement Step 5 needs to add progress or completed-work entries
    without building or writing full content (safe update). Prefer over
    manage_file(write) for single-bullet appends.

    EXAMPLES:
    - append_entry(operation="progress", date_str="2026-02-24", entry_text="**Phase X** - COMPLETE. Done.")
    - append_entry(operation="active_context", date_str="2026-02-24", title="Step 1", summary="Rubric added.")

    RETURNS: JSON (AppendProgressEntryResult or AppendActiveContextEntryResult per operation).

    Parameters:
    - operation: 'progress' or 'active_context'
    - progress: date_str (YYYY-MM-DD), entry_text required
    - active_context: date_str (YYYY-MM-DD), title, summary required
    """
    if operation not in ("progress", "active_context"):
        return _append_entry_error_invalid_operation(operation)
    if operation == "progress":
        if not date_str or entry_text is None:
            return _append_entry_error_progress_missing()
        return await _append_entry_handle_progress(date_str, entry_text, ctx)
    if operation == "active_context":
        if not date_str or not title or summary is None:
            return _append_entry_error_active_context_missing()
        return await _append_entry_handle_active_context(date_str, title, summary, ctx)
    return _append_entry_error_invalid_operation(operation)
