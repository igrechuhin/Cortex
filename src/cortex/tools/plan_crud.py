"""
Plan CRUD: create_plan, list_plans, get_plan.

Implementation module for plan file creation, listing, and reading.
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST, MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations, safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.plan_archive import is_path_under_archive


class CreatePlanResult(BaseModel):
    """Result of creating a plan file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_path: str | None = Field(
        None, description="Absolute path to created plan file (on success)"
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class PlanEntry(BaseModel):
    """Single plan entry for list_plans response."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    slug: str = Field(description="Filename without .md (e.g. phase-60-feature)")
    title: str | None = Field(
        None, description="First # heading from plan content, if available"
    )


class ListPlansResult(BaseModel):
    """Result of listing plans."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    plans: list[PlanEntry] = Field(
        default_factory=lambda: [],
        description="List of plan entries (slug, optional title)",
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class GetPlanResult(BaseModel):
    """Result of reading a plan (content or metadata)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    slug: str | None = Field(None, description="Plan slug (filename without .md)")
    content: str | None = Field(
        None, description="Full plan content when response_format='content'"
    )
    title: str | None = Field(None, description="First # heading (metadata)")
    plan_status: str | None = Field(
        None,
        description="Value of **Status**: line (metadata); alias to avoid 'status' clash",
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


def _sanitize_plan_slug(title: str) -> str:
    """Sanitize title to create a valid filename slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _get_plan_directory(root: Path) -> Path:
    """Get the plans directory path."""
    return get_cortex_path(root, CortexResourceType.PLANS)


def _extract_first_heading(content: str) -> str | None:
    """Extract first # or ## line text (strip # and whitespace)."""
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            return re.sub(r"^#+\s*", "", s).strip() or None
    return None


def _extract_status_line(content: str) -> str | None:
    """Extract **Status**: value from plan content."""
    for line in content.split("\n"):
        s = line.strip()
        if s.lower().startswith("**status**") and ":" in s:
            return s.split(":", 1)[1].strip().strip(".").strip()
    return None


def _list_plan_files(
    root: Path, include_archive: bool
) -> tuple[list[tuple[str, Path]], str | None]:
    """List .md plan files. Returns ([(slug, path), ...], error_message)."""
    plans_dir = _get_plan_directory(root)
    if not plans_dir.exists():
        return ([], None)
    result: list[tuple[str, Path]] = []
    try:
        for path in plans_dir.rglob("*.md"):
            if not path.is_file():
                continue
            if not include_archive:
                try:
                    rel = path.relative_to(plans_dir)
                    if is_path_under_archive(rel):
                        continue
                except ValueError:
                    continue
            result.append((path.stem, path))
        result.sort(key=lambda x: (x[1].name, str(x[1])))
        return (result, None)
    except Exception as e:
        return ([], str(e))


def _get_plan_path(root: Path, slug: str) -> Path | None:
    """Resolve plan file path by slug (filename without .md). Returns None if not found."""
    plans_dir = _get_plan_directory(root)
    if not plans_dir.exists():
        return None
    candidate = plans_dir / f"{slug}.md"
    if candidate.is_file():
        return candidate
    for path in plans_dir.rglob("*.md"):
        if path.stem == slug and path.is_file():
            return path
    return None


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

    final_slug = slug if slug else _sanitize_plan_slug(title)
    if not final_slug:
        return (None, "Could not generate valid filename from title or slug")

    plan_file = plans_dir / f"{final_slug}.md"

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


def _list_plans_impl(root: Path, include_archive: bool) -> ListPlansResult:
    """List plans; optionally include archive. Returns ListPlansResult."""
    pairs, err = _list_plan_files(root, include_archive)
    if err:
        return ListPlansResult(
            status="error",
            plans=[],
            message="Failed to list plans",
            error=err,
        )
    entries: list[PlanEntry] = []
    for slug, path in pairs:
        title: str | None = None
        try:
            content = path.read_text(encoding="utf-8")
            title = _extract_first_heading(content)
        except Exception:
            pass
        entries.append(PlanEntry(slug=slug, title=title))
    return ListPlansResult(
        status="success",
        plans=entries,
        message=f"Found {len(entries)} plan(s)",
        error=None,
    )


async def _list_plans_tool_impl(include_archive: bool, ctx: MCPContext | None) -> str:
    """Implementation of list_plans tool."""
    await log_client(ctx, "info", "list_plans: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        result = _list_plans_impl(root, include_archive)
        return result.model_dump_json()
    except Exception as e:
        await log_client(ctx, "error", f"list_plans: {e}", logger_name=__name__)
        return ListPlansResult(
            status="error",
            plans=[],
            message="Unexpected error",
            error=str(e),
        ).model_dump_json()


@mcp.tool(annotations=read_only_annotations("List Plans"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_plans(
    include_archive: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """List plan files in the plans directory.

    USE WHEN: Checking for existing plans before creating a new one (e.g. create-plan
    Step 2.5) or discovering plan slugs for get_plan.

    RETURNS: JSON with status, plans (list of {slug, title}), and error if any.

    Parameters:
    - include_archive: If True, include plans under .cortex/plans/archive/ (default: False)
    """
    return await _list_plans_tool_impl(include_archive, ctx)


def _get_plan_read_content(path: Path) -> tuple[str | None, str | None]:
    """Read plan file content. Returns (content, error_message)."""
    try:
        return (path.read_text(encoding="utf-8"), None)
    except Exception as e:
        return (None, str(e))


def _get_plan_result_error(slug: str, message: str, error: str) -> GetPlanResult:
    """Build error GetPlanResult."""
    return GetPlanResult(
        status="error",
        slug=slug,
        content=None,
        title=None,
        plan_status=None,
        message=message,
        error=error,
    )


def _get_plan_result_success(
    slug: str,
    content: str | None,
    title: str | None,
    plan_status: str | None,
    message: str,
) -> GetPlanResult:
    """Build success GetPlanResult."""
    return GetPlanResult(
        status="success",
        slug=slug,
        content=content,
        title=title,
        plan_status=plan_status,
        message=message,
        error=None,
    )


def _get_plan_impl(root: Path, slug: str, response_format: str) -> GetPlanResult:
    """Read plan by slug. Returns GetPlanResult."""
    path = _get_plan_path(root, slug)
    if path is None:
        return _get_plan_result_error(
            slug, "Plan not found", f"No plan file with slug '{slug}'"
        )
    content, read_err = _get_plan_read_content(path)
    if read_err:
        return _get_plan_result_error(slug, "Failed to read plan", read_err)
    if response_format == "content":
        return _get_plan_result_success(
            slug, content, None, None, f"Plan '{slug}' read successfully"
        )
    return _get_plan_result_success(
        slug,
        None,
        _extract_first_heading(content or ""),
        _extract_status_line(content or ""),
        f"Plan '{slug}' metadata",
    )


async def _get_plan_tool_impl(
    slug: str, response_format: str, ctx: MCPContext | None
) -> str:
    """Implementation of get_plan tool."""
    await log_client(ctx, "info", "get_plan: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        result = _get_plan_impl(root, slug, response_format)
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


@mcp.tool(annotations=read_only_annotations("Get Plan"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_plan(
    slug: str,
    response_format: str = "content",
    ctx: MCPContext | None = None,
) -> str:
    """Read a plan by slug (filename without .md).

    USE WHEN: Enriching an existing plan or checking plan content without raw file reads.

    RETURNS: JSON with status, slug, and either content (full text) or title/plan_status (metadata).

    Parameters:
    - slug: Plan filename without .md (e.g. phase-60-feature or structured-planning-cortex-mcp-tools)
    - response_format: 'content' (default) for full markdown; 'metadata' for title and status only
    """
    return await _get_plan_tool_impl(slug, response_format, ctx)
