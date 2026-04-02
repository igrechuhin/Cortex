"""
Plan roadmap: register_plan_in_roadmap.

Implementation module for registering plan entries in roadmap.md.
"""

from pathlib import Path

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_MEDIUM,
    MemoryBankFile,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.register_helpers import (
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
) -> tuple[str, int | None]:
    """Register plan entry and return (content, line_inserted)."""
    return register_plan_entry(
        current_content,
        plan_title,
        description,
        status,
        section_id,
        "last",
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
) -> str:
    """Handle successful plan registration."""
    await log_client(
        ctx,
        "info",
        f"register_plan_in_roadmap: success - line {line_inserted}",
        logger_name=__name__,
    )
    return create_register_success_result(section_id, line_inserted).model_dump_json()


async def _execute_register_plan(
    root: Path,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    ctx: MCPContext | None,
) -> str:
    """Execute plan registration. Returns JSON result."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap_path = memory_bank_dir / MemoryBankFile.ROADMAP

    read_result = await _handle_roadmap_read(roadmap_path, ctx)
    if read_result:
        return read_result

    current_content, _ = read_roadmap_file(roadmap_path)
    assert current_content is not None
    updated_content, line_inserted = _do_register_plan_entry(
        current_content, plan_title, description, status, section_id
    )

    if line_inserted is None:
        return await _handle_entry_not_found(ctx, section_id)

    write_result = await _handle_roadmap_write(
        roadmap_path, updated_content, section_id, ctx, root
    )
    return write_result or await _handle_entry_success(ctx, section_id, line_inserted)


async def _validate_and_execute_register(
    section: str,
    root: Path,
    plan_title: str,
    description: str,
    status: str,
    ctx: MCPContext | None,
) -> str:
    """Validate section and execute registration."""
    if is_completed_status(status):
        await log_client(
            ctx,
            "warning",
            "register_plan_in_roadmap: rejected COMPLETED status",
            logger_name=__name__,
        )
        return create_register_error_result(
            _ROADMAP_COMPLETED_STATUS_MESSAGE
        ).model_dump_json()

    section_id, section_error = validate_registration_section(section)
    if section_error:
        await log_client(
            ctx,
            "warning",
            f"register_plan_in_roadmap: {section_error}",
            logger_name=__name__,
        )
        return create_register_error_result(section_error).model_dump_json()

    assert section_id is not None
    return await _execute_register_plan(
        root, plan_title, description, status, section_id, ctx
    )


async def _register_plan_impl(
    plan_title: str,
    description: str,
    status: str,
    section: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of register_plan_in_roadmap logic."""
    await log_client(
        ctx, "info", "register_plan_in_roadmap: starting", logger_name=__name__
    )

    try:
        root = await resolve_project_root_async(None, ctx)
        return await _validate_and_execute_register(
            section, root, plan_title, description, status, ctx
        )
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"register_plan_in_roadmap: {e}",
            logger_name=__name__,
        )
        return RegisterPlanResult(
            status="error",
            file_name=MemoryBankFile.ROADMAP,
            message="Unexpected error",
            line_inserted=None,
            section=None,
            error=str(e),
        ).model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def register_plan_in_roadmap(
    plan_title: str,
    description: str,
    status: str = "PENDING",
    section: str = "pending",
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
    return await _register_plan_impl(plan_title, description, status, section, ctx)
