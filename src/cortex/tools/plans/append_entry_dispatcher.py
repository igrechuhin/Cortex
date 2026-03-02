"""
Append entry operations: internal implementation for update_memory_bank.

append_entry_impl is called by update_memory_bank for progress_append and
active_context_append. No longer a standalone MCP tool (consolidated).
"""

from __future__ import annotations

from cortex.core.context_logging import MCPContext


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
    from cortex.tools.plans.completion import append_progress_entry_impl

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
    from cortex.tools.plans.completion import append_active_context_entry_impl

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


async def append_entry_impl(
    operation: str = "progress",
    # progress params
    date_str: str | None = None,
    entry_text: str | None = None,
    # active_context params
    title: str | None = None,
    summary: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Internal: append entry to progress or activeContext.

    Called by update_memory_bank. Operations: progress, active_context.
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
