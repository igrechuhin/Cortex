"""
Plan Completion Tool

Moves a completed plan from roadmap.md to activeContext.md so that
roadmap stays future/upcoming only and completed work is recorded in activeContext.
When plan_file_name is provided, also moves (archives) the plan file to the
appropriate archive directory and removes any duplicate from the plans root.
"""

import re
import shutil
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.core.mcp_annotations import destructive_annotations, safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.models import (
    AppendActiveContextEntryResult,
    AppendProgressEntryResult,
)
from cortex.tools.roadmap_corruption import fix_roadmap_content_if_needed


class CompletePlanResult(BaseModel):
    """Result of completing a plan (move from roadmap to activeContext, optional progress and archive)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    message: str = Field(description="Success or error message")
    roadmap_line_removed: int | None = Field(
        None, ge=1, description="Line number removed from roadmap (on success)"
    )
    active_context_line_inserted: int | None = Field(
        None, ge=1, description="Line number inserted in activeContext (on success)"
    )
    progress_line_inserted: int | None = Field(
        None,
        ge=1,
        description="Line number inserted in progress.md (if progress_entry provided)",
    )
    archive_path: str | None = Field(
        None,
        description="Path where plan file was archived (if plan_file_name provided)",
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


def _find_progress_date_section(content: str, date_str: str) -> tuple[int, int] | None:
    """Return (start_0, end_0) 0-based line range for ## date_str in progress.md, or None."""
    lines = content.split("\n")
    target = f"## {date_str.strip()}"
    start = None
    for i, line in enumerate(lines):
        if line.strip() == target:
            start = i
            break
    if start is None:
        return None
    end = start + 1
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            end = i
            break
        end = i + 1
    return (start, end)


def _append_progress_entry_content(
    content: str, date_str: str, entry_text: str
) -> tuple[str, int | None]:
    """Append one bullet to progress.md under ## date_str. Returns (new_content, 1-based line)."""
    section = _find_progress_date_section(content, date_str)
    lines = content.split("\n")
    bullet = f"- {entry_text.strip()}"
    if section:
        start_0, end_0 = section
        last_bullet = _last_bullet_line_in_range(lines, start_0 + 1, end_0)
        insert_at = (last_bullet + 1) if last_bullet is not None else start_0 + 2
        new_lines = lines[:insert_at] + [bullet] + lines[insert_at:]
        return ("\n".join(new_lines), insert_at + 1)
    header = f"## {date_str.strip()}"
    for i, line in enumerate(lines):
        if line.strip().startswith("# ") and "Progress" in line:
            insert_at = i + 2
            new_lines = lines[:insert_at] + [header, "", bullet, ""] + lines[insert_at:]
            return ("\n".join(new_lines), insert_at + 3)
    new_lines = [header, "", bullet, ""] + lines
    return ("\n".join(new_lines), 3)


def _read_file(path: Path) -> tuple[str | None, str | None]:
    """Read file. Returns (content, error_message)."""
    if not path.exists():
        return (None, f"File not found: {path}")
    try:
        return (path.read_text(encoding="utf-8"), None)
    except Exception as e:
        return (None, str(e))


