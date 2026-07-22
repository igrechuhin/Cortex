"""Read/write flow for manage_file: handle read, handle write, execute_memory_bank_write.

Extracted from file_operations to keep file size under limit. Used by
file_manage_file_helpers (dispatch) and by compaction_operations.
"""

import json
import logging
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict, OperationStatus, VersionMetadata
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_logger import record_spend_tokens
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.files.metadata_operations import (
    compute_file_metrics,
    create_version_snapshot,
    update_file_metadata,
)
from cortex.tools.files.operation_helpers import (
    build_read_error_response,
    build_schema_validation_error_response,
    build_write_error_response,
    execute_validated_write,
    validate_and_prepare_write_content,
    validate_write_request,
)
from cortex.tools.files.section_helpers import extract_content_sections
from cortex.tools.plans.corruption import fix_memory_bank_content_if_needed
from cortex.tools.plans.roadmap_plan_graph_annotate import annotate_roadmap_for_project
from cortex.validation.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

# Avoid circular import: file_lock_guard used only at runtime in _verify_write_lock


def _safe_record_spend(project_root: Path | None, tokens: int) -> None:
    """Record spend tokens; tolerate I/O errors so read/write never fails."""
    if project_root is None:
        return
    try:
        _ = record_spend_tokens(project_root, tokens)
    except OSError as e:
        logger.debug("record_spend_tokens failed for %s: %s", project_root, e)


@dataclass(frozen=True)
class _WriteFlowParams:
    """Bundled params for write flow to keep function length under limit."""

    file_path: Path
    file_name: str
    content: str | None
    change_description: str | None
    schema_validator: SchemaValidator | None
    project_root: Path | None
    fs_manager: FileSystemManager
    metadata_index: MetadataIndex
    token_counter: TokenCounter
    version_manager: VersionManager


@dataclass(frozen=True)
class _ManageFileWriteCtx:
    """Bundled disk write + WAL inputs (structural line budget)."""

    file_path: Path
    file_name: str
    content: str
    change_description: str | None
    fs_manager: FileSystemManager
    metadata_index: MetadataIndex
    token_counter: TokenCounter
    version_manager: VersionManager
    project_root: Path | None = None


async def _build_read_response(
    file_name: str,
    extracted_content: str,
    section_warning: str | None,
    include_metadata: bool,
    metadata_index: MetadataIndex,
    project_root: Path,
) -> str:
    """Build read operation JSON response."""
    response: ModelDict = {
        "status": OperationStatus.SUCCESS.value,
        "file_name": file_name,
        "content": extracted_content,
    }

    if section_warning:
        response["warning"] = section_warning

    if include_metadata:
        metadata = await metadata_index.get_file_metadata(file_name)
        if metadata is not None:
            response["metadata"] = cast(JsonValue, metadata.model_dump(mode="json"))
            # Already-computed token count via MetadataIndex; record once per read.
            _safe_record_spend(project_root, metadata.token_count)

    return json.dumps(response, indent=2)


async def handle_read_operation(
    file_path: Path,
    file_name: str,
    root: Path,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    include_metadata: bool,
    sections: list[str] | None,
) -> str:
    """Handle read operation with optional section extraction."""
    if not file_path.exists():
        return build_read_error_response(file_name, root)

    content_str, _ = await fs_manager.read_file(file_path)
    if file_name == MemoryBankFile.ROADMAP:
        content_str = annotate_roadmap_for_project(content_str, root)
    extracted_content, section_warning = extract_content_sections(content_str, sections)

    return await _build_read_response(
        file_name,
        extracted_content,
        section_warning,
        include_metadata,
        metadata_index,
        root,
    )


async def _validate_schema_if_needed(
    schema_validator: SchemaValidator | None,
    file_name: str,
    content: str,
) -> str | None:
    """Validate file content against schema if validator and schema exist."""
    if schema_validator is not None and schema_validator.get_schema(file_name):
        result = await schema_validator.validate_file(file_name, content)
        if not result.valid:
            return build_schema_validation_error_response(file_name, result)
    return None


