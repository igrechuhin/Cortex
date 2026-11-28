"""Prevalidation and immutable target preparation for plan completion."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.artifact_graph import read_plan_status_from_content
from cortex.core.constants import MemoryBankFile
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_metadata import has_cancelled_plan_status
from cortex.core.security import InputValidator
from cortex.tools.plans.completion_content import (
    append_progress_entry_content,
    create_section_and_append,
    has_completed_entry_for_date_and_title,
    remove_line_at,
)
from cortex.tools.plans.completion_transaction_io import (
    hash_text,
    operation_id,
    persist_payload,
    read_payload,
    read_required_text,
    request_fingerprint,
    transaction_archive_subdir,
    utc_now_iso,
    validate_contained_path,
)
from cortex.tools.plans.completion_transaction_models import (
    CancellationRequest,
    CompletionFileKey,
    CompletionFileRecord,
    CompletionOperationRecord,
    CompletionPhase,
    CompletionRequest,
    PlanArchiveRequest,
    PreparedCompletionFile,
)
from cortex.tools.plans.entries_content import extract_plan_path_from_bullet
from cortex.tools.plans.register_artifact_graph import replace_plan_frontmatter_status


def validate_plan_file_name(plan_file_name: str | None) -> str | None:
    """Validate an optional plan filename without mutating the filesystem."""
    if plan_file_name is None:
        return None
    if Path(plan_file_name).name != plan_file_name or "/" in plan_file_name:
        raise ValueError(
            "plan_file_name must be a single filename (no path components)"
        )
    validated = InputValidator.validate_file_name(plan_file_name)
    if validated != plan_file_name or not validated.lower().endswith(".md"):
        raise ValueError("plan_file_name must be an exact Markdown filename")
    return validated


def normalized_request(
    plan_title: str,
    summary: str,
    completion_date: str,
    progress_entry: str | None,
    plan_file_name: str | None,
) -> CompletionRequest:
    """Build normalized request after pure validation."""
    title = plan_title.strip()
    if not title:
        raise ValueError("plan_title is required")
    if not summary.strip():
        raise ValueError("summary is required")
    return CompletionRequest(
        plan_title=title,
        summary=summary.strip(),
        completion_date=completion_date.strip(),
        progress_entry=progress_entry.strip() if progress_entry else None,
        plan_file_name=validate_plan_file_name(plan_file_name),
    )


def _roadmap_line(content: str, request: CompletionRequest) -> int:
    candidates = [
        (index, line)
        for index, line in enumerate(content.splitlines(), start=1)
        if re.match(r"^[\-–—]\s", line.strip()) and request.plan_title in line
    ]
    if not candidates:
        raise ValueError(f"No roadmap bullet containing '{request.plan_title}'")
    if len(candidates) > 1:
        raise ValueError(
            f"Ambiguous roadmap identity: multiple bullets contain '{request.plan_title}'"
        )
    line_number, line = candidates[0]
    refs = re.findall(r"(?:\.cortex/)?plans/([^`\s|]+\.md)", line)
    if request.plan_file_name and refs and request.plan_file_name not in refs:
        raise ValueError("Roadmap plan reference does not match plan_file_name")
    return line_number


def _validate_plan_identity(content: str, request: CompletionRequest) -> None:
    match = re.search(r"^title\s*:\s*[\"']?(.+?)[\"']?\s*$", content, re.MULTILINE)
    if match and match.group(1).strip().casefold() != request.plan_title.casefold():
        raise ValueError("Plan frontmatter title does not match plan_title")


def _active_after(content: str, request: CompletionRequest) -> tuple[str, int | None]:
    expected = (
        f"- ✅ **{request.plan_title}** - COMPLETE "
        f"({request.completion_date}) - {request.summary}"
    )
    if expected in content.splitlines():
        return content, None
    if has_completed_entry_for_date_and_title(
        content, request.completion_date, request.plan_title
    ):
        raise ValueError("Conflicting activeContext completion entry already exists")
    return create_section_and_append(
        content, request.completion_date, request.plan_title, request.summary
    )


def _progress_after(content: str, request: CompletionRequest) -> tuple[str, int | None]:
    assert request.progress_entry is not None
    expected = f"- {request.progress_entry}"
    if expected in content.splitlines():
        return content, None
    return append_progress_entry_content(
        content, request.completion_date, request.progress_entry
    )


def _prepared_file(
    key: CompletionFileKey,
    path: Path,
    before: str,
    after: str,
) -> PreparedCompletionFile:
    return PreparedCompletionFile(key=key, path=path, before=before, after=after)


def _persist_file_record(
    project_root: Path,
    operations_root: Path,
    op_id: str,
    prepared: PreparedCompletionFile,
) -> CompletionFileRecord:
    before_name = f"{op_id}.{prepared.key.value}.before.txt"
    after_name = f"{op_id}.{prepared.key.value}.after.txt"
    persist_payload(operations_root / before_name, prepared.before)
    persist_payload(operations_root / after_name, prepared.after)
    return CompletionFileRecord(
        key=prepared.key,
        relative_path=prepared.path.relative_to(project_root).as_posix(),
        before_exists=True,
        before_hash=hash_text(prepared.before),
        after_hash=hash_text(prepared.after),
        before_payload=before_name,
        after_payload=after_name,
    )


def plan_archive_paths(
    project_root: Path, request: PlanArchiveRequest
) -> tuple[Path | None, Path | None]:
    """Resolve and contain the exact root source and canonical destination."""
    if request.plan_file_name is None:
        return None, None
    plans = get_cortex_path(project_root, CortexResourceType.PLANS)
    source = plans / request.plan_file_name
    subdir = transaction_archive_subdir(request, request.plan_file_name)
    if subdir is None:
        raise ValueError("Cannot determine archive location")
    archive = get_cortex_path(project_root, CortexResourceType.PLANS_ARCHIVE)
    destination = archive / subdir / request.plan_file_name
    validate_contained_path(source, plans)
    validate_contained_path(destination, archive)
    return source, destination


def completion_dependency_slug(
    project_root: Path, operations_root: Path, record: CompletionOperationRecord
) -> str | None:
    """Identify the completed dependency even when no plan file is archived."""
    if record.request.plan_file_name is not None:
        return Path(record.request.plan_file_name).stem
    if record.roadmap_line_removed is None:
        return None

    # AI: Use the prepared roadmap revision, whose row is removed on commit.
    roadmap = next(
        item for item in record.files if item.key == CompletionFileKey.ROADMAP
    )
    before = read_payload(operations_root, roadmap.before_payload)
    lines = before.splitlines()
    if hash_text(before) != roadmap.before_hash or record.roadmap_line_removed > len(
        lines
    ):
        raise ValueError("Completion roadmap changed since preparation")
    reference = extract_plan_path_from_bullet(lines[record.roadmap_line_removed - 1])
    if reference is None:
        return None
    path = project_root / reference
    if path.suffix == ".md" and path.parent == get_cortex_path(
        project_root, CortexResourceType.PLANS
    ):
        return path.stem
    return None


def _append_plan_record(
    project_root: Path,
    request: CompletionRequest,
    files: list[PreparedCompletionFile],
) -> tuple[Path | None, Path | None]:
    source, destination = plan_archive_paths(project_root, request)
    if source is None:
        return source, destination
    plan_before = read_required_text(
        source, get_cortex_path(project_root, CortexResourceType.PLANS)
    )
    if has_cancelled_plan_status(plan_before):
        raise ValueError("Cancelled plans cannot be completed")
    _validate_plan_identity(plan_before, request)
    assert destination is not None
    if destination.exists():
        raise FileExistsError(f"Archive destination already exists: {destination}")
    plan_after = replace_plan_frontmatter_status(plan_before, PlanStatus.DONE)
    if read_plan_status_from_content(plan_after) != PlanStatus.DONE:
        raise ValueError("Plan frontmatter cannot be normalized to DONE")
    files.append(
        _prepared_file(
            CompletionFileKey.PLAN,
            source,
            plan_before,
            plan_after,
        )
    )
    return source, destination


def _append_memory_records(
    project_root: Path,
    request: CompletionRequest,
    files: list[PreparedCompletionFile],
) -> tuple[int, int | None, int | None]:
    mem = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    roadmap = mem / MemoryBankFile.ROADMAP
    active = mem / MemoryBankFile.ACTIVE_CONTEXT
    roadmap_before = read_required_text(roadmap, mem)
    active_before = read_required_text(active, mem)
    line = _roadmap_line(roadmap_before, request)
    active_after, active_line = _active_after(active_before, request)
    files.append(
        _prepared_file(
            CompletionFileKey.ROADMAP,
            roadmap,
            roadmap_before,
            remove_line_at(roadmap_before, line),
        )
    )
    files.append(
        _prepared_file(
            CompletionFileKey.ACTIVE_CONTEXT,
            active,
            active_before,
            active_after,
        )
    )
    progress_line = _append_progress_record(mem, request, files)
    return line, active_line, progress_line


def _append_progress_record(
    memory_root: Path,
    request: CompletionRequest,
    files: list[PreparedCompletionFile],
) -> int | None:
    if request.progress_entry is None:
        return None
    progress = memory_root / MemoryBankFile.PROGRESS
    progress_before = read_required_text(progress, memory_root)
    progress_after, progress_line = _progress_after(progress_before, request)
    files.append(
        _prepared_file(
            CompletionFileKey.PROGRESS,
            progress,
            progress_before,
            progress_after,
        )
    )
    return progress_line


def _new_operation_record(
    project_root: Path,
    request: PlanArchiveRequest,
    files: list[CompletionFileRecord],
    source: Path | None,
    destination: Path | None,
    line_numbers: tuple[int | None, int | None, int | None],
) -> CompletionOperationRecord:
    timestamp = utc_now_iso()
    roadmap_line, active_line, progress_line = line_numbers
    return CompletionOperationRecord(
        operation_id=operation_id(request),
        request_fingerprint=request_fingerprint(request),
        request=request,
        phase=CompletionPhase.PREPARED,
        files=files,
        archive_source=source.relative_to(project_root).as_posix() if source else None,
        archive_destination=(
            destination.relative_to(project_root).as_posix() if destination else None
        ),
        roadmap_line_removed=roadmap_line,
        active_context_line_inserted=active_line,
        progress_line_inserted=progress_line,
        created_at=timestamp,
        updated_at=timestamp,
    )


def prepare_record(
    project_root: Path,
    operations_root: Path,
    request: PlanArchiveRequest,
) -> CompletionOperationRecord:
    """Prevalidate every input/read/destination and persist immutable payloads."""
    prepared_files: list[PreparedCompletionFile]
    if isinstance(request, CancellationRequest):
        from cortex.tools.plans.cancellation_prepare import prepare_cancellation

        prepared = prepare_cancellation(project_root, request)
        source, destination = prepared.source, prepared.destination
        prepared_files = prepared.files
        line_numbers = (prepared.roadmap_line_removed, None, None)
    else:
        prepared_files = []
        source, destination = _append_plan_record(project_root, request, prepared_files)
        line_numbers = _append_memory_records(project_root, request, prepared_files)
    op_id = operation_id(request)
    files = [
        _persist_file_record(project_root, operations_root, op_id, prepared)
        for prepared in prepared_files
    ]
    return _new_operation_record(
        project_root, request, files, source, destination, line_numbers
    )
