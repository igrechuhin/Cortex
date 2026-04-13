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
from cortex.core.models import OperationStatus
from cortex.core.progress_types import SessionProgress, report_structured_progress
from cortex.server import mcp
from cortex.tools.models_base import StrictBaseModel


class _SessionDispatchArgs(StrictBaseModel):
    task_description: str | None
    task_title: str | None
    role: str | None
    summary: str | None
    completed_tasks: list[str] | None
    in_progress_task: str | None
    in_progress_notes: str | None
    blockers: list[str] | None
    decisions_made: list[str] | None
    create_checkpoint: bool
    goal: str | None
    plan_slug: str | None
    blocked_files: list[str] | None


def _session_error_invalid_operation(operation: str) -> str:
    """Build error JSON for invalid session operation."""
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": (
                f"Invalid operation '{operation}'. "
                "Use start, register, deregister, or compact."
            ),
        },
        indent=2,
    )


async def _session_handle_start(
    task_description: str | None,
    goal: str | None,
    plan_slug: str | None,
    blocked_files: list[str] | None,
    ctx: MCPContext | None,
) -> str:
    """Handle session(operation='start')."""
    from cortex.tools.session.start_tools import session_start as _session_start

    await _emit_session_dispatch_progress(ctx, "start", "Starting session operation")
    return await _session_start(
        task_description=task_description,
        goal=goal,
        plan_slug=plan_slug,
        blocked_files=blocked_files,
        ctx=ctx,
    )


async def _session_handle_register(
    task_title: str,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Handle session(operation='register')."""
    from cortex.tools.session.registry import (
        session_register as _session_register,
    )

    await _emit_session_dispatch_progress(ctx, "register", "Registering session task")
    return await _session_register(task_title=task_title, role=role, ctx=ctx)


async def _session_handle_deregister(ctx: MCPContext | None) -> str:
    """Handle session(operation='deregister')."""
    from cortex.tools.session.registry import (
        session_deregister as _session_deregister,
    )

    await _emit_session_dispatch_progress(
        ctx, "deregister", "Deregistering current session"
    )
    return await _session_deregister(ctx=ctx)


async def _emit_session_dispatch_progress(
    ctx: MCPContext | None, operation: str, message: str
) -> None:
    """Emit standard structured progress + log for session dispatch actions."""
    await report_structured_progress(
        ctx,
        SessionProgress(
            tool="session",
            phase="dispatch",
            message=message,
            operation=operation,
        ),
        current=1,
        total=1,
    )
    await log_client(
        ctx, "info", f"session({operation}): starting", logger_name=__name__
    )


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
    from cortex.tools.memory.compaction_operations import (
        compact_session as _compact_session,
    )

    await _emit_session_dispatch_progress(ctx, "compact", "Compacting session memory")
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
            "status": OperationStatus.ERROR.value,
            "error": "task_title is required when operation is 'register'",
        },
        indent=2,
    )


async def _session_dispatch_start(
    task_description: str | None,
    goal: str | None,
    plan_slug: str | None,
    blocked_files: list[str] | None,
    ctx: MCPContext | None,
) -> str:
    return await _session_handle_start(
        task_description, goal, plan_slug, blocked_files, ctx
    )


async def _session_dispatch_register(
    task_title: str | None, role: str | None, ctx: MCPContext | None
) -> str:
    assert task_title is not None and str(task_title).strip()
    return await _session_handle_register(
        task_title=str(task_title).strip(), role=role, ctx=ctx
    )


async def _session_dispatch_compact(
    summary: str | None,
    completed_tasks: list[str] | None,
    in_progress_task: str | None,
    in_progress_notes: str | None,
    blockers: list[str] | None,
    decisions_made: list[str] | None,
    create_checkpoint: bool,
    ctx: MCPContext | None,
) -> str:
    return await _session_handle_compact(
        summary,
        completed_tasks,
        in_progress_task,
        in_progress_notes,
        blockers,
        decisions_made,
        create_checkpoint,
        ctx,
    )


async def _session_dispatch_impl(
    op: str,
    args: _SessionDispatchArgs,
    ctx: MCPContext | None,
) -> str:
    if op == "start":
        return await _session_dispatch_start(
            args.task_description, args.goal, args.plan_slug, args.blocked_files, ctx
        )
    if op == "register":
        return await _session_dispatch_register(args.task_title, args.role, ctx)
    if op == "deregister":
        return await _session_handle_deregister(ctx)
    return await _session_dispatch_compact_from_args(args, ctx)


async def _session_dispatch_compact_from_args(
    args: _SessionDispatchArgs,
    ctx: MCPContext | None,
) -> str:
    return await _session_dispatch_compact(
        args.summary,
        args.completed_tasks,
        args.in_progress_task,
        args.in_progress_notes,
        args.blockers,
        args.decisions_made,
        args.create_checkpoint,
        ctx,
    )


async def _session_run(
    operation: str,
    task_description: str | None,
    goal: str | None,
    plan_slug: str | None,
    blocked_files: list[str] | None,
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
    err, op = _session_validate(operation, task_title)
    if err is not None:
        return err
    args = _session_build_dispatch_args(
        {
            k: v
            for k, v in locals().items()
            if k not in {"operation", "ctx", "err", "op"}
        }
    )
    return await _session_dispatch_impl_from_args(op, args, ctx)


async def _session_dispatch_impl_from_args(
    op: str,
    args: _SessionDispatchArgs,
    ctx: MCPContext | None,
) -> str:
    return await _session_dispatch_impl(op, args, ctx)


def _session_build_dispatch_args(values: dict[str, object]) -> _SessionDispatchArgs:
    return _SessionDispatchArgs.model_validate(values)


@mcp.tool(
    annotations=destructive_annotations(
        "Session (Start/Register/Deregister/Compact)",
    ),
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
# fmt: off
async def session(
    operation: str = "start", task_description: str | None = None,
    goal: str | None = None, plan_slug: str | None = None,
    blocked_files: list[str] | None = None, task_title: str | None = None,
    role: str | None = None, summary: str | None = None,
    completed_tasks: list[str] | None = None, in_progress_task: str | None = None,
    in_progress_notes: str | None = None, blockers: list[str] | None = None,
    decisions_made: list[str] | None = None, create_checkpoint: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    # fmt: on
    """USE WHEN: Session lifecycle (orientation, registry, compaction).

    EXAMPLES: session(operation="start", goal="Fix auth bug");
    session(operation="compact", summary="Session handoff").
    """
    return await _session_run(
        operation,
        task_description,
        goal,
        plan_slug,
        blocked_files,
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