async def _write_progress(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write progress.md with lock-guarding. Returns error_message if failed."""
    # Lock-guarding: verify lock before writing
    if project_root is not None:
        from cortex.tools.file_lock_guard import verify_lock_for_file_operation

        is_allowed, lock_error = await verify_lock_for_file_operation(
            project_root=project_root,
            file_name=MemoryBankFile.PROGRESS,
            content=content,
            change_description=None,
        )
        if not is_allowed:
            assert lock_error is not None
            return f"Lock verification failed: {lock_error}"

    try:
        _ = path.write_text(content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


async def _write_roadmap(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write roadmap file with lock-guarding. Returns error_message if failed."""
    # Lock-guarding: verify lock before writing
    if project_root is not None:
        from cortex.tools.file_lock_guard import verify_lock_for_file_operation

        is_allowed, lock_error = await verify_lock_for_file_operation(
            project_root=project_root,
            file_name=MemoryBankFile.ROADMAP,
            content=content,
            change_description=None,
        )
        if not is_allowed:
            assert lock_error is not None
            return f"Lock verification failed: {lock_error}"

    try:
        fixed = fix_roadmap_content_if_needed(content)
        _ = path.write_text(fixed, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


async def _write_active_context(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write activeContext file with lock-guarding. Returns error_message if failed."""
    # Lock-guarding: verify lock before writing
    if project_root is not None:
        from cortex.tools.file_lock_guard import verify_lock_for_file_operation

        is_allowed, lock_error = await verify_lock_for_file_operation(
            project_root=project_root,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            content=content,
            change_description=None,
        )
        if not is_allowed:
            assert lock_error is not None
            return f"Lock verification failed: {lock_error}"

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
        progress_line_inserted=None,
        archive_path=None,
        error=error,
    )


def _complete_plan_success(roadmap_line: int, active_line: int) -> CompletePlanResult:
    """Build success result for plan completion."""
    return CompletePlanResult(
        status="success",
        message=f"Plan moved from roadmap (line {roadmap_line}) to activeContext (line {active_line})",
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        progress_line_inserted=None,
        archive_path=None,
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


def _read_and_validate_active(
    active_path: Path, roadmap_line_num: int
) -> tuple[str | None, CompletePlanResult | None]:
    """Read activeContext and validate. Returns (content, error_result)."""
    active_content, active_read_err = _read_file(active_path)
    if active_read_err or not active_content:
        return (
            None,
            _append_to_active_error(
                roadmap_line_num,
                "Removed from roadmap but failed to read activeContext",
                active_read_err or "Empty activeContext",
            ),
        )
    return (active_content, None)


async def _append_to_active_and_save(
    active_path: Path,
    date_str: str,
    plan_title: str,
    summary: str,
    roadmap_line_num: int,
    project_root: Path | None = None,
) -> CompletePlanResult:
    """Read activeContext, append completed entry, write. Returns result."""
    active_content, error_result = _read_and_validate_active(
        active_path, roadmap_line_num
    )
    if error_result or not active_content:
        return error_result or _append_to_active_error(
            roadmap_line_num, "Empty activeContext", "Empty content"
        )
    new_active, inserted_line = _create_section_and_append(
        active_content, date_str, plan_title.strip(), summary
    )
    if inserted_line is None:
        return _append_to_active_error(
            roadmap_line_num,
            "Failed to append",
            "Could not find or create Completed Work section",
        )
    err = await _write_active_context(active_path, new_active, project_root)
    if err:
        return _append_to_active_error(
            roadmap_line_num, "Failed to write activeContext", err
        )
    return _complete_plan_success(roadmap_line_num, inserted_line)


async def _do_complete_plan(
    root: Path,
    plan_title: str,
    summary: str,
    date_str: str,
) -> CompletePlanResult:
    """Remove plan from roadmap and add completed entry to activeContext."""
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap_path = mem_dir / MemoryBankFile.ROADMAP
    active_path = mem_dir / MemoryBankFile.ACTIVE_CONTEXT

    roadmap_content, line_num, err = _read_roadmap_and_find_line(
        roadmap_path, plan_title
    )
    if err is not None:
        return err
    assert roadmap_content is not None and line_num is not None

    new_roadmap = _remove_line_at(roadmap_content, line_num)
    write_err = await _write_roadmap(roadmap_path, new_roadmap, root)
    if write_err:
        return _complete_plan_error("Failed to update roadmap", None, None, write_err)

    return await _append_to_active_and_save(
        active_path, date_str, plan_title, summary, line_num, root
    )


def _archive_subdir_for_plan(filename: str) -> str | None:
    """Return archive subdir relative to plans/archive/ from plan filename, or None if unknown."""
    name = filename.strip()
    if not name or "/" in name or "\\" in name:
        return None
    if name.startswith("session-optimization-") and name.endswith(".md"):
        return "SessionOptimization"
    if "investigate" in name.lower() and name.endswith(".md"):
        match = re.search(r"(\d{8})", name)
        if match:
            d = match.group(1)
            return f"Investigations/{d[:4]}-{d[4:6]}-{d[6:8]}"
        return "Investigations"
    phase_match = re.match(r"phase-(\d+)-", name, re.IGNORECASE)
    if phase_match and name.endswith(".md"):
        return f"Phase{phase_match.group(1)}"
    return "Other"


def _archive_plan_file(
    root: Path, plan_file_name: str
) -> tuple[str | None, str | None]:
    """Move plan file to archive and remove duplicate from plans root. Returns (archive_path, error)."""
    if Path(plan_file_name).name != plan_file_name:
        return (None, "plan_file_name must be a single filename (no path components)")
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    source = plans_dir / plan_file_name
    if not source.exists():
        return (None, f"Plan file not found: {plan_file_name}")
    subdir = _archive_subdir_for_plan(plan_file_name)
    if subdir is None:
        return (None, f"Cannot determine archive location for: {plan_file_name}")
    plans_archive_root = get_cortex_path(root, CortexResourceType.PLANS_ARCHIVE)
    archive_dir = plans_archive_root / subdir
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / plan_file_name
    try:
        _ = shutil.move(str(source), str(dest))
    except OSError as e:
        return (None, f"Failed to move plan file: {e}")
    if source.exists():
        try:
            _ = source.unlink()
        except OSError:
            pass
    return (str(dest), None)


def _progress_error(message: str, error: str) -> AppendProgressEntryResult:
    """Build error result for progress operations."""
    return AppendProgressEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.PROGRESS,
        message=message,
        line_inserted=None,
        error=error,
    )


def _validate_progress_entry_text(entry_text: str) -> str | None:
    """Reject progress entry text that matches common corruption patterns.

    Ensures COMPLETE is preceded by the proper delimiter (e.g. " - COMPLETE"
    or ")** - COMPLETE") to avoid malformed bullets like "20260209COMPLETE".
    Returns an error message if invalid, None if valid.
    """
    t = (entry_text or "").strip()
    if "COMPLETE" in t and " - COMPLETE" not in t:
        return (
            "Progress entry contains 'COMPLETE' but is missing ' - COMPLETE' "
            "(e.g. use '**Title** - COMPLETE. Summary...', not '...COMPLETE' alone)"
        )
    return None


async def _execute_append_progress(
    root: Path, date_str: str, entry_text: str
) -> AppendProgressEntryResult:
    """Append one entry to progress.md under ## date_str. Returns result."""
    validation_err = _validate_progress_entry_text(entry_text)
    if validation_err:
        return _progress_error("Invalid progress entry format", validation_err)
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    progress_path = mem_dir / MemoryBankFile.PROGRESS
    content, read_err = _read_file(progress_path)
    if read_err or not content:
        return _progress_error("Failed to read progress", read_err or "Empty file")
    new_content, line_inserted = _append_progress_entry_content(
        content, date_str.strip(), entry_text
    )
    if line_inserted is None:
        return _progress_error(
            "Failed to append entry", "Could not find or create date section"
        )
    write_err = await _write_progress(progress_path, new_content, root)
    if write_err:
        return _progress_error("Failed to write progress", write_err)
    return AppendProgressEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.PROGRESS,
        message=f"Appended entry at line {line_inserted}",
        line_inserted=line_inserted,
        error=None,
    )


def _active_context_error(message: str, error: str) -> AppendActiveContextEntryResult:
    """Build error result for activeContext operations."""
    return AppendActiveContextEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ACTIVE_CONTEXT,
        message=message,
        line_inserted=None,
        error=error,
    )


async def _execute_append_active_context(
    root: Path, date_str: str, title: str, summary: str
) -> AppendActiveContextEntryResult:
    """Append one completed entry to activeContext.md. Returns result."""
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    active_path = mem_dir / MemoryBankFile.ACTIVE_CONTEXT
    content, read_err = _read_file(active_path)
    if read_err or not content:
        return _active_context_error(
            "Failed to read activeContext", read_err or "Empty file"
        )
    new_content, line_inserted = _create_section_and_append(
        content, date_str.strip(), title, summary
    )
    if line_inserted is None:
        return _active_context_error(
            "Failed to append entry",
            "Could not find or create Completed Work section",
        )
    write_err = await _write_active_context(active_path, new_content, root)
    if write_err:
        return _active_context_error("Failed to write activeContext", write_err)
    return AppendActiveContextEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.ACTIVE_CONTEXT,
        message=f"Appended entry at line {line_inserted}",
        line_inserted=line_inserted,
        error=None,
    )