async def _verify_write_lock(
    project_root: Path | None,
    file_name: str,
    content: str,
    change_description: str | None,
) -> str | None:
    """Verify lock for write operation. Returns error JSON or None."""
    if project_root is None:
        return None
    from cortex.tools.files.lock_guard import verify_lock_for_file_operation

    is_allowed, lock_error = await verify_lock_for_file_operation(
        project_root=project_root,
        file_name=file_name,
        content=content,
        change_description=change_description,
    )
    if not is_allowed:
        assert lock_error is not None
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": f"Lock verification failed: {lock_error}",
                "file_name": file_name,
            },
            indent=2,
        )
    return None


def _prepare_content_for_write(file_name: str, content: str) -> str:
    """Apply roadmap/progress content fix if applicable."""
    return (
        fix_memory_bank_content_if_needed(content, file_name)
        if file_name in (MemoryBankFile.ROADMAP, MemoryBankFile.PROGRESS)
        else content
    )


def build_write_response(
    file_name: str,
    version_info: VersionMetadata,
    token_counter: TokenCounter,
    content: str,
) -> str:
    """Build write operation response."""
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "file_name": file_name,
            "message": f"✅ File {file_name} written successfully",
            "snapshot_id": version_info.snapshot_path,
            "version": version_info.version,
            "tokens": token_counter.count_tokens(content),
        },
        indent=2,
    )


async def write_file_with_hash_check(
    file_path: Path, content: str, fs_manager: FileSystemManager
) -> None:
    """Write file using on-disk hash as conflict baseline."""
    expected_hash: str | None = None
    if file_path.exists():
        _, expected_hash = await fs_manager.read_file(file_path)
    _ = await fs_manager.write_file(file_path, content, expected_hash=expected_hash)


async def _execute_write_flow(
    file_path: Path,
    file_name: str,
    content: str,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
    project_root: Path | None = None,
) -> str:
    """Execute the main write flow (disk write + metadata; no WAL)."""
    await write_file_with_hash_check(file_path, content, fs_manager)

    file_metrics = compute_file_metrics(content, fs_manager, token_counter)
    version_info = await create_version_snapshot(
        file_path,
        content,
        file_metrics,
        version_manager,
        change_description,
    )

    await update_file_metadata(
        file_name,
        file_path,
        content,
        file_metrics,
        metadata_index,
        version_info,
        token_counter=token_counter,
    )

    # Already-computed token count via compute_file_metrics/MetadataIndex.
    _safe_record_spend(project_root, cast(int, file_metrics.get("token_count", 0)))

    return build_write_response(file_name, version_info, token_counter, content)


async def _read_file_if_exists(
    fs_manager: FileSystemManager, file_path: Path, exists: bool
) -> str:
    if not exists:
        return ""
    text, _ = await fs_manager.read_file(file_path)
    return text


async def _wal_manage_file_after_success(
    fs_manager: FileSystemManager,
    file_path: Path,
    project_root: Path | None,
    before_exists: bool,
    before_content: str,
) -> None:
    from cortex.memory.wal import WalOperation
    from cortex.memory.wal_hooks import try_wal_record_text_mutation

    after_content, _ = await fs_manager.read_file(file_path)
    try_wal_record_text_mutation(
        project_root,
        file_path,
        WalOperation.WRITE,
        before_exists,
        before_content,
        after_content,
        True,
        None,
    )


async def _wal_manage_file_after_conflict(
    fs_manager: FileSystemManager,
    file_path: Path,
    project_root: Path | None,
    before_exists: bool,
    before_content: str,
    exc: FileConflictError | FileLockTimeoutError | GitConflictError,
) -> None:
    from cortex.memory.wal import WalOperation
    from cortex.memory.wal_hooks import try_wal_record_text_mutation

    after_content = ""
    if file_path.exists():
        try:
            after_content, _ = await fs_manager.read_file(file_path)
        except (OSError, ValueError):
            after_content = ""
    try_wal_record_text_mutation(
        project_root,
        file_path,
        WalOperation.WRITE,
        before_exists,
        before_content,
        after_content,
        False,
        str(exc),
    )


