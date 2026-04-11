"""
Plan roadmap: register_plan_in_roadmap.

Implementation module for registering plan entries in roadmap.md.
"""

from dataclasses import dataclass
from pathlib import Path

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_MEDIUM,
    MemoryBankFile,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_utils import (
    PlanValidationError,
    find_clarification_markers,
    parse_task_graph,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.register_helpers import (
    SectionValidation,
    create_register_error_result,
    create_register_success_result,
    is_completed_status,
    read_roadmap_file,
    register_plan_entry,
    validate_registration_section,
    write_roadmap_file,
)
from cortex.tools.plans.register_models import RegisterPlanResult

_ROADMAP_COMPLETED_STATUS_MESSAGE = (
    "Roadmap records future/upcoming work only. "
    "Completed work belongs in activeContext.md. Use status 'PENDING' or 'IN PROGRESS'."
)


@dataclass(frozen=True, slots=True)
class _SectionCheck:
    section_id: str | None
    error_json: str | None


@dataclass(frozen=True, slots=True)
class _ClarificationGateDecision:
    status: str
    description: str


@dataclass(frozen=True, slots=True)
class _RegisterPlanExecParams:
    root: Path
    plan_title: str
    description: str
    status: str
    section_id: str
    plan_file_name: str | None
    plan_relative_path: str | None
    ctx: MCPContext | None
    parallel_steps_count: int | None
    sequential_steps_count: int | None


def _resolve_plan_path_for_marker_scan(
    root: Path, plan_file_name: str | None, plan_relative_path: str | None
) -> Path | None:
    if plan_relative_path:
        return root / plan_relative_path
    if plan_file_name:
        return get_cortex_path(root, CortexResourceType.PLANS) / plan_file_name
    return None


def _validate_plan_task_graph_before_register(
    root: Path,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> tuple[str | None, int | None, int | None]:
    """Validate plan task graph when a plan path is known.

    Returns ``(error_json, parallel_steps_count, sequential_steps_count)``.
    When no plan file is resolved, returns ``(None, None, None)`` (skip validation).
    """
    plan_path = _resolve_plan_path_for_marker_scan(
        root, plan_file_name, plan_relative_path
    )
    if plan_path is None or not plan_path.exists():
        return (None, None, None)
    try:
        raw = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            create_register_error_result(
                f"Cannot read plan for task graph: {exc}"
            ).model_dump_json(),
            None,
            None,
        )
    try:
        nodes = parse_task_graph(raw)
    except PlanValidationError as exc:
        return (create_register_error_result(str(exc)).model_dump_json(), None, None)
    parallel_steps_count = sum(1 for node in nodes if node.parallel)
    sequential_steps_count = sum(1 for node in nodes if not node.parallel)
    return (None, parallel_steps_count, sequential_steps_count)


def _append_clarification_note(base: str, note: str) -> str:
    base_clean = base.rstrip()
    if note in base_clean:
        return base_clean
    if not base_clean:
        return note
    if base_clean.endswith("."):
        return f"{base_clean} {note}"
    return f"{base_clean}. {note}"


def _gate_registration_on_clarifications(
    root: Path,
    description: str,
    status: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> _ClarificationGateDecision:
    plan_path = _resolve_plan_path_for_marker_scan(
        root, plan_file_name, plan_relative_path
    )
    if plan_path is None or not plan_path.exists():
        return _ClarificationGateDecision(status=status, description=description)
    markers = find_clarification_markers(plan_path.read_text(encoding="utf-8"))
    if not markers:
        return _ClarificationGateDecision(status=status, description=description)
    blocking_count = sum(1 for marker in markers if marker.blocking)
    if blocking_count > 0:
        note = (
            f"Blocked: {blocking_count} clarifications required before implementation."
        )
        return _ClarificationGateDecision(
            status="BLOCKED",
            description=_append_clarification_note(description, note),
        )
    note = f"{len(markers)} clarifications pending (non-blocking)."
    return _ClarificationGateDecision(
        status="PENDING",
        description=_append_clarification_note(description, note),
    )


async def _handle_roadmap_read(
    roadmap_path: Path,
    ctx: MCPContext | None,
) -> str | None:
    """Read roadmap or return error JSON. Returns error JSON or None."""
    _, read_error = read_roadmap_file(roadmap_path)
    if read_error:
        await log_client(
            ctx,
            "warning",
            f"register_plan_in_roadmap: {read_error}",
            logger_name=__name__,
        )
        return create_register_error_result(read_error).model_dump_json()
    return None


async def _handle_roadmap_write(
    roadmap_path: Path,
    updated_content: str,
    section_id: str,
    ctx: MCPContext | None,
    project_root: Path | None = None,
) -> str | None:
    """Write roadmap or return error JSON. Returns error JSON or None."""
    write_error = await write_roadmap_file(roadmap_path, updated_content, project_root)
    if write_error:
        await log_client(
            ctx,
            "error",
            f"register_plan_in_roadmap: {write_error}",
            logger_name=__name__,
        )
        return create_register_error_result(write_error).model_dump_json()
    return None


def _do_register_plan_entry(
    current_content: str,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> tuple[str, int | None]:
    """Register plan entry and return (content, line_inserted)."""
    return register_plan_entry(
        current_content,
        plan_title,
        description,
        status,
        section_id,
        "last",
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
    )


async def _handle_entry_not_found(
    ctx: MCPContext | None,
    section_id: str,
) -> str:
    """Handle case when section is not found in roadmap."""
    await log_client(
        ctx,
        "warning",
        f"register_plan_in_roadmap: Section {section_id} not found",
        logger_name=__name__,
    )
    error_msg = f"Section '{section_id}' not found in roadmap"
    return create_register_error_result(error_msg).model_dump_json()


async def _handle_entry_success(
    ctx: MCPContext | None,
    section_id: str,
    line_inserted: int,
    *,
    parallel_steps_count: int | None = None,
    sequential_steps_count: int | None = None,
) -> str:
    """Handle successful plan registration."""
    await log_client(
        ctx,
        "info",
        f"register_plan_in_roadmap: success - line {line_inserted}",
        logger_name=__name__,
    )
    return create_register_success_result(
        section_id,
        line_inserted,
        parallel_steps_count=parallel_steps_count,
        sequential_steps_count=sequential_steps_count,
    ).model_dump_json()


async def _read_and_register_entry(
    roadmap_path: Path,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> tuple[str, int | None] | str:
    """Read roadmap and register entry. Returns (updated_content, line) or error JSON."""
    read_result = await _handle_roadmap_read(roadmap_path, ctx)
    if read_result:
        return read_result
    current_content, _ = read_roadmap_file(roadmap_path)
    assert current_content is not None
    return _do_register_plan_entry(
        current_content,
        plan_title,
        description,
        status,
        section_id,
        plan_file_name,
        plan_relative_path,
    )


def _roadmap_path(root: Path) -> Path:
    return (
        get_cortex_path(root, CortexResourceType.MEMORY_BANK) / MemoryBankFile.ROADMAP
    )


async def _finish_register_from_read_result(
    rp: Path,
    root: Path,
    ctx: MCPContext | None,
    section_id: str,
    read_result: str | tuple[str, int | None],
    parallel_steps_count: int | None,
    sequential_steps_count: int | None,
) -> str:
    """Branch on read/merge outcome and persist when possible."""
    if isinstance(read_result, str):
        return read_result
    updated_content, line_inserted = read_result
    if line_inserted is None:
        return await _handle_entry_not_found(ctx, section_id)
    return await _persist_register_merge(
        rp,
        root,
        section_id,
        ctx,
        updated_content,
        line_inserted,
        parallel_steps_count,
        sequential_steps_count,
    )


async def _persist_register_merge(
    rp: Path,
    root: Path,
    section_id: str,
    ctx: MCPContext | None,
    updated_content: str,
    line_inserted: int,
    parallel_steps_count: int | None,
    sequential_steps_count: int | None,
) -> str:
    """Write roadmap after merge and emit success JSON."""
    write_result = await _handle_roadmap_write(
        rp, updated_content, section_id, ctx, root
    )
    return write_result or await _handle_entry_success(
        ctx,
        section_id,
        line_inserted,
        parallel_steps_count=parallel_steps_count,
        sequential_steps_count=sequential_steps_count,
    )


async def _execute_register_plan(params: _RegisterPlanExecParams) -> str:
    """Execute plan registration. Returns JSON result."""
    rp = _roadmap_path(params.root)
    read_result = await _read_and_register_entry(
        rp,
        params.plan_title,
        params.description,
        params.status,
        params.section_id,
        params.plan_file_name,
        params.plan_relative_path,
        params.ctx,
    )
    return await _finish_register_from_read_result(
        rp,
        params.root,
        params.ctx,
        params.section_id,
        read_result,
        params.parallel_steps_count,
        params.sequential_steps_count,
    )


async def _check_status_and_section(
    status: str, section: str, ctx: MCPContext | None
) -> _SectionCheck:
    """Validate status and section."""
    if is_completed_status(status):
        await log_client(
            ctx,
            "warning",
            "register_plan_in_roadmap: rejected COMPLETED status",
            logger_name=__name__,
        )
        return _SectionCheck(
            section_id=None,
            error_json=create_register_error_result(
                _ROADMAP_COMPLETED_STATUS_MESSAGE
            ).model_dump_json(),
        )
    sv: SectionValidation = validate_registration_section(section)
    if sv.error_message:
        await log_client(
            ctx,
            "warning",
            f"register_plan_in_roadmap: {sv.error_message}",
            logger_name=__name__,
        )
        return _SectionCheck(
            section_id=None,
            error_json=create_register_error_result(sv.error_message).model_dump_json(),
        )
    return _SectionCheck(section_id=sv.section_id, error_json=None)


async def _register_after_section_ok(
    root: Path,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    """Run task-graph validation then persist roadmap entry."""
    ge, pc, sc = _validate_plan_task_graph_before_register(
        root, plan_file_name, plan_relative_path
    )
    if ge is not None:
        return ge
    return await _execute_register_plan(
        _RegisterPlanExecParams(
            root=root,
            plan_title=plan_title,
            description=description,
            status=status,
            section_id=section_id,
            plan_file_name=plan_file_name,
            plan_relative_path=plan_relative_path,
            ctx=ctx,
            parallel_steps_count=pc,
            sequential_steps_count=sc,
        )
    )


async def _validate_and_execute_register(
    section: str,
    root: Path,
    plan_title: str,
    description: str,
    status: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    """Validate section and execute registration."""
    check = await _check_status_and_section(status, section, ctx)
    if check.error_json is not None:
        return check.error_json
    assert check.section_id is not None
    return await _register_after_section_ok(
        root,
        plan_title,
        description,
        status,
        check.section_id,
        plan_file_name,
        plan_relative_path,
        ctx,
    )


def _register_plan_error_result(e: Exception) -> str:
    return RegisterPlanResult(
        status=ToolResultStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Unexpected error",
        line_inserted=None,
        section=None,
        error=str(e),
        parallel_steps_count=None,
        sequential_steps_count=None,
    ).model_dump_json()


async def _register_plan_impl(
    plan_title: str,
    description: str,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    """Implementation of register_plan_in_roadmap logic."""
    await log_client(
        ctx, "info", "register_plan_in_roadmap: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        return await _execute_register_with_clarification_gate(
            root,
            section,
            plan_title,
            description,
            status,
            plan_file_name,
            plan_relative_path,
            ctx,
        )
    except Exception as e:
        await log_client(
            ctx, "error", f"register_plan_in_roadmap: {e}", logger_name=__name__
        )
        return _register_plan_error_result(e)


async def _execute_register_with_clarification_gate(
    root: Path,
    section: str,
    plan_title: str,
    description: str,
    status: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    gated = _gate_registration_on_clarifications(
        root, description, status, plan_file_name, plan_relative_path
    )
    return await _validate_and_execute_register(
        section,
        root,
        plan_title,
        gated.description,
        gated.status,
        plan_file_name,
        plan_relative_path,
        ctx,
    )


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def register_plan_in_roadmap(
    plan_title: str,
    description: str,
    status: str = "PENDING",
    section: str = "pending",
    plan_file_name: str | None = None,
    plan_relative_path: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Register a plan entry in the roadmap using structured merging.

    USE WHEN: Registering a newly created plan in roadmap.md during the Plan prompt workflow.

    EXAMPLES: 'register_plan_in_roadmap(plan_title="Phase 60", description="Tool altitude audit.", section="pending")',
    'register plan in roadmap'.

    RETURNS: JSON with operation status, line inserted, section, and error if any.

    Parameters:
    - plan_title: Title of the plan (used in roadmap entry)
    - description: One-line or short description for the roadmap entry
    - status: Plan status - use 'PENDING' or 'IN PROGRESS' only (completed work belongs in activeContext.md)
    - section: Roadmap section name - one of 'blockers', 'active_work', 'future', 'pending' (default: 'pending')

    This tool handles the read-modify-write of roadmap.md, ensuring no content is lost
    and the entry is placed in the correct section.
    """
    return await _register_plan_impl(
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
    )
