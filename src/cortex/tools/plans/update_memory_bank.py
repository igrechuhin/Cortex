"""
Unified memory bank mutation tool: roadmap and append operations.

Consolidates roadmap (add/remove entry/section) and append_entry
(progress/active_context) into a single operation-based dispatcher.
Reduces tool count by 1.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp

# Operation name constants for validation
_ROADMAP_OPS = frozenset({"roadmap_add", "roadmap_remove", "roadmap_remove_section"})
_APPEND_OPS = frozenset({"progress_append", "active_context_append"})
_LOG_OPS = frozenset({"log_append"})
_VALID_OPS = _ROADMAP_OPS | _APPEND_OPS | _LOG_OPS


class _UpdateRequest(NamedTuple):
    operation: str
    section: str | None
    entry_text: str | None
    position: str
    change_description: str | None
    entry_contains: str | None
    section_heading_contains: str | None
    date_str: str | None
    title: str | None
    summary: str | None
    operation_type: str | None
    skip_classification: bool


def _error_invalid_operation(operation: str) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Invalid operation '{operation}'. Use: roadmap_add, roadmap_remove, roadmap_remove_section, progress_append, active_context_append, log_append.",
        line_inserted=None,
        section=None,
        error="Invalid operation",
    ).model_dump_json()


@mcp.tool(
    annotations=safe_write_annotations("Update Memory Bank (Roadmap & Append)"),
    output_schema=None,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
# fmt: off
async def update_memory_bank(
    operation: str = "roadmap_add", section: str | None = None, entry_text: str | None = None,
    position: str = "last", change_description: str | None = None, entry_contains: str | None = None,
    section_heading_contains: str | None = None, date_str: str | None = None, title: str | None = None,
    summary: str | None = None, operation_type: str | None = None, skip_classification: bool = False,
    ctx: MCPContext | None = None,
) -> str:
# fmt: on
    """Add/remove roadmap entries and append memory-bank entries.

    USE WHEN: You need a single memory-bank mutation entrypoint for roadmap
    edits (add/remove section entries) or append-style updates for progress,
    active context, or operations log entries.

    DO NOT use this tool for free-form markdown rewrites; Prefer targeted
    operation modes so validation and sync rules remain enforceable.

    EXAMPLES:
    - update_memory_bank(operation="roadmap_add", section="pending",
      entry_text="- Improve retrieval scoring")
    - update_memory_bank(operation="progress_append", date_str="2026-04-14",
      entry_text="Implemented typed memory reader")
    - update_memory_bank(operation="log_append", operation_type="fix",
      title="Resolve docs gate mismatch", summary="Aligned roadmap and progress")
    """
    request = _UpdateRequest(
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
        operation_type,
        skip_classification,
    )
    if operation not in _VALID_OPS:
        return _error_invalid_operation(operation)
    return await _dispatch_update_memory_bank(request, ctx)


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
    skip_classification: bool,
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
        skip_classification=skip_classification,
        ctx=ctx,
    )


async def _dispatch_update_memory_bank(
    request: _UpdateRequest, ctx: MCPContext | None
) -> str:
    """Route to roadmap_impl or append_entry_impl based on operation."""
    if request.operation in _LOG_OPS:
        return await _handle_log_append_op(
            request.operation_type,
            request.title,
            request.summary,
            request.date_str,
            ctx,
        )
    if request.operation in _ROADMAP_OPS:
        return await _handle_roadmap_op(
            request.operation,
            request.section,
            request.entry_text,
            request.position,
            request.change_description,
            request.entry_contains,
            request.section_heading_contains,
            ctx,
        )
    return await _handle_append_op(
        request.operation,
        request.date_str,
        request.entry_text,
        request.title,
        request.summary,
        request.skip_classification,
        ctx,
    )


def _log_append_response(
    *, status: str, message: str, line_inserted: int | None, error: str | None
) -> str:
    import json

    from cortex.core.constants import MemoryBankFile

    return json.dumps(
        {
            "status": status,
            "file_name": MemoryBankFile.LOG,
            "message": message,
            "line_inserted": line_inserted,
            "error": error,
        }
    )


def _parse_operation_type(operation_type: str | None) -> tuple[str | None, str | None]:
    from cortex.tools.plans.operations_log import OperationsLogType

    if not operation_type:
        return None, "Missing operation_type or title"
    try:
        return OperationsLogType(operation_type.strip().lower()).value, None
    except ValueError:
        allowed = ", ".join(item.value for item in OperationsLogType)
        return (
            None,
            f"Invalid operation_type '{operation_type}'. Use one of: {allowed}.",
        )


def _parse_timestamp(date_str: str | None) -> tuple[datetime | None, str | None]:
    if not date_str:
        return None, None
    try:
        return datetime.fromisoformat(date_str.strip()), None
    except ValueError:
        return None, "date_str must be ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM)."


def _resolve_log_error_kind(message: str) -> str:
    if message.startswith("operation_type and title"):
        return "Missing operation_type or title"
    if message.startswith("date_str must be ISO format"):
        return "Invalid date_str"
    return "Invalid operation_type"


def _validate_log_append_input(
    operation_type: str | None,
    title: str | None,
    date_str: str | None,
) -> tuple[str | None, datetime | None, str | None]:
    if not operation_type or not title:
        return (
            None,
            None,
            "operation_type and title are required when operation is 'log_append'",
        )
    operation_value, operation_error = _parse_operation_type(operation_type)
    if operation_error:
        return None, None, operation_error
    parsed_timestamp, timestamp_error = _parse_timestamp(date_str)
    if timestamp_error:
        return None, None, timestamp_error
    return operation_value, parsed_timestamp, None


async def _resolve_log_path(ctx: MCPContext | None) -> Path:
    from cortex.core.path_resolver import CortexResourceType, get_cortex_path
    from cortex.core.usage_context import get_or_resolve_project_root

    project_root = Path(await get_or_resolve_project_root(ctx))
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK) / "log.md"


async def _append_log_entry(
    operation_value: str,
    title: str,
    summary: str | None,
    parsed_timestamp: datetime | None,
    ctx: MCPContext | None,
) -> int:
    from cortex.tools.plans.operations_log import (
        OperationsLogType,
        append_operations_log_entry,
    )

    log_path = await _resolve_log_path(ctx)
    op_kind = OperationsLogType(operation_value)
    return append_operations_log_entry(
        log_path=log_path,
        operation_type=op_kind,
        title=title,
        summary=summary,
        timestamp=parsed_timestamp,
    )


def _prepare_log_append(
    operation_type: str | None, title: str | None, date_str: str | None
) -> tuple[str, datetime | None, str] | str:
    from cortex.core.models import OperationStatus

    operation_value, parsed_timestamp, validation_error = _validate_log_append_input(
        operation_type, title, date_str
    )
    if validation_error:
        return _log_append_response(
            status=OperationStatus.ERROR.value,
            message=validation_error,
            line_inserted=None,
            error=_resolve_log_error_kind(validation_error),
        )
    if operation_value is None or title is None:
        return _log_append_response(
            status=OperationStatus.ERROR.value,
            message="Invalid operation_type",
            line_inserted=None,
            error="Invalid operation_type",
        )
    return operation_value, parsed_timestamp, title


async def _handle_log_append_op(
    operation_type: str | None,
    title: str | None,
    summary: str | None,
    date_str: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.core.models import OperationStatus

    prepared = _prepare_log_append(operation_type, title, date_str)
    if isinstance(prepared, str):
        return prepared
    operation_value, parsed_timestamp, normalized_title = prepared
    line_inserted = await _append_log_entry(
        operation_value=operation_value,
        title=normalized_title,
        summary=summary,
        parsed_timestamp=parsed_timestamp,
        ctx=ctx,
    )
    return _log_append_response(
        status=OperationStatus.SUCCESS.value,
        message="Appended operation entry to log.md",
        line_inserted=line_inserted,
        error=None,
    )