async def _execute_write_flow_then_wal(
    ctx: _ManageFileWriteCtx,
    before_exists: bool,
    before_content: str,
) -> str:
    result = await _execute_write_flow(
        ctx.file_path,
        ctx.file_name,
        ctx.content,
        ctx.change_description,
        ctx.fs_manager,
        ctx.metadata_index,
        ctx.token_counter,
        ctx.version_manager,
        ctx.project_root,
    )
    await _wal_manage_file_after_success(
        ctx.fs_manager,
        ctx.file_path,
        ctx.project_root,
        before_exists,
        before_content,
    )
    return result


async def _execute_write_with_error_handling(ctx: _ManageFileWriteCtx) -> str:
    """Execute write flow with error handling and optional WAL."""
    before_exists = ctx.file_path.exists()
    before_content = await _read_file_if_exists(
        ctx.fs_manager, ctx.file_path, before_exists
    )
    try:
        return await _execute_write_flow_then_wal(ctx, before_exists, before_content)
    except (FileConflictError, FileLockTimeoutError, GitConflictError) as e:
        await _wal_manage_file_after_conflict(
            ctx.fs_manager,
            ctx.file_path,
            ctx.project_root,
            before_exists,
            before_content,
            e,
        )
        return build_write_error_response(e)


async def _execute_write_with_project_root(
    project_root: Path | None,
    file_path: Path,
    file_name: str,
    fc: str,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    ctx = _ManageFileWriteCtx(
        file_path=file_path,
        file_name=file_name,
        content=fc,
        change_description=change_description,
        fs_manager=fs_manager,
        metadata_index=metadata_index,
        token_counter=token_counter,
        version_manager=version_manager,
        project_root=project_root,
    )
    return await _execute_write_with_error_handling(ctx)


async def _run_write_flow(p: _WriteFlowParams) -> str:
    """Validate/prepare then execute write."""
    err, final_content = await validate_and_prepare_write_content(
        p.file_path,
        p.file_name,
        p.content,
        p.change_description,
        p.schema_validator,
        p.project_root,
        validate_write_request,
        _verify_write_lock,
        _validate_schema_if_needed,
        _prepare_content_for_write,
    )
    if err is not None:
        return err
    assert final_content is not None
    write_fn = partial(
        _execute_write_with_project_root,
        p.project_root,
    )
    return await execute_validated_write(
        p.file_path,
        p.file_name,
        final_content,
        p.change_description,
        write_fn,
        p.fs_manager,
        p.metadata_index,
        p.token_counter,
        p.version_manager,
    )


async def handle_write_operation(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
    schema_validator: SchemaValidator | None,
    project_root: Path | None = None,
) -> str:
    """Handle write: validate/prepare then execute."""
    p = _WriteFlowParams(
        file_path,
        file_name,
        content,
        change_description,
        schema_validator,
        project_root,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )
    return await _run_write_flow(p)


def validate_file_path(
    fs_manager: FileSystemManager, memory_bank_dir: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and construct safe path. Returns (file_path, error_json)."""
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
        return (file_path, "")
    except (ValueError, PermissionError) as e:
        error_json = json.dumps(
            {"status": OperationStatus.ERROR.value, "error": f"Invalid file name: {e}"},
            indent=2,
        )
        return (None, error_json)


async def handle_rollback_operation(file_name: str, version: int, root: Path) -> str:
    """Handle rollback operation. Restores file from version snapshot."""
    from cortex.tools.memory.foundation_rollback import execute_rollback

    result = await execute_rollback(file_name, version, root)
    if isinstance(result, dict):
        payload = result
    else:
        payload = result.model_dump(exclude_none=True)
    return json.dumps(payload, indent=2)


async def execute_memory_bank_write(
    project_root: Path,
    file_name: str,
    content: str,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    """Write a memory bank file with versioning and metadata.

    For use by compact_session and other internal callers that need the same
    write flow as manage_file (version snapshot, metadata update).
    """
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    file_path, err = validate_file_path(fs_manager, memory_bank_dir, file_name)
    if file_path is None:
        return err
    ctx = _ManageFileWriteCtx(
        file_path=file_path,
        file_name=file_name,
        content=content,
        change_description=change_description,
        fs_manager=fs_manager,
        metadata_index=metadata_index,
        token_counter=token_counter,
        version_manager=version_manager,
        project_root=project_root,
    )
    return await _execute_write_with_error_handling(ctx)
