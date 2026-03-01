"""Execution logic for plan completion tool."""

from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.models import (
    AppendActiveContextEntryResult,
    AppendProgressEntryResult,
)
from cortex.tools.plans.completion_archive import archive_plan_file
from cortex.tools.plans.completion_content import (
    append_progress_entry_content,
    create_section_and_append,
    find_roadmap_bullet_line,
    has_completed_entry_for_date_and_title,
    remove_line_at,
)
from cortex.tools.plans.completion_io import (
    read_file,
    write_active_context,
    write_progress,
    write_roadmap,
)
from cortex.tools.plans.completion_models import CompletePlanResult
from cortex.tools.plans.completion_validation import (
    validate_date_str,
    validate_progress_entry_text,
)


def complete_plan_error(
    message: str,
    roadmap_line: int | None,
    active_line: int | None,
    error: str,
) -> CompletePlanResult:
    """Build error result for plan completion."""
    return CompletePlanResult(
        status=OperationStatus.ERROR,
        message=message,
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        progress_line_inserted=None,
        archive_path=None,
        error=error,
    )


def complete_plan_invalid_date_json(date_err: str) -> str:
    """Return JSON error result for invalid completion_date."""
    return CompletePlanResult(
        status=OperationStatus.ERROR,
        message="Invalid completion_date",
        roadmap_line_removed=None,
        active_context_line_inserted=None,
        progress_line_inserted=None,
        archive_path=None,
        error=date_err,
    ).model_dump_json()


def complete_plan_success(roadmap_line: int, active_line: int) -> CompletePlanResult:
    """Build success result for plan completion."""
    return CompletePlanResult(
        status=OperationStatus.SUCCESS,
        message=f"Plan moved from roadmap (line {roadmap_line}) to activeContext (line {active_line})",
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        progress_line_inserted=None,
        archive_path=None,
        error=None,
    )


def read_roadmap_and_find_line(
    roadmap_path: Path, plan_title: str
) -> tuple[str | None, int | None, CompletePlanResult | None]:
    """Read roadmap and find bullet line. Returns (content, line_num, error_result)."""
    content, read_err = read_file(roadmap_path)
    if read_err or not content:
        return (
            None,
            None,
            complete_plan_error(
                "Failed to read roadmap", None, None, read_err or "Empty roadmap"
            ),
        )
    line_num = find_roadmap_bullet_line(content, plan_title)
    if line_num is None:
        return (
            None,
            None,
            complete_plan_error(
                "Plan not found in roadmap",
                None,
                None,
                f"No roadmap bullet containing '{plan_title.strip()}'",
            ),
        )
    return (content, line_num, None)


def append_to_active_error(
    roadmap_line_num: int, message: str, error: str
) -> CompletePlanResult:
    """Build error result for append-to-active step."""
    return complete_plan_error(message, roadmap_line_num, None, error)


def read_and_validate_active(
    active_path: Path, roadmap_line_num: int
) -> tuple[str | None, CompletePlanResult | None]:
    """Read activeContext and validate. Returns (content, error_result)."""
    active_content, active_read_err = read_file(active_path)
    if active_read_err or not active_content:
        return (
            None,
            append_to_active_error(
                roadmap_line_num,
                "Removed from roadmap but failed to read activeContext",
                active_read_err or "Empty activeContext",
            ),
        )
    return (active_content, None)


async def append_to_active_and_save(
    active_path: Path,
    date_str: str,
    plan_title: str,
    summary: str,
    roadmap_line_num: int,
    project_root: Path | None = None,
) -> CompletePlanResult:
    """Read activeContext, append completed entry, write. Returns result."""
    active_content, error_result = read_and_validate_active(
        active_path, roadmap_line_num
    )
    if error_result or not active_content:
        return error_result or append_to_active_error(
            roadmap_line_num, "Empty activeContext", "Empty content"
        )
    new_active, inserted_line = create_section_and_append(
        active_content, date_str, plan_title.strip(), summary
    )
    if inserted_line is None:
        return append_to_active_error(
            roadmap_line_num,
            "Failed to append",
            "Could not find or create Completed Work section",
        )
    err = await write_active_context(active_path, new_active, project_root)
    if err:
        return append_to_active_error(
            roadmap_line_num, "Failed to write activeContext", err
        )
    return complete_plan_success(roadmap_line_num, inserted_line)


