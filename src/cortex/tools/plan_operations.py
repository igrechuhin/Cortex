"""
Plan Operations Tools

This module contains MCP tools for structured plan creation and roadmap registration,
providing a cleaner API than manual file writes and full roadmap content handling.

Tools:
- create_plan: Create a new plan file in the plans directory
- register_plan_in_roadmap: Register a plan in roadmap.md with structured merging
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.roadmap_corruption import fix_roadmap_content_if_needed


class CreatePlanResult(BaseModel):
    """Result of creating a plan file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_path: str | None = Field(
        None, description="Absolute path to created plan file (on success)"
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class RegisterPlanResult(BaseModel):
    """Result of registering a plan in roadmap."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_name: str = Field(description="File that was modified (roadmap.md)")
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="Line number where entry was inserted"
    )
    section: str | None = Field(None, description="Section where entry was added")
    error: str | None = Field(None, description="Error message if status is error")


def _sanitize_plan_slug(title: str) -> str:
    """Sanitize title to create a valid filename slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _get_plan_directory(root: Path) -> Path:
    """Get the plans directory path."""
    return root / ".cortex" / "plans"


def _create_plan_file(
    root: Path,
    title: str,
    slug: str | None,
    content: str,
) -> tuple[Path | None, str | None]:
    """Create a plan file. Returns (path, error_message)."""
    plans_dir = _get_plan_directory(root)

    if not plans_dir.exists():
        try:
            plans_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return (None, f"Failed to create plans directory: {str(e)}")

    # Determine filename
    final_slug = slug if slug else _sanitize_plan_slug(title)
    if not final_slug:
        return (None, "Could not generate valid filename from title or slug")

    plan_file = plans_dir / f"{final_slug}.md"

    # Write file
    try:
        _ = plan_file.write_text(content, encoding="utf-8")
        return (plan_file, None)
    except Exception as e:
        return (None, f"Failed to write plan file: {str(e)}")


def _create_success_result(plan_path: Path | None) -> CreatePlanResult:
    """Create a success result for plan creation."""
    if plan_path is None:
        return CreatePlanResult(
            status="error",
            file_path=None,
            message="Plan path is None",
            error="Unexpected: no path returned",
        )
    return CreatePlanResult(
        status="success",
        file_path=str(plan_path),
        message=f"Plan created at {plan_path}",
        error=None,
    )


def _create_error_result(error: str) -> CreatePlanResult:
    """Create an error result for plan creation."""
    return CreatePlanResult(
        status="error",
        file_path=None,
        message="Failed to create plan file",
        error=error,
    )


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
        return _create_error_result(error).model_dump_json()

    await log_client(
        ctx,
        "info",
        f"create_plan: success - {plan_path}",
        logger_name=__name__,
    )
    return _create_success_result(plan_path).model_dump_json()


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
        plan_path, error = _create_plan_file(root, title, slug, content)
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


@mcp.tool(annotations=safe_write_annotations("Create Plan"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def create_plan(
    title: str,
    content: str,
    slug: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Create a structured plan file in the plans directory.

    USE WHEN: Creating a new plan during the create-plan workflow.

    RETURNS: JSON with operation status, file path (on success), and error if any.

    Parameters:
    - title: Plan title (used to generate slug if not provided)
    - content: Full markdown content for the plan file
    - slug: Optional filename slug (e.g., 'phase-x-feature-name'). If not provided,
            generated from title by converting to lowercase and replacing spaces with hyphens.
    """
    return await _create_plan_impl(title, content, slug, ctx)


def _parse_roadmap_sections(content: str) -> dict[str, tuple[int, int]]:
    """Parse roadmap to get section boundaries.

    Returns: {section_id: (start_line, end_line)}
    """
    sections: dict[str, tuple[int, int]] = {}
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$")
    header_to_section = {
        "Blockers (ASAP Priority)": "blockers",
        "Active Work (in progress)": "active_work",
        "Future Enhancements": "future",
        "Pending plans (from .cortex/plans)": "pending",
    }

    current_section_name: str | None = None
    current_section_start = 0

    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if not match:
            continue
        header_text = match.group(2)
        section_id = header_to_section.get(header_text)

        if current_section_name is not None:
            sections[current_section_name] = (current_section_start, i - 1)

        if section_id:
            current_section_name = section_id
            current_section_start = i

    if current_section_name is not None:
        sections[current_section_name] = (current_section_start, len(lines) - 1)

    return sections


def _find_insertion_line_for_section(
    lines: list[str],
    section_start: int,
    section_end: int,
    position: str = "last",
) -> int:
    """Find the line number where a new entry should be inserted."""
    # Find first and last bullet lines in this section
    first_bullet = -1
    last_bullet = -1

    for i in range(section_start + 1, section_end + 1):
        if lines[i].startswith("- "):
            if first_bullet == -1:
                first_bullet = i
            last_bullet = i

    if position == "first":
        if first_bullet != -1:
            return first_bullet
        return section_start + 1

    if last_bullet != -1:
        return last_bullet + 1
    return section_start + 1


def _register_plan_entry(
    content: str,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    position: str = "last",
) -> tuple[str, int | None]:
    """Register a plan entry in the roadmap.

    Returns: (updated_content, inserted_line_number)
    """
    sections = _parse_roadmap_sections(content)

    if section_id not in sections:
        return (content, None)

    section_start, section_end = sections[section_id]
    lines = content.split("\n")

    # Format entry: "- **Plan Title** - STATUS - Description"
    entry_text = f"- **{plan_title}** - {status} - {description}"

    insert_line = _find_insertion_line_for_section(
        lines, section_start, section_end, position
    )
    lines.insert(insert_line, entry_text)
    updated_content = "\n".join(lines)

    return (updated_content, insert_line + 1)


_ROADMAP_COMPLETED_STATUS_MESSAGE = (
    "Roadmap records future/upcoming work only. "
    "Completed work belongs in activeContext.md. Use status 'PENDING' or 'IN PROGRESS'."
)


def _is_completed_status(status: str) -> bool:
    """Return True if status indicates completed work (not allowed in roadmap)."""
    normalized = status.strip().upper()
    return normalized in ("COMPLETED", "COMPLETE", "DONE")


def _validate_registration_section(section: str) -> tuple[str | None, str | None]:
    """Validate section identifier. Returns (section_id, error_message)."""
    section_map = {
        "blockers": "blockers",
        "active_work": "active_work",
        "future": "future",
        "pending": "pending",
    }

    section_id = section_map.get(section.lower())
    if not section_id:
        error_msg = f"Section must be one of: {', '.join(section_map.keys())}"
        return (None, error_msg)

    return (section_id, None)


def _read_roadmap_file(roadmap_path: Path) -> tuple[str | None, str | None]:
    """Read roadmap file. Returns (content, error_message)."""
    if not roadmap_path.exists():
        return (None, f"roadmap.md not found at {roadmap_path}")

    try:
        content = roadmap_path.read_text(encoding="utf-8")
        return (content, None)
    except Exception as e:
        return (None, str(e))


def _write_roadmap_file(roadmap_path: Path, content: str) -> str | None:
    """Write updated roadmap. Returns error_message if failed."""
    try:
        fixed_content = fix_roadmap_content_if_needed(content)
        _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


def _create_register_error_result(error: str) -> RegisterPlanResult:
    """Create an error result for plan registration."""
    return RegisterPlanResult(
        status="error",
        file_name="roadmap.md",
        message="Failed to register plan",
        line_inserted=None,
        section=None,
        error=error,
    )


def _create_register_success_result(
    section_id: str,
    line_inserted: int,
) -> RegisterPlanResult:
    """Create a success result for plan registration."""
    return RegisterPlanResult(
        status="success",
        file_name="roadmap.md",
        message=f"Plan registered in '{section_id}' section at line {line_inserted}",
        line_inserted=line_inserted,
        section=section_id,
        error=None,
    )


async def _handle_roadmap_read(
    roadmap_path: Path,
    ctx: MCPContext | None,
) -> str | None:
    """Read roadmap or return error JSON. Returns error JSON or None."""
    _, read_error = _read_roadmap_file(roadmap_path)
    if read_error:
        await log_client(
            ctx,
            "warning",
            f"register_plan_in_roadmap: {read_error}",
            logger_name=__name__,
        )
        return _create_register_error_result(read_error).model_dump_json()
    return None


async def _handle_roadmap_write(
    roadmap_path: Path,
    updated_content: str,
    section_id: str,
    ctx: MCPContext | None,
) -> str | None:
    """Write roadmap or return error JSON. Returns error JSON or None."""
    write_error = _write_roadmap_file(roadmap_path, updated_content)
    if write_error:
        await log_client(
            ctx,
            "error",
            f"register_plan_in_roadmap: {write_error}",
            logger_name=__name__,
        )
        return _create_register_error_result(write_error).model_dump_json()
    return None


def _do_register_plan_entry(
    current_content: str,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
) -> tuple[str, int | None]:
    """Register plan entry and return (content, line_inserted)."""
    return _register_plan_entry(
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
    return _create_register_error_result(error_msg).model_dump_json()


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
    return _create_register_success_result(section_id, line_inserted).model_dump_json()


async def _execute_register_plan(
    root: Path,
    plan_title: str,
    description: str,
    status: str,
    section_id: str,
    ctx: MCPContext | None,
) -> str:
    """Execute plan registration. Returns JSON result."""
    roadmap_path = root / ".cortex" / "memory-bank" / "roadmap.md"

    # Read roadmap
    read_result = await _handle_roadmap_read(roadmap_path, ctx)
    if read_result:
        return read_result

    # Get content and register entry
    current_content, _ = _read_roadmap_file(roadmap_path)
    assert current_content is not None
    updated_content, line_inserted = _do_register_plan_entry(
        current_content, plan_title, description, status, section_id
    )

    if line_inserted is None:
        return await _handle_entry_not_found(ctx, section_id)

    # Write roadmap
    write_result = await _handle_roadmap_write(
        roadmap_path, updated_content, section_id, ctx
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
    if _is_completed_status(status):
        await log_client(
            ctx,
            "warning",
            "register_plan_in_roadmap: rejected COMPLETED status",
            logger_name=__name__,
        )
        return _create_register_error_result(
            _ROADMAP_COMPLETED_STATUS_MESSAGE
        ).model_dump_json()

    section_id, section_error = _validate_registration_section(section)
    if section_error:
        await log_client(
            ctx,
            "warning",
            f"register_plan_in_roadmap: {section_error}",
            logger_name=__name__,
        )
        return _create_register_error_result(section_error).model_dump_json()

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
            file_name="roadmap.md",
            message="Unexpected error",
            line_inserted=None,
            section=None,
            error=str(e),
        ).model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Register Plan in Roadmap"))
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

    USE WHEN: Registering a newly created plan in roadmap.md during the create-plan workflow.

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
