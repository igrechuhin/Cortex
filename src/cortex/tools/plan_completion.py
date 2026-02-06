"""
Plan Completion Tool

Moves a completed plan from roadmap.md to activeContext.md so that
roadmap stays future/upcoming only and completed work is recorded in activeContext.
"""

import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.roadmap_corruption import fix_roadmap_content_if_needed


class CompletePlanResult(BaseModel):
    """Result of completing a plan (move from roadmap to activeContext)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    message: str = Field(description="Success or error message")
    roadmap_line_removed: int | None = Field(
        None, ge=1, description="Line number removed from roadmap (on success)"
    )
    active_context_line_inserted: int | None = Field(
        None, ge=1, description="Line number inserted in activeContext (on success)"
    )
    error: str | None = Field(None, description="Error message if status is error")


def _today_iso() -> str:
    """Return today's date in YYYY-MM-DD."""
    return date.today().strftime("%Y-%m-%d")


def _find_roadmap_bullet_line(content: str, plan_title: str) -> int | None:
    """Return 1-based line number of first bullet line containing plan_title, or None."""
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("- ") and plan_title.strip() in line:
            return i
    return None


def _remove_line_at(content: str, one_based_line: int) -> str:
    """Remove the line at the given 1-based index; return new content."""
    lines = content.split("\n")
    idx = one_based_line - 1
    if idx < 0 or idx >= len(lines):
        return content
    new_lines = lines[:idx] + lines[idx + 1 :]
    return "\n".join(new_lines)


def _find_completed_work_section(content: str, date_str: str) -> tuple[int, int] | None:
    """Return (start_line_1based, end_line_1based) of '## Completed Work (date_str)' or None."""
    lines = content.split("\n")
    pattern = re.compile(
        r"^##\s+Completed Work\s+\(\s*" + re.escape(date_str) + r"\s*\)"
    )
    start = None
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return None
    end = start
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("## ") and i + 1 != start:
            end = i
            break
        end = i + 1
    return (start, end)


def _last_bullet_line_in_range(
    lines: list[str], start_0: int, end_0: int
) -> int | None:
    """Return 0-based index of last line in [start_0, end_0) that starts with '- ', or None."""
    last = None
    for i in range(start_0, min(end_0, len(lines))):
        if lines[i].strip().startswith("- "):
            last = i
    return last


def _append_completed_entry(
    content: str, date_str: str, title: str, summary: str
) -> tuple[str, int | None]:
    """Append completed entry to activeContext. Returns (new_content, 1-based line inserted)."""
    lines = content.split("\n")
    section = _find_completed_work_section(content, date_str)
    if not section:
        return (content, None)
    start_1, end_1 = section
    start_0, end_0 = start_1 - 1, end_1
    last_bullet = _last_bullet_line_in_range(lines, start_0, end_0)
    insert_at = (last_bullet + 1) if last_bullet is not None else start_0 + 1
    entry = f"- ✅ **{title}** - COMPLETE ({date_str}) - {summary}"
    new_lines = lines[:insert_at] + [""] + [entry] + lines[insert_at:]
    new_content = "\n".join(new_lines)
    line_inserted = insert_at + 2
    return (new_content, line_inserted)


