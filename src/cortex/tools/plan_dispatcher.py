"""
Plan dispatcher: unified plan(operation=...) MCP tool.

Consolidates create_plan and complete_plan into a single operation-based dispatcher
following the Phase 50 pattern (query_memory_bank, query_usage).
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


def _plan_error_invalid_operation(operation: str) -> str:
    from cortex.tools.plan_crud import CreatePlanResult

    return CreatePlanResult(
        status="error",
        file_path=None,
        message=f"Invalid operation '{operation}'. Use create, list, get, or complete.",
        error="Invalid operation",
    ).model_dump_json()


def _plan_error_missing_complete_params() -> str:
    from cortex.core.models import OperationStatus
    from cortex.tools.plan_completion_models import CompletePlanResult

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
    from cortex.tools.plan_completion import complete_plan

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
    from cortex.tools.plan_crud import create_plan as _create_plan

    return await _create_plan(
        operation=operation,
        title=title,
        content=content,
        slug=slug,
        include_archive=include_archive,
        response_format=response_format,
        ctx=ctx,
    )


@mcp.tool(annotations=destructive_annotations("Plan (Create/List/Get/Complete)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def plan(
    operation: str = "create",
    # create params
    title: str | None = None,
    content: str | None = None,
    slug: str | None = None,
    # list params
    include_archive: bool = False,
    # get params
    response_format: str = "content",
    # complete params
    plan_title: str | None = None,
    summary: str | None = None,
    completion_date: str | None = None,
    progress_entry: str | None = None,
    plan_file_name: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Create, list, get, or complete plan files (single plan lifecycle tool).

    USE WHEN: Creating a plan (operation=create), listing plans (operation=list),
    reading a plan by slug (operation=get), or completing a plan and moving it
    from roadmap to activeContext (operation=complete).

    EXAMPLES:
    - plan(operation="create", title="Phase 60", content="# Plan...")
    - plan(operation="list") or plan(operation="list", include_archive=True)
    - plan(operation="get", slug="phase-58-multi-agent")
    - plan(operation="complete", plan_title="Session improvements", summary="Tools optimization.", plan_file_name="session-optimization-2026-02-23.md")

    RETURNS: JSON (CreatePlanResult, ListPlansResult, GetPlanResult, or CompletePlanResult per operation).

    Parameters:
    - operation: 'create' (default), 'list', 'get', or 'complete'
    - create: title, content required; slug optional
    - list: include_archive (default False)
    - get: slug required; response_format 'content' or 'metadata'
    - complete: plan_title, summary required; completion_date, progress_entry, plan_file_name optional
    """
    if operation not in ("create", "list", "get", "complete"):
        return _plan_error_invalid_operation(operation)
    if operation == "complete":
        if not plan_title or not summary:
            return _plan_error_missing_complete_params()
        return await _plan_handle_complete(
            plan_title, summary, completion_date, progress_entry, plan_file_name, ctx
        )
    return await _plan_handle_crud(
        operation, title, content, slug, include_archive, response_format, ctx
    )