async def _apply_progress_and_archive(
    root: Path,
    date_str: str,
    progress_entry: str | None,
    plan_file_name: str | None,
    result: CompletePlanResult,
) -> None:
    """Apply optional progress append and plan file archive; mutate result."""
    if progress_entry:
        progress_result = await _execute_append_progress(root, date_str, progress_entry)
        if progress_result.status == "success" and progress_result.line_inserted:
            result.progress_line_inserted = progress_result.line_inserted
    if plan_file_name:
        archive_path, archive_err = _archive_plan_file(root, plan_file_name)
        if archive_err:
            result.status = "error"
            result.error = archive_err
            result.message = (
                f"Plan moved to activeContext but archive failed: {archive_err}"
            )
        elif archive_path:
            result.archive_path = archive_path


async def _complete_plan_impl(
    plan_title: str,
    summary: str,
    completion_date: str | None,
    progress_entry: str | None,
    plan_file_name: str | None,
    ctx: MCPContext | None,
) -> str:
    """Implementation of complete_plan: roadmap + activeContext, optional progress, optional archive."""
    await log_client(ctx, "info", "complete_plan: starting", logger_name=__name__)
    date_str = (completion_date or _today_iso()).strip()
    root = await resolve_project_root_async(None, ctx)
    result = await _do_complete_plan(root, plan_title, summary, date_str)
    if result.status != "success":
        await log_client(
            ctx, "warning", f"complete_plan: {result.status}", logger_name=__name__
        )
        return result.model_dump_json()
    await _apply_progress_and_archive(
        root, date_str, progress_entry, plan_file_name, result
    )
    await log_client(
        ctx, "info", f"complete_plan: {result.status}", logger_name=__name__
    )
    return result.model_dump_json()