async def do_complete_plan(
    root: Path,
    plan_title: str,
    summary: str,
    date_str: str,
) -> CompletePlanResult:
    """Remove plan from roadmap and add completed entry to activeContext."""
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap_path = mem_dir / MemoryBankFile.ROADMAP
    active_path = mem_dir / MemoryBankFile.ACTIVE_CONTEXT

    roadmap_content, line_num, err = read_roadmap_and_find_line(
        roadmap_path, plan_title
    )
    if err is not None:
        return err
    assert roadmap_content is not None and line_num is not None

    new_roadmap = remove_line_at(roadmap_content, line_num)
    write_err = await write_roadmap(roadmap_path, new_roadmap, root)
    if write_err:
        return complete_plan_error("Failed to update roadmap", None, None, write_err)

    return await append_to_active_and_save(
        active_path, date_str, plan_title, summary, line_num, root
    )


def progress_error(message: str, error: str) -> AppendProgressEntryResult:
    """Build error result for progress operations."""
    return AppendProgressEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.PROGRESS,
        message=message,
        line_inserted=None,
        error=error,
    )


async def execute_append_progress(
    root: Path, date_str: str, entry_text: str
) -> AppendProgressEntryResult:
    """Append one entry to progress.md under ## date_str. Returns result."""
    date_err = validate_date_str(date_str)
    if date_err:
        return progress_error("Invalid date format", date_err)
    validation_err = validate_progress_entry_text(entry_text)
    if validation_err:
        return progress_error("Invalid progress entry format", validation_err)
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    progress_path = mem_dir / MemoryBankFile.PROGRESS
    content, read_err = read_file(progress_path)
    if read_err or not content:
        return progress_error("Failed to read progress", read_err or "Empty file")
    new_content, line_inserted = append_progress_entry_content(
        content, date_str.strip(), entry_text
    )
    if line_inserted is None:
        return progress_error(
            "Failed to append entry", "Could not find or create date section"
        )
    write_err = await write_progress(progress_path, new_content, root)
    if write_err:
        return progress_error("Failed to write progress", write_err)
    return AppendProgressEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.PROGRESS,
        message=f"Appended entry at line {line_inserted}",
        line_inserted=line_inserted,
        error=None,
    )


def active_context_error(message: str, error: str) -> AppendActiveContextEntryResult:
    """Build error result for activeContext operations."""
    return AppendActiveContextEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ACTIVE_CONTEXT,
        message=message,
        line_inserted=None,
        error=error,
    )


def append_active_context_precondition(
    content: str | None,
    read_err: str | None,
    date_str: str,
    title: str,
) -> AppendActiveContextEntryResult | None:
    """Result to return early (read error or duplicate), or None to proceed."""
    if read_err or not content:
        return active_context_error(
            "Failed to read activeContext", read_err or "Empty file"
        )
    if has_completed_entry_for_date_and_title(content, date_str, title):
        return AppendActiveContextEntryResult(
            status=OperationStatus.SUCCESS,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            message="Skipped duplicate entry (same date and title already present).",
            line_inserted=None,
            error=None,
        )
    return None


async def execute_append_active_context(
    root: Path, date_str: str, title: str, summary: str
) -> AppendActiveContextEntryResult:
    """Append one completed entry to activeContext.md. Returns result."""
    mem_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    active_path = mem_dir / MemoryBankFile.ACTIVE_CONTEXT
    content, read_err = read_file(active_path)
    early = append_active_context_precondition(
        content, read_err, date_str.strip(), title
    )
    if early is not None:
        return early
    assert content is not None
    new_content, line_inserted = create_section_and_append(
        content, date_str.strip(), title, summary
    )
    if line_inserted is None:
        return active_context_error(
            "Failed to append entry",
            "Could not find or create Completed Work section",
        )
    write_err = await write_active_context(active_path, new_content, root)
    if write_err:
        return active_context_error("Failed to write activeContext", write_err)
    return AppendActiveContextEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.ACTIVE_CONTEXT,
        message=f"Appended entry at line {line_inserted}",
        line_inserted=line_inserted,
        error=None,
    )


async def apply_progress_and_archive(
    root: Path,
    date_str: str,
    progress_entry: str | None,
    plan_file_name: str | None,
    result: CompletePlanResult,
) -> None:
    """Apply optional progress append and plan file archive; mutate result."""
    if progress_entry:
        progress_result = await execute_append_progress(root, date_str, progress_entry)
        if progress_result.status == "success" and progress_result.line_inserted:
            result.progress_line_inserted = progress_result.line_inserted
    if plan_file_name:
        archive_path, archive_err = archive_plan_file(root, plan_file_name)
        if archive_err:
            result.status = OperationStatus.ERROR
            result.error = archive_err
            result.message = (
                f"Plan moved to activeContext but archive failed: {archive_err}"
            )
        elif archive_path:
            result.archive_path = archive_path
