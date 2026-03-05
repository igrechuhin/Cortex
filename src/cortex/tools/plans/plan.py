"""
Plan dispatcher: unified plan(operation=...) MCP tool.

Consolidates create_plan, complete_plan, and register_plan_in_roadmap into a single
operation-based dispatcher following the Phase 50 pattern (query_memory_bank, query_usage).
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


def _plan_error_invalid_operation(operation: str) -> str:
    from cortex.tools.plans.crud import CreatePlanResult

    return CreatePlanResult(
        status="error",
        file_path=None,
        message=f"Invalid operation '{operation}'. Use create, list, get, complete, or register.",
        error="Invalid operation",
    ).model_dump_json()


def _plan_error_missing_complete_params() -> str:
    from cortex.core.models import OperationStatus
    from cortex.tools.plans.completion_models import CompletePlanResult

    return CompletePlanResult(
        status=OperationStatus.ERROR,
        message="plan_title and summary are required when operation is 'complete'",
        roadmap_line_removed=None,
        active_context_line_inserted=None,
        progress_line_inserted=None,
        archive_path=None,
        error="Missing plan_title or summary",
    ).model_dump_json()


async def _plan_handle_complete(
    plan_title: str,
    summary: str,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.completion import complete_plan

    return await complete_plan(
        plan_title=plan_title,
        summary=summary,
        completion_date=completion_date,
        progress_entry=progress_entry,
        plan_file_name=plan_file_name,
        ctx=ctx,
    )


async def _plan_handle_crud(
    operation: str,
    title: str | None,
    content: str | None,
    slug: str | None,
    include_archive: bool,
    response_format: str,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.crud import create_plan as _create_plan

    return await _create_plan(
        operation=operation,
        title=title,
        content=content,
        slug=slug,
        include_archive=include_archive,
        response_format=response_format,
        ctx=ctx,
    )


def _plan_error_missing_register_params() -> str:
    from cortex.tools.plans.register_models import RegisterPlanResult

    return RegisterPlanResult(
        status="error",
        file_name="roadmap.md",
        message="plan_title and description are required when operation is 'register'",
        line_inserted=None,
        section=None,
        error="Missing plan_title or description",
    ).model_dump_json()


async def _plan_handle_register(
    plan_title: str,
    description: str,
    status: str,
    section: str,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.register import register_plan_in_roadmap

    return await register_plan_in_roadmap(
        plan_title=plan_title,
        description=description,
        status=status,
        section=section,
        ctx=ctx,
    )


async def _plan_dispatch_complete(
    plan_title: str | None,
    summary: str | None,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    ctx: MCPContext | None,
) -> str:
    if not plan_title or not summary:
        return _plan_error_missing_complete_params()
    assert plan_title is not None and summary is not None
    return await _plan_handle_complete(
        plan_title, summary, completion_date, progress_entry, plan_file_name, ctx
    )


async def _plan_dispatch_register(
    plan_title: str | None,
    description: str | None,
    status: str,
    section: str,
    ctx: MCPContext | None,
) -> str:
    if not plan_title or not description:
        return _plan_error_missing_register_params()
    assert plan_title is not None and description is not None
    return await _plan_handle_register(plan_title, description, status, section, ctx)


async def _plan_dispatch(
    operation: str,
    title: str | None,
    content: str | None,
    slug: str | None,
    include_archive: bool,
    response_format: str,
    plan_title: str | None,
    summary: str | None,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    description: str | None,
    status: str,
    section: str,
    ctx: MCPContext | None,
) -> str:
    """Dispatch plan(operation=...) to the appropriate handler."""
    if operation not in ("create", "list", "get", "complete", "register"):
        return _plan_error_invalid_operation(operation)
    if operation == "complete":
        return await _plan_dispatch_complete(
            plan_title, summary, completion_date, progress_entry, plan_file_name, ctx
        )
    if operation == "register":
        return await _plan_dispatch_register(
            plan_title, description, status, section, ctx
        )
    return await _plan_handle_crud(
        operation, title, content, slug, include_archive, response_format, ctx
    )


@mcp.tool(
    annotations=destructive_annotations("Plan (Create/List/Get/Complete/Register)")
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def plan(
    operation: str = "create",
    title: str | None = None,
    content: str | None = None,
    slug: str | None = None,
    include_archive: bool = False,
    response_format: str = "content",
    plan_title: str | None = None,
    summary: str | None = None,
    completion_date: str | None = None,
    progress_entry: str | None = None,
    plan_file_name: str | None = None,
    description: str | None = None,
    status: str = "PENDING",
    section: str = "pending",
    ctx: MCPContext | None = None,
) -> str:
    """Plan lifecycle: create, list, get, complete, or register in roadmap.

    USE WHEN: You need to create or update plans under .cortex/plans/, mark a
    plan as complete (with memory-bank updates), or register a plan entry in
    roadmap.md.

    EXAMPLES: 'plan(operation=\"create\", title=\"Phase 92\", content=\"...\")',
    'plan(operation=\"complete\", plan_title=\"Phase 92\", summary=\"Done\")',
    'plan(operation=\"register\", plan_title=\"Phase 92\", description=\"Improve tool docs\")'.
    """
    return await _plan_dispatch(
        operation,
        title,
        content,
        slug,
        include_archive,
        response_format,
        plan_title,
        summary,
        completion_date,
        progress_entry,
        plan_file_name,
        description,
        status,
        section,
        ctx,
    )