@mcp.tool(annotations=destructive_annotations("Complete Plan"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def complete_plan(
    plan_title: str,
    summary: str,
    completion_date: str | None = None,
    progress_entry: str | None = None,
    plan_file_name: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Move a completed plan from roadmap to activeContext; optionally append progress and archive plan file.

    USE WHEN: A plan has been finished and should be recorded as completed
    in activeContext.md and removed from roadmap.md (roadmap = future only).
    When the step references a plan file, pass plan_file_name so the tool
    also moves (archives) the plan file to the correct archive directory.

    RETURNS: JSON with status, roadmap_line_removed, active_context_line_inserted,
    optional progress_line_inserted, optional archive_path.

    - Removes the first roadmap bullet that contains plan_title.
    - Appends a completed entry to activeContext under ## Completed Work (date).
    - If progress_entry is provided, appends that line to progress.md under the date.
    - If plan_file_name is provided, moves the plan file to archive (SessionOptimization/,
      PhaseN/, Investigations/YYYY-MM-DD/, or Other/) and removes any duplicate from plans root.
    - completion_date: YYYY-MM-DD (default: today UTC).
    """
    try:
        return await _complete_plan_impl(
            plan_title,
            summary,
            completion_date,
            progress_entry,
            plan_file_name,
            ctx,
        )
    except Exception as e:
        await log_client(ctx, "error", f"complete_plan: {e}", logger_name=__name__)
        return CompletePlanResult(
            status="error",
            message="Unexpected error",
            roadmap_line_removed=None,
            active_context_line_inserted=None,
            progress_line_inserted=None,
            archive_path=None,
            error=str(e),
        ).model_dump_json()


async def _append_progress_entry_impl(
    date_str: str,
    entry_text: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of append_progress_entry."""
    await log_client(
        ctx, "info", "append_progress_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = await _execute_append_progress(root, date_str, entry_text)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"append_progress_entry: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Append Progress Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def append_progress_entry(
    date_str: str,
    entry_text: str,
    ctx: MCPContext | None = None,
) -> str:
    """Append a single entry to progress.md under the given date section.

    USE WHEN: Implement Step 5 needs to add one progress entry without
    building or writing full progress content (safe update).

    date_str: YYYY-MM-DD. entry_text: one bullet line (e.g. "**Title** - COMPLETE. ...").
    RETURNS: JSON with status, line_inserted, or error.
    """
    try:
        return await _append_progress_entry_impl(date_str, entry_text, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"append_progress_entry: {e}", logger_name=__name__
        )
        return AppendProgressEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.PROGRESS,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()


async def _append_active_context_entry_impl(
    date_str: str,
    title: str,
    summary: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of append_active_context_entry."""
    await log_client(
        ctx, "info", "append_active_context_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = await _execute_append_active_context(root, date_str, title, summary)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"append_active_context_entry: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Append Active Context Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def append_active_context_entry(
    date_str: str,
    title: str,
    summary: str,
    ctx: MCPContext | None = None,
) -> str:
    """Append a single completed entry to activeContext.md.

    USE WHEN: Implement Step 5 needs to add completed work without
    building or writing full activeContext content (safe update).

    date_str: YYYY-MM-DD. title/summary: entry content.
    RETURNS: JSON with status, line_inserted, or error.
    """
    try:
        return await _append_active_context_entry_impl(date_str, title, summary, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"append_active_context_entry: {e}",
            logger_name=__name__,
        )
        return AppendActiveContextEntryResult(
            status=OperationStatus.ERROR,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            message="Unexpected error",
            line_inserted=None,
            error=str(e),
        ).model_dump_json()