def _create_section_and_append(
    content: str, date_str: str, title: str, summary: str
) -> tuple[str, int | None]:
    """If no section for date exists, add it after first '## Completed Work'; then append entry."""
    section = _find_completed_work_section(content, date_str)
    if section:
        return _append_completed_entry(content, date_str, title, summary)
    lines = content.split("\n")
    new_section_header = f"## Completed Work ({date_str})"
    entry = f"- ✅ **{title}** - COMPLETE ({date_str}) - {summary}"
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Completed Work\s+\(", line.strip()):
            insert_at = i
            new_lines = (
                lines[:insert_at]
                + [new_section_header]
                + [""]
                + [entry]
                + [""]
                + lines[insert_at:]
            )
            new_content = "\n".join(new_lines)
            return (new_content, insert_at + 3)
    return (content, None)


def _read_file(path: Path) -> tuple[str | None, str | None]:
    """Read file. Returns (content, error_message)."""
    if not path.exists():
        return (None, f"File not found: {path}")
    try:
        return (path.read_text(encoding="utf-8"), None)
    except Exception as e:
        return (None, str(e))


def _write_roadmap(path: Path, content: str) -> str | None:
    """Write roadmap file. Returns error_message if failed."""
    try:
        fixed = fix_roadmap_content_if_needed(content)
        _ = path.write_text(fixed, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


def _write_active_context(path: Path, content: str) -> str | None:
    """Write activeContext file. Returns error_message if failed."""
    try:
        _ = path.write_text(content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


def _complete_plan_error(
    message: str,
    roadmap_line: int | None,
    active_line: int | None,
    error: str,
) -> CompletePlanResult:
    """Build error result for plan completion."""
    return CompletePlanResult(
        status="error",
        message=message,
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        error=error,
    )


def _complete_plan_success(roadmap_line: int, active_line: int) -> CompletePlanResult:
    """Build success result for plan completion."""
    return CompletePlanResult(
        status="success",
        message=f"Plan moved from roadmap (line {roadmap_line}) to activeContext (line {active_line})",
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        error=None,
    )


def _read_roadmap_and_find_line(
    roadmap_path: Path, plan_title: str
) -> tuple[str | None, int | None, CompletePlanResult | None]:
    """Read roadmap and find bullet line. Returns (content, line_num, error_result)."""
    content, read_err = _read_file(roadmap_path)
    if read_err or not content:
        return (
            None,
            None,
            _complete_plan_error(
                "Failed to read roadmap", None, None, read_err or "Empty roadmap"
            ),
        )
    line_num = _find_roadmap_bullet_line(content, plan_title)
    if line_num is None:
        return (
            None,
            None,
            _complete_plan_error(
                "Plan not found in roadmap",
                None,
                None,
                f"No roadmap bullet containing '{plan_title.strip()}'",
            ),
        )
    return (content, line_num, None)


def _append_to_active_error(
    roadmap_line_num: int, message: str, error: str
) -> CompletePlanResult:
    """Build error result for append-to-active step."""
    return _complete_plan_error(message, roadmap_line_num, None, error)


def _append_to_active_and_save(
    active_path: Path,
    date_str: str,
    plan_title: str,
    summary: str,
    roadmap_line_num: int,
) -> CompletePlanResult:
    """Read activeContext, append completed entry, write. Returns result."""
    active_content, active_read_err = _read_file(active_path)
    if active_read_err or not active_content:
        return _append_to_active_error(
            roadmap_line_num,
            "Removed from roadmap but failed to read activeContext",
            active_read_err or "Empty activeContext",
        )

    new_active, inserted_line = _create_section_and_append(
        active_content, date_str, plan_title.strip(), summary
    )
    if inserted_line is None:
        return _append_to_active_error(
            roadmap_line_num,
            "Removed from roadmap but failed to append to activeContext",
            "Could not find or create Completed Work section",
        )

    active_write_err = _write_active_context(active_path, new_active)
    if active_write_err:
        return _append_to_active_error(
            roadmap_line_num,
            "Removed from roadmap but failed to write activeContext",
            active_write_err,
        )

    return _complete_plan_success(roadmap_line_num, inserted_line)


def _do_complete_plan(
    root: Path,
    plan_title: str,
    summary: str,
    date_str: str,
) -> CompletePlanResult:
    """Remove plan from roadmap and add completed entry to activeContext."""
    mem_dir = root / ".cortex" / "memory-bank"
    roadmap_path = mem_dir / "roadmap.md"
    active_path = mem_dir / "activeContext.md"

    roadmap_content, line_num, err = _read_roadmap_and_find_line(
        roadmap_path, plan_title
    )
    if err is not None:
        return err
    assert roadmap_content is not None and line_num is not None

    new_roadmap = _remove_line_at(roadmap_content, line_num)
    write_err = _write_roadmap(roadmap_path, new_roadmap)
    if write_err:
        return _complete_plan_error("Failed to update roadmap", None, None, write_err)

    return _append_to_active_and_save(
        active_path, date_str, plan_title, summary, line_num
    )


async def _complete_plan_impl(
    plan_title: str,
    summary: str,
    completion_date: str | None,
    ctx: MCPContext | None,
) -> str:
    """Implementation of complete_plan."""
    await log_client(ctx, "info", "complete_plan: starting", logger_name=__name__)
    date_str = (completion_date or _today_iso()).strip()
    root = await resolve_project_root_async(None, ctx)
    result = _do_complete_plan(root, plan_title, summary, date_str)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"complete_plan: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=destructive_annotations("Complete Plan"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def complete_plan(
    plan_title: str,
    summary: str,
    completion_date: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Move a completed plan from roadmap to activeContext.

    USE WHEN: A plan has been finished and should be recorded as completed
    in activeContext.md and removed from roadmap.md (roadmap = future only).

    RETURNS: JSON with status, roadmap_line_removed, active_context_line_inserted.

    - Removes the first roadmap bullet that contains plan_title.
    - Appends a completed entry to activeContext under ## Completed Work (date).
    - completion_date: YYYY-MM-DD (default: today UTC).
    """
    try:
        return await _complete_plan_impl(plan_title, summary, completion_date, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"complete_plan: {e}", logger_name=__name__)
        return CompletePlanResult(
            status="error",
            message="Unexpected error",
            roadmap_line_removed=None,
            active_context_line_inserted=None,
            error=str(e),
        ).model_dump_json()
