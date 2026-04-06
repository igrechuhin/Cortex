"""
Plan CRUD: create_plan, list_plans, get_plan.

Implementation module for plan file creation, listing, and reading.
"""

from pathlib import Path
from typing import Literal

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.constitutional_scan import apply_constitutional_compliance
from cortex.tools.plans.crud_helpers import (
    create_error_result,
    create_plan_file,
    create_success_result,
    get_plan_impl,
    list_plans_impl,
)
from cortex.tools.plans.crud_models import (
    CreatePlanResult,
    GetPlanResult,
    ListPlansResult,
    PlanEntry,
)

__all__ = [
    "create_plan",
    "list_plans",
    "get_plan",
    "CreatePlanResult",
    "ListPlansResult",
    "GetPlanResult",
    "PlanEntry",
]


async def _handle_plan_result(
    plan_path: Path | None,
    error: str | None,
    ctx: MCPContext | None,
) -> str:
    """Handle plan creation result."""
    if error:
        await log_client(
            ctx,
            "warning",
            f"create_plan: {error}",
            logger_name=__name__,
        )
        return create_error_result(error).model_dump_json()

    await log_client(
        ctx,
        "info",
        f"create_plan: success - {plan_path}",
        logger_name=__name__,
    )
    return create_success_result(plan_path).model_dump_json()


async def _create_plan_impl(
    title: str,
    content: str,
    slug: str | None,
    ctx: MCPContext | None,
) -> str:
    """Implementation of create_plan logic."""
    await log_client(ctx, "info", "create_plan: starting", logger_name=__name__)

    try:
        root = await resolve_project_root_async(None, ctx)
        final_content, _ = apply_constitutional_compliance(root, content)
        plan_path, error = create_plan_file(root, title, slug, final_content)
        return await _handle_plan_result(plan_path, error, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"create_plan: {e}",
            logger_name=__name__,
        )
        return CreatePlanResult(
            status="error",
            file_path=None,
            message="Unexpected error",
            error=str(e),
        ).model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def create_plan(
    operation: Literal["create", "list", "get"] = "create",
    title: str | None = None,
    content: str | None = None,
    slug: str | None = None,
    include_archive: bool = False,
    response_format: str = "content",
    ctx: MCPContext | None = None,
) -> str:
    """Create, list, or get plan files (single tool for plan CRUD).

    USE WHEN: Creating a plan (operation=create), listing plans (operation=list),
    or reading a plan by slug (operation=get).

    EXAMPLES:
    - create_plan(operation="create", title="Phase 60", content="# Plan...")
    - create_plan(operation="list") or create_plan(operation="list", include_archive=True)
    - create_plan(operation="get", slug="phase-58-multi-agent")

    RETURNS: JSON (CreatePlanResult, ListPlansResult, or GetPlanResult per operation).

    Parameters:
    - operation: 'create' (default), 'list', or 'get'
    - title: Plan title (required when operation=create)
    - content: Full markdown content (required when operation=create)
    - slug: Filename without .md (optional for create; required when operation=get)
    - include_archive: Include archive plans when operation=list (default False)
    - response_format: 'content' or 'metadata' when operation=get (default 'content')
    """
    if operation == "list":
        return await _list_plans_tool_impl(include_archive, ctx)
    if operation == "get":
        if not slug:
            return GetPlanResult(
                status="error",
                slug=None,
                content=None,
                title=None,
                plan_status=None,
                message="slug is required when operation is 'get'",
                error="Missing slug",
            ).model_dump_json()
        return await _get_plan_tool_impl(slug, response_format, ctx)
    if not title or not content:
        return CreatePlanResult(
            status="error",
            file_path=None,
            message="title and content are required when operation is 'create'",
            error="Missing title or content",
        ).model_dump_json()
    return await _create_plan_impl(title, content, slug, ctx)


async def _list_plans_tool_impl(include_archive: bool, ctx: MCPContext | None) -> str:
    """Implementation of list_plans tool."""
    await log_client(ctx, "info", "list_plans: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        result = list_plans_impl(root, include_archive)
        return result.model_dump_json()
    except Exception as e:
        await log_client(ctx, "error", f"list_plans: {e}", logger_name=__name__)
        return ListPlansResult(
            status="error",
            plans=[],
            message="Unexpected error",
            error=str(e),
        ).model_dump_json()


async def list_plans(
    include_archive: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """List plan files in the plans directory (internal / tests; not MCP-registered).

    Deprecated for agents: use ``plan(operation='list')`` (or ``create_plan`` with
    ``operation='list'``) instead. This callable remains for programmatic callers.

    USE WHEN: Checking for existing plans before creating a new one (e.g. Plan prompt
    Step 2.5) or discovering plan slugs for get_plan.

    EXAMPLES: 'list plans', 'list plans include_archive=true', 'what plans exist'.

    RETURNS: JSON with status, plans (list of {slug, title}), and error if any.

    Args:
        include_archive: If True, include plans under .cortex/plans/archive/.
            Default: False.

    Example:
        >>> list_plans()
        {"status": "success", "plans": [{"slug": "phase-58-multi-agent", "title": "Phase 58..."}], "count": 5}
    """
    return await _list_plans_tool_impl(include_archive, ctx)


async def _get_plan_tool_impl(
    slug: str, response_format: str, ctx: MCPContext | None
) -> str:
    """Implementation of get_plan tool."""
    await log_client(ctx, "info", "get_plan: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        result = get_plan_impl(root, slug, response_format)
        return result.model_dump_json()
    except Exception as e:
        await log_client(ctx, "error", f"get_plan: {e}", logger_name=__name__)
        return GetPlanResult(
            status="error",
            slug=slug,
            content=None,
            title=None,
            plan_status=None,
            message="Unexpected error",
            error=str(e),
        ).model_dump_json()


async def get_plan(
    slug: str,
    response_format: str = "content",
    ctx: MCPContext | None = None,
) -> str:
    """Read a plan by slug (internal / tests; not MCP-registered).

    Deprecated for agents: use ``plan(operation='get', slug=...)`` instead. This
    callable remains for programmatic callers.

    USE WHEN: Enriching an existing plan or checking plan content without raw file reads.

    EXAMPLES: 'get_plan(slug="phase-58-multi-agent")', 'get plan phase-9-excellence',
    'get_plan(slug="plan-foo", response_format="metadata")'.

    RETURNS: JSON with status, slug, and either content (full text) or title/plan_status (metadata).

    Args:
        slug: Plan filename without .md (e.g. phase-60-feature or plan-anthropic-context-engineering-alignment).
        response_format: "content" (default) for full markdown; "metadata" for title and status only.

    Example:
        >>> get_plan(slug="phase-58-multi-agent", response_format="metadata")
        {"status": "success", "slug": "phase-58-multi-agent", "title": "Phase 58...", "plan_status": "PENDING", "message": "..."}
    """
    return await _get_plan_tool_impl(slug, response_format, ctx)
