"""
Plan dispatcher: unified plan(operation=...) MCP tool.

Consolidates create_plan, complete_plan, and register_plan_in_roadmap into a single
operation-based dispatcher following the Phase 50 pattern (query_memory_bank, query_usage).
"""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import PlanToolOperation
from cortex.server import mcp
from cortex.tools.models_base import StrictBaseModel


class _PlanDispatchWire(StrictBaseModel):
    """Raw ``plan()`` tool parameters (``operation`` is a wire string until coercion)."""

    operation: str | None = None
    title: str | None = None
    content: str | None = None
    slug: str | None = None
    explore_log_path: str | None = None
    include_archive: bool = False
    response_format: str = "content"
    plan_title: str | None = None
    summary: str | None = None
    completion_date: str | None = None
    progress_entry: str | None = None
    plan_file_name: str | None = None
    plan_relative_path: str | None = None
    resolved_clarifications: dict[str, str] | None = None
    description: str | None = None
    status: str = "PENDING"
    section: str = "pending"
    planning_mode: str | None = None
    step_section: str | None = None
    step_skip: bool = False
    section_corrections: str | None = None


_PLAN_WIRE_KEYS: frozenset[str] = frozenset(_PlanDispatchWire.model_fields.keys())


class _PlanDispatchRequest(StrictBaseModel):
    """Normalized ``plan()`` kwargs; wire-level ``title`` is merged into ``plan_title`` before validate."""

    operation: PlanToolOperation
    plan_title: str | None
    content: str | None
    slug: str | None
    explore_log_path: str | None
    include_archive: bool
    response_format: str
    summary: str | None
    completion_date: str | None
    progress_entry: str | None
    plan_file_name: str | None
    plan_relative_path: str | None
    resolved_clarifications: dict[str, str] | None
    description: str | None
    status: str
    section: str
    planning_mode: str | None = None
    step_section: str | None = None
    step_skip: bool = False
    section_corrections: str | None = None


