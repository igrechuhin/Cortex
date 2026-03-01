"""Session dispatcher: unified session(operation=...) MCP tool.

Consolidates session_start, session_register, session_deregister, and compact_session
into a single operation-based dispatcher (tool consolidation).
"""

from __future__ import annotations

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


def _session_error_invalid_operation(operation: str) -> str:
    """Build error JSON for invalid session operation."""
    return json.dumps(
        {
            "status": "error",
            "error": (
                f"Invalid operation '{operation}'. "
                "Use start, register, deregister, or compact."
            ),
        },
        indent=2,
    )


async def _session_handle_start(
    task_description: str | None,
    ctx: MCPContext | None,
) -> str:
    """Handle session(operation='start')."""
    from cortex.tools.session.start_tools import session_start as _session_start

    await log_client(ctx, "info", "session(start): starting", logger_name=__name__)
    return await _session_start(task_description=task_description, ctx=ctx)


async def _session_handle_register(
    task_title: str,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Handle session(operation='register')."""
    from cortex.tools.session.registry import (
        session_register as _session_register,
    )

    await log_client(ctx, "info", "session(register): starting", logger_name=__name__)
    return await _session_register(task_title=task_title, role=role, ctx=ctx)


async def _session_handle_deregister(ctx: MCPContext | None) -> str:
    """Handle session(operation='deregister')."""
    from cortex.tools.session.registry import (
        session_deregister as _session_deregister,
    )

    await log_client(ctx, "info", "session(deregister): starting", logger_name=__name__)
    return await _session_deregister(ctx=ctx)


async def _session_handle_compact(
    summary: str | None,
    completed_tasks: list[str] | None,
    in_progress_task: str | None,
    in_progress_notes: str | None,
    blockers: list[str] | None,
    decisions_made: list[str] | None,
    create_checkpoint: bool,
    ctx: MCPContext | None,
) -> str:
    """Handle session(operation='compact')."""
    from cortex.tools.compaction_operations import compact_session as _compact_session

    await log_client(ctx, "info", "session(compact): starting", logger_name=__name__)
    return await _compact_session(
        summary=summary,
        completed_tasks=completed_tasks,
        in_progress_task=in_progress_task,
        in_progress_notes=in_progress_notes,
        blockers=blockers,
        decisions_made=decisions_made,
        create_checkpoint=create_checkpoint,
        ctx=ctx,
    )


def _session_validate(operation: str, task_title: str | None) -> tuple[str | None, str]:
    """Return (error_json or None, op) after validating operation."""
    op = (operation or "start").strip().lower()
    if op not in ("start", "register", "deregister", "compact"):
        return _session_error_invalid_operation(operation or ""), op
    if op == "register" and (not task_title or not str(task_title).strip()):
        return _session_error_register_missing_title(), op
    return None, op


def _session_error_register_missing_title() -> str:
    """Build error JSON when register is missing task_title."""
    return json.dumps(
        {
            "status": "error",
            "error": "task_title is required when operation is 'register'",
        },
        indent=2,
    )


async def _session_dispatch_impl(
    op: str,
    task_description: str | None,
    task_title: str | None,
    role: str | None,
    summary: str | None,
    completed_tasks: list[str] | None,
    in_progress_task: str | None,
    in_progress_notes: str | None,
    blockers: list[str] | None,
    decisions_made: list[str] | None,
    create_checkpoint: bool,
    ctx: MCPContext | None,
) -> str:
    """Dispatch to operation-specific handler."""
    if op == "start":
        return await _session_handle_start(task_description, ctx)
    if op == "register":
        assert task_title is not None and str(task_title).strip()
        return await _session_handle_register(
            task_title=str(task_title).strip(), role=role, ctx=ctx
        )
    if op == "deregister":
        return await _session_handle_deregister(ctx)
    args = (summary, completed_tasks, in_progress_task, in_progress_notes)
    rest = (blockers, decisions_made, create_checkpoint, ctx)
    return await _session_handle_compact(*args, *rest)


@mcp.tool(
    annotations=destructive_annotations(
        "Session (Start/Register/Deregister/Compact)",
    ),
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def session(
    operation: str = "start",
    # start params
    task_description: str | None = None,
    # register params
    task_title: str | None = None,
    role: str | None = None,
    # compact params
    summary: str | None = None,
    completed_tasks: list[str] | None = None,
    in_progress_task: str | None = None,
    in_progress_notes: str | None = None,
    blockers: list[str] | None = None,
    decisions_made: list[str] | None = None,
    create_checkpoint: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Session lifecycle: orientation, register, deregister, or compact (single tool).

    USE WHEN: Starting a session (orientation brief), registering a task for
    multi-agent visibility (Phase 58), deregistering when done, or compacting
    memory bank and writing handoff at end of session.

    RETURNS: JSON. For start: SessionStartResult (brief, token_count). For
    register/deregister: SessionRegistryResult (status, message). For compact:
    status, token_savings, tokens_after, rollback_snapshots. On error:
    status "error" and error message.

    EXAMPLES:
    - session(operation="start") — orientation brief at session start
    - session(operation="register", task_title="Implement Phase 58", role="feature")
    - session(operation="deregister") — when finishing a task
    - session(operation="compact", summary="Implemented Step 1; next: audit")

    Args:
        operation: "start" (default), "register", "deregister", or "compact".
        task_description: For start. Optional task description (reserved).
        task_title: For register. Task title being worked on (required).
        role: For register. Optional agent role (feature, quality, testing, etc.).
        summary: For compact. Optional free-form handoff summary.
        completed_tasks: For compact. Optional list of completed tasks.
        in_progress_task: For compact. Optional task in progress.
        in_progress_notes: For compact. Optional notes for in-progress task.
        blockers: For compact. Optional list of blockers.
        decisions_made: For compact. Optional list of key decisions.
        create_checkpoint: For compact. If True, create git tag cortex/session-*.
    """
    err, op = _session_validate(operation, task_title)
    if err is not None:
        return err
    return await _session_dispatch_impl(
        op,
        task_description,
        task_title,
        role,
        summary,
        completed_tasks,
        in_progress_task,
        in_progress_notes,
        blockers,
        decisions_made,
        create_checkpoint,
        ctx,
    )
