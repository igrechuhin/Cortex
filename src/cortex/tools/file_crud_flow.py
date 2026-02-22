"""Read/write flow for manage_file: handle read, handle write, execute_memory_bank_write.

Extracted from file_operations to keep file size under limit. Used by
file_manage_file_helpers (dispatch) and by compaction_operations.
"""

import json
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
from cortex.core.models import JsonValue, ModelDict, VersionMetadata
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.file_metadata_operations import (
    compute_file_metrics,
    create_version_snapshot,
    update_file_metadata,
)
from cortex.tools.file_operation_helpers import (
    build_read_error_response,
    build_schema_validation_error_response,
    build_write_error_response,
    run_validate_prepare_then_execute,
    validate_write_request,
)
from cortex.tools.file_section_helpers import extract_content_sections
from cortex.tools.roadmap_corruption import fix_memory_bank_content_if_needed
from cortex.validation.schema_validator import SchemaValidator

# Avoid circular import: file_lock_guard used only at runtime in _verify_write_lock


async def _build_read_response(
    file_name: str,
    extracted_content: str,
    section_warning: str | None,
    include_metadata: bool,
    metadata_index: MetadataIndex,
) -> str:
    """Build read operation JSON response."""
    response: ModelDict = {
        "status": "success",
        "file_name": file_name,
        "content": extracted_content,
    }

    if section_warning:
        response["warning"] = section_warning

    if include_metadata:
        metadata = await metadata_index.get_file_metadata(file_name)
        if isinstance(metadata, dict):
            response["metadata"] = cast(JsonValue, metadata)

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
    extracted_content, section_warning = extract_content_sections(content_str, sections)

    return await _build_read_response(
        file_name, extracted_content, section_warning, include_metadata, metadata_index
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
    from cortex.tools.file_lock_guard import verify_lock_for_file_operation

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
                "status": "error",
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
            "status": "success",
            "file_name": file_name,
            "message": f"✅ File {file_name} written successfully",
            "snapshot_id": version_info.snapshot_path,
            "version": version_info.version,
            "tokens": token_counter.count_tokens(content),
        },
        indent=2,
    )


async def _write_file_with_hash_check(
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
) -> str:
    """Execute the main write flow."""
    await _write_file_with_hash_check(file_path, content, fs_manager)

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

    return build_write_response(file_name, version_info, token_counter, content)


async def _execute_write_with_error_handling(
    file_path: Path,
    file_name: str,
    content: str,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    """Execute write flow with error handling."""
    try:
        return await _execute_write_flow(
            file_path,
            file_name,
            content,
            change_description,
            fs_manager,
            metadata_index,
            token_counter,
            version_manager,
        )
    except (FileConflictError, FileLockTimeoutError, GitConflictError) as e:
        return build_write_error_response(e)


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
    return await run_validate_prepare_then_execute(
        file_path,
        file_name,
        content,
        change_description,
        schema_validator,
        project_root,
        validate_write_request,
        _verify_write_lock,
        _validate_schema_if_needed,
        _prepare_content_for_write,
        _execute_write_with_error_handling,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )


def validate_file_path(
    fs_manager: FileSystemManager, memory_bank_dir: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and construct safe path. Returns (file_path, error_json)."""
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
        return (file_path, "")
    except (ValueError, PermissionError) as e:
        error_json = json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
        return (None, error_json)


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
    return await _execute_write_with_error_handling(
        file_path,
        file_name,
        content,
        change_description,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )
