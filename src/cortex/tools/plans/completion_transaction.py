"""Recoverable transaction coordinator for multi-file plan completion."""

from __future__ import annotations

from pathlib import Path

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.models import OperationStatus
from cortex.tools.plans.completion_models import CompletePlanResult
from cortex.tools.plans.completion_transaction_io import (
    cleanup_completed_records,
    cleanup_operation_payloads,
    completion_lock,
    drop_operation_files,
    hash_text,
    operation_id,
    persist_record,
    read_payload,
    read_record,
    record_path,
    request_fingerprint,
    resolve_archive_paths,
    resolve_record_file,
    save_record_phase,
    validate_record_consistency,
    write_owned_text,
)
from cortex.tools.plans.completion_transaction_models import (
    CompletionFileKey,
    CompletionOperationRecord,
    CompletionPhase,
    CompletionRequest,
)
from cortex.tools.plans.completion_transaction_prepare import prepare_record
from cortex.tools.plans.completion_transaction_recovery import (
    completed_state_present,
    rollback_completion,
)


def _result_error(
    message: str,
    error: str,
    op_id: str | None = None,
    recovery_required: bool = False,
) -> CompletePlanResult:
    return CompletePlanResult(
        status=OperationStatus.ERROR,
        message=message,
        error=error,
        operation_id=op_id,
        recovery_required=recovery_required,
    )


def _success_result(
    project_root: Path, record: CompletionOperationRecord, replay: bool
) -> CompletePlanResult:
    message = "Plan completion committed atomically."
    if replay:
        message = "Plan already completed; identical retry made no changes."
    return CompletePlanResult(
        status=OperationStatus.SUCCESS,
        message=message,
        roadmap_line_removed=record.roadmap_line_removed,
        active_context_line_inserted=record.active_context_line_inserted,
        progress_line_inserted=record.progress_line_inserted,
        archive_path=(
            str(project_root / record.archive_destination)
            if record.archive_destination
            else None
        ),
        operation_id=record.operation_id,
        idempotent_replay=replay,
    )


def _phase_for_file(key: CompletionFileKey) -> CompletionPhase:
    return {
        CompletionFileKey.PLAN: CompletionPhase.PLAN_WRITTEN,
        CompletionFileKey.ROADMAP: CompletionPhase.ROADMAP_WRITTEN,
        CompletionFileKey.ACTIVE_CONTEXT: CompletionPhase.ACTIVE_WRITTEN,
        CompletionFileKey.PROGRESS: CompletionPhase.PROGRESS_WRITTEN,
    }[key]


async def _write_record_files(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    record: CompletionOperationRecord,
) -> None:
    for item in record.files:
        before = read_payload(operations_root, item.before_payload)
        after = read_payload(operations_root, item.after_payload)
        if before != after:
            target = resolve_record_file(project_root, item)
            await write_owned_text(
                manager, target, after, item.before_hash, item.before_exists
            )
        save_record_phase(path, record, _phase_for_file(item.key))


def _archive(project_root: Path, record: CompletionOperationRecord) -> None:
    resolved = resolve_archive_paths(project_root, record)
    if resolved is None:
        return
    source, destination = resolved
    if destination.exists():
        raise FileExistsError(f"Archive destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved = resolve_archive_paths(project_root, record)
    assert resolved is not None
    source, destination = resolved
    plan_state = next(
        item for item in record.files if item.key == CompletionFileKey.PLAN
    )
    if (
        not source.is_file()
        or hash_text(source.read_text(encoding="utf-8")) != plan_state.after_hash
    ):
        raise ValueError("Plan changed before archive move")
    _ = source.replace(destination)


async def _execute_prepared(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    record: CompletionOperationRecord,
) -> CompletePlanResult:
    try:
        await _write_record_files(project_root, operations_root, manager, path, record)
        _archive(project_root, record)
        if record.archive_destination:
            save_record_phase(path, record, CompletionPhase.ARCHIVED)
        save_record_phase(path, record, CompletionPhase.COMPLETED)
        cleanup_completed_records(operations_root)
        return _success_result(project_root, record, False)
    except (
        FileConflictError,
        FileLockTimeoutError,
        GitConflictError,
        OSError,
        ValueError,
    ) as exc:
        return await _rollback_result(
            project_root, operations_root, manager, path, record, exc
        )


async def _rollback_result(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    record: CompletionOperationRecord,
    failure: Exception,
) -> CompletePlanResult:
    rollback_error = await rollback_completion(
        project_root, operations_root, manager, path, record, str(failure)
    )
    if rollback_error:
        return _result_error(
            "Completion failed with explicit recoverable state",
            rollback_error,
            record.operation_id,
            True,
        )
    cleanup_completed_records(operations_root)
    return _result_error(
        "Completion failed and was rolled back", str(failure), record.operation_id
    )


async def _handle_existing_record(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    existing: CompletionOperationRecord,
    fingerprint: str,
) -> CompletePlanResult | None:
    if existing.request_fingerprint != fingerprint:
        return _result_error(
            "Conflicting completion retry rejected",
            "Existing operation parameters differ for this plan",
            existing.operation_id,
        )
    if existing.phase == CompletionPhase.COMPLETED:
        return _completed_retry_result(project_root, existing)
    return await _recover_nonterminal_record(
        project_root, operations_root, manager, path, existing
    )


async def _recover_nonterminal_record(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    existing: CompletionOperationRecord,
) -> CompletePlanResult | None:
    recovery_error = await rollback_completion(
        project_root,
        operations_root,
        manager,
        path,
        existing,
        "Recovered interrupted completion before retry",
    )
    if recovery_error:
        return _result_error(
            "Completion remains in explicit recoverable state",
            recovery_error,
            existing.operation_id,
            True,
        )
    drop_operation_files(operations_root, existing)
    return None


def _completed_retry_result(
    project_root: Path, existing: CompletionOperationRecord
) -> CompletePlanResult:
    if completed_state_present(project_root, existing):
        return _success_result(project_root, existing, True)
    return _result_error(
        "Completed operation state conflicts with current files",
        "Recorded completion is no longer semantically present",
        existing.operation_id,
    )


def _prepare_new_record(
    project_root: Path,
    operations_root: Path,
    path: Path,
    request: CompletionRequest,
    op_id: str,
) -> CompletionOperationRecord:
    cleanup_operation_payloads(operations_root, op_id)
    try:
        record = prepare_record(project_root, operations_root, request)
        persist_record(path, record)
    except (OSError, ValueError):
        cleanup_operation_payloads(operations_root, op_id)
        raise
    return record


async def _run_locked_transaction(
    project_root: Path,
    request: CompletionRequest,
    manager: FileSystemManager,
    operations_root: Path,
    op_id: str,
) -> CompletePlanResult:
    path = record_path(operations_root, op_id)
    existing, record_error = _read_validated_record(
        project_root, operations_root, path, op_id
    )
    if record_error is not None:
        return record_error
    if existing:
        result = await _handle_existing_record(
            project_root,
            operations_root,
            manager,
            path,
            existing,
            request_fingerprint(request),
        )
        if result is not None:
            return result
    record = _prepare_new_record(project_root, operations_root, path, request, op_id)
    return await _execute_prepared(project_root, operations_root, manager, path, record)


def _read_validated_record(
    project_root: Path,
    operations_root: Path,
    path: Path,
    op_id: str,
) -> tuple[CompletionOperationRecord | None, CompletePlanResult | None]:
    try:
        record = read_record(operations_root, path)
    except ValueError as exc:
        return None, _malformed_record_result(op_id, exc)
    if record is None:
        return None, None
    try:
        validate_record_consistency(project_root, operations_root, path, record, op_id)
    except (OSError, ValueError) as exc:
        return None, _invalid_record_result(path, record, op_id, exc)
    return record, None


def _malformed_record_result(op_id: str, failure: ValueError) -> CompletePlanResult:
    return _result_error(
        "Completion operation record is malformed; manual recovery required",
        str(failure),
        op_id,
        True,
    )


def _invalid_record_result(
    path: Path,
    record: CompletionOperationRecord,
    op_id: str,
    failure: Exception,
) -> CompletePlanResult:
    try:
        save_record_phase(path, record, CompletionPhase.RECOVERY_REQUIRED, str(failure))
    except OSError:
        pass
    return _result_error(
        "Completion remains in explicit recoverable state",
        str(failure),
        op_id,
        True,
    )


async def run_completion_transaction(
    project_root: Path, request: CompletionRequest
) -> CompletePlanResult:
    """Complete a plan exactly once or recover its interrupted prior attempt."""
    op_id = operation_id(request)
    try:
        async with completion_lock(project_root) as (manager, operations_root):
            return await _run_locked_transaction(
                project_root, request, manager, operations_root, op_id
            )
    except FileLockTimeoutError as exc:
        return _result_error("Completion lock denied", str(exc), op_id)
    except (FileConflictError, GitConflictError) as exc:
        return _result_error("Completion write conflict", str(exc), op_id)
    except (OSError, ValueError) as exc:
        return _result_error("Completion precondition failed", str(exc), op_id)