def _plan_error_invalid_operation(operation: str) -> str:
    from cortex.tools.plans.crud import CreatePlanResult

    return CreatePlanResult(
        status="error",
        file_path=None,
        message=(
            "Invalid operation "
            f"'{operation}'. Use create, list, get, complete, register, enrich, "
            "graph, archive_completed, continue_step, approve_step, or finalize_step."
        ),
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
        plans_unblocked=None,
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
    explore_log_path: str | None,
    include_archive: bool,
    response_format: str,
    planning_mode: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.crud import create_plan as _create_plan

    return await _create_plan(
        operation=operation,
        title=title,
        content=content,
        slug=slug,
        explore_log_path=explore_log_path,
        include_archive=include_archive,
        response_format=response_format,
        planning_mode=planning_mode,
        ctx=ctx,
    )


def _plan_error_missing_register_params() -> str:
    from cortex.tools.models_base import ToolResultStatus
    from cortex.tools.plans.register_models import RegisterPlanResult

    return RegisterPlanResult(
        status=ToolResultStatus.ERROR,
        file_name="roadmap.md",
        message="plan_title and description are required when operation is 'register'",
        line_inserted=None,
        section=None,
        error="Missing plan_title or description",
        parallel_steps_count=None,
        sequential_steps_count=None,
    ).model_dump_json()


async def _plan_handle_register(
    plan_title: str,
    description: str,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.register import register_plan_in_roadmap

    return await register_plan_in_roadmap(
        plan_title=plan_title,
        description=description,
        status=status,
        section=section,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
        ctx=ctx,
    )


async def _plan_handle_enrich(
    slug: str | None,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    resolved_clarifications: dict[str, str] | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.enrich import enrich_plan

    return await enrich_plan(
        slug=slug,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
        resolved_clarifications=resolved_clarifications,
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
    return await _plan_handle_complete(
        plan_title, summary, completion_date, progress_entry, plan_file_name, ctx
    )


async def _plan_dispatch_register(
    plan_title: str | None,
    description: str | None,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    if not plan_title or not description:
        return _plan_error_missing_register_params()
    return await _plan_handle_register(
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
    )


async def _plan_handle_archive_completed(ctx: MCPContext | None) -> str:
    """Scan .cortex/plans/ for status: COMPLETE and archive each one."""
    import json
    import re

    from cortex.core.path_resolver import CortexResourceType, get_cortex_path
    from cortex.core.usage_context import get_or_resolve_project_root
    from cortex.tools.plans.completion_archive import archive_plan_file

    root_str = await get_or_resolve_project_root(ctx)
    from pathlib import Path

    root = Path(root_str)
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    archived: list[str] = []
    errors: list[str] = []
    for plan_path in sorted(plans_dir.glob("*.md")):
        try:
            head = plan_path.read_text(encoding="utf-8")[:500]
        except OSError:
            continue
        if re.search(r'status:\s*["\']?COMPLETE', head, re.IGNORECASE):
            dest, err = archive_plan_file(root, plan_path.name)
            if err:
                errors.append(f"{plan_path.name}: {err}")
            elif dest:
                archived.append(plan_path.name)
    return json.dumps(
        {"status": "ok", "archived": archived, "errors": errors, "count": len(archived)}
    )


def _plan_request_has_required_args(request: _PlanDispatchRequest) -> bool:
    """Return True when required fields for *request.operation* are populated."""
    op = request.operation
    if op == PlanToolOperation.COMPLETE:
        return bool(request.plan_title and request.summary)
    if op == PlanToolOperation.REGISTER:
        return bool(request.plan_title and request.description)
    if op == PlanToolOperation.CREATE:
        return bool(request.plan_title and request.content)
    if op == PlanToolOperation.ENRICH:
        return bool(
            request.slug or request.plan_file_name or request.plan_relative_path
        )
    if op == PlanToolOperation.CONTINUE_STEP:
        return bool(request.slug and request.content and request.content.strip())
    if op == PlanToolOperation.APPROVE_STEP:
        return bool(request.slug and request.step_section)
    if op == PlanToolOperation.FINALIZE_STEP:
        return bool(request.slug and request.plan_title and request.description)
    return True


async def _append_plan_create_log(
    result_str: str, title: str | None, ctx: MCPContext | None
) -> None:
    from cortex.tools.plans.operations_log import OperationsLogType
    from cortex.tools.plans.operations_log_hooks import (
        append_log_entry_best_effort,
        parse_json_object,
    )

    result_obj = parse_json_object(result_str)
    if result_obj and result_obj.get("status") == "success" and title:
        await append_log_entry_best_effort(
            operation_type=OperationsLogType.PLAN,
            title=f"Created plan: {title.strip()}",
            summary=None,
            ctx=ctx,
        )


async def _append_plan_complete_log(
    result_str: str, plan_title: str | None, summary: str | None, ctx: MCPContext | None
) -> None:
    from cortex.tools.plans.operations_log import OperationsLogType
    from cortex.tools.plans.operations_log_hooks import (
        append_log_entry_best_effort,
        parse_json_object,
    )

    result_obj = parse_json_object(result_str)
    if result_obj and result_obj.get("status") == "success" and plan_title:
        await append_log_entry_best_effort(
            operation_type=OperationsLogType.PLAN,
            title=f"Completed plan: {plan_title.strip()}",
            summary=summary.strip() if summary else None,
            ctx=ctx,
        )


def _coerce_plan_tool_operation(raw: str | None) -> PlanToolOperation | None:
    """Map wire string to :class:`PlanToolOperation`; ``None``/empty defaults to list."""
    if raw is None or raw == "":
        return PlanToolOperation.LIST
    try:
        return PlanToolOperation(raw)
    except ValueError:
        return None


async def _log_plan_operation(
    ctx: MCPContext | None, operation: str, has_required: bool
) -> None:
    await log_client(
        ctx,
        "info",
        f"plan: operation={operation}, required_args_present={has_required}",
        logger_name=__name__,
    )


async def _plan_dispatch(
    inputs: _PlanDispatchWire,
    ctx: MCPContext | None,
) -> str:
    """Dispatch plan(operation=...) to the appropriate handler."""
    resolved_op = _coerce_plan_tool_operation(inputs.operation)
    if resolved_op is None:
        return _plan_error_invalid_operation(inputs.operation or "")
    request = _request_from_plan_wire(inputs, resolved_op)
    has_required = _plan_request_has_required_args(request)
    await _log_plan_operation(ctx, resolved_op.value, has_required)
    return await _plan_dispatch_valid_operation(request, ctx)


def _merge_create_title_into_plan_title(payload: dict[str, object]) -> None:
    """Fold legacy ``title`` into ``plan_title`` so one field serves create and lifecycle ops."""
    legacy = payload.pop("title", None)
    current = payload.get("plan_title")
    if current is not None and isinstance(current, str) and current.strip():
        return
    if legacy is not None:
        payload["plan_title"] = legacy


def _build_plan_dispatch_request(
    values: dict[str, object],
) -> _PlanDispatchRequest:
    data = dict(values)
    _merge_create_title_into_plan_title(data)
    return _PlanDispatchRequest.model_validate(data)


def _request_from_plan_wire(
    inputs: _PlanDispatchWire,
    resolved_op: PlanToolOperation,
) -> _PlanDispatchRequest:
    data: dict[str, object] = {**inputs.model_dump(), "operation": resolved_op}
    return _build_plan_dispatch_request(data)


async def _dispatch_continue_step(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.step_plan_workflow import handle_continue_step

    return await handle_continue_step(request.slug, request.content, ctx)


async def _dispatch_approve_step(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.step_plan_workflow import handle_approve_step

    return await handle_approve_step(
        request.slug,
        request.step_section,
        request.section_corrections,
        request.step_skip,
        ctx,
    )


async def _dispatch_finalize_step(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.step_plan_workflow import handle_finalize_step

    return await handle_finalize_step(
        request.slug,
        request.plan_title,
        request.description,
        request.status,
        request.section,
        request.plan_file_name,
        request.plan_relative_path,
        ctx,
    )


async def _try_dispatch_step_plan_tool(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str | None:
    op = request.operation
    if op == PlanToolOperation.CONTINUE_STEP:
        return await _dispatch_continue_step(request, ctx)
    if op == PlanToolOperation.APPROVE_STEP:
        return await _dispatch_approve_step(request, ctx)
    if op == PlanToolOperation.FINALIZE_STEP:
        return await _dispatch_finalize_step(request, ctx)
    return None


async def _handle_special_plan_operations(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str | None:
    op = request.operation
    if op == PlanToolOperation.GRAPH:
        from cortex.tools.plans.plan_graph import plan_graph_json

        return await plan_graph_json(ctx, include_archive=request.include_archive)
    if op == PlanToolOperation.ARCHIVE_COMPLETED:
        return await _plan_handle_archive_completed(ctx)
    if op == PlanToolOperation.COMPLETE:
        return await _dispatch_complete_with_log(
            request.plan_title,
            request.summary,
            request.completion_date,
            request.progress_entry,
            request.plan_file_name,
            ctx,
        )
    step_result = await _try_dispatch_step_plan_tool(request, ctx)
    if step_result is not None:
        return step_result
    return await _handle_register_or_enrich(request, ctx)


async def _handle_register_or_enrich(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str | None:
    if request.operation == PlanToolOperation.REGISTER:
        return await _plan_dispatch_register(
            request.plan_title,
            request.description,
            request.status,
            request.section,
            request.plan_file_name,
            request.plan_relative_path,
            ctx,
        )
    if request.operation == PlanToolOperation.ENRICH:
        return await _plan_handle_enrich(
            request.slug,
            request.plan_file_name,
            request.plan_relative_path,
            request.resolved_clarifications,
            ctx,
        )
    return None


async def _dispatch_complete_with_log(
    plan_title: str | None,
    summary: str | None,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    ctx: MCPContext | None,
) -> str:
    result_str = await _plan_dispatch_complete(
        plan_title, summary, completion_date, progress_entry, plan_file_name, ctx
    )
    await _append_plan_complete_log(result_str, plan_title, summary, ctx)
    return result_str


async def _plan_dispatch_valid_operation(
    request: _PlanDispatchRequest,
    ctx: MCPContext | None,
) -> str:
    special_result = await _handle_special_plan_operations(request, ctx)
    if special_result is not None:
        return special_result
    result_str = await _plan_handle_crud(
        request.operation.value,
        request.plan_title,
        request.content,
        request.slug,
        request.explore_log_path,
        request.include_archive,
        request.response_format,
        request.planning_mode,
        ctx,
    )
    if request.operation == PlanToolOperation.CREATE:
        await _append_plan_create_log(result_str, request.plan_title, ctx)
    return result_str


@mcp.tool(
    annotations=destructive_annotations("Plan (Create/List/Get/Complete/Register)")
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
# fmt: off
async def plan(operation: str | None = None, title: str | None = None, content: str | None = None, slug: str | None = None, explore_log_path: str | None = None, include_archive: bool = False, response_format: str = "content", plan_title: str | None = None, summary: str | None = None, completion_date: str | None = None, progress_entry: str | None = None, plan_file_name: str | None = None, plan_relative_path: str | None = None, resolved_clarifications: dict[str, str] | None = None, description: str | None = None, status: str = "PENDING", section: str = "pending", planning_mode: str | None = None, step_section: str | None = None, step_skip: bool = False, section_corrections: str | None = None, ctx: MCPContext | None = None) -> str:
# fmt: on
    """Plan lifecycle: create, list, get, complete, register, graph, or archive_completed.

    USE WHEN: managing plan files, marking plans complete, registering roadmap entries,
    or reading the plan dependency graph (operation=\"graph\").
    EXAMPLES: plan(operation=\"create\", ...), plan(operation=\"graph\"), plan(operation=\"register\", ...).
    """
    wire_payload = {name: locals()[name] for name in _PLAN_WIRE_KEYS}
    return await _plan_dispatch(
        _PlanDispatchWire.model_validate(wire_payload),
        ctx,
    )
