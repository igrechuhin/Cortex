"""
Append entry operations: internal implementation for update_memory_bank.

append_entry_impl is called by update_memory_bank for progress_append and
active_context_append. No longer a standalone MCP tool (consolidated).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import NamedTuple

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
    date_str: str, entry_text: str, skip_classification: bool, ctx: MCPContext | None
) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.context_logging import log_client
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendProgressEntryResult
    from cortex.tools.plans.completion import append_progress_entry_impl

    try:
        return await append_progress_entry_impl(
            date_str, _classify_entry(entry_text, skip_classification), ctx
        )
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
    payload: "_ActiveContextPayload", ctx: MCPContext | None
) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.context_logging import log_client
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AppendActiveContextEntryResult
    from cortex.tools.plans.completion import append_active_context_entry_impl

    try:
        return await _append_active_context_classified(
            append_active_context_entry_impl,
            payload,
            ctx,
        )
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


async def _append_active_context_classified(
    append_active_context_entry_impl: Callable[
        [str, str, str, MCPContext | None], Awaitable[str]
    ],
    payload: "_ActiveContextPayload",
    ctx: MCPContext | None,
) -> str:
    return await append_active_context_entry_impl(
        payload.date_str,
        payload.title,
        _classify_entry(payload.summary, payload.skip_classification),
        ctx,
    )


async def append_entry_impl(
    operation: str = "progress",
    # progress params
    date_str: str | None = None,
    entry_text: str | None = None,
    # active_context params
    title: str | None = None,
    summary: str | None = None,
    skip_classification: bool = False,
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
        return await _append_entry_handle_progress(
            date_str, entry_text, skip_classification, ctx
        )
    if operation == "active_context":
        if not date_str or not title or summary is None:
            return _append_entry_error_active_context_missing()
        payload = _ActiveContextPayload(date_str, title, summary, skip_classification)
        return await _append_entry_handle_active_context(payload, ctx)
    return _append_entry_error_invalid_operation(operation)


def _classify_entry(text: str, skip_classification: bool) -> str:
    if skip_classification or "<!-- memory_type:" in text:
        return text
    from cortex.memory.memory_types import classify_text

    memory_type = classify_text(text).value
    return f"<!-- memory_type: {memory_type} -->\n{text}"


class _ActiveContextPayload(NamedTuple):
    date_str: str
    title: str
    summary: str
    skip_classification: bool
