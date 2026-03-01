"""Helper functions for file operations error handling."""

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.file_operation_error_responses import (
    build_invalid_operation_error,
    build_missing_parameters_error,
    build_new_file_creation_error,
    build_read_error_response,
    build_schema_validation_error_response,
    build_write_error_response,
)
from cortex.validation.schema_validator import SchemaValidator

__all__ = [
    "FileOperation",
    "build_invalid_operation_error",
    "build_missing_parameters_error",
    "build_new_file_creation_error",
    "build_read_error_response",
    "build_schema_validation_error_response",
    "build_write_error_response",
    "execute_validated_write",
    "parse_file_operation",
    "validate_and_prepare_write_content",
    "validate_manage_file_operation",
    "validate_write_content",
    "validate_write_request",
]


class FileOperation(str, Enum):
    """Fixed set of manage_file operations. Use instead of raw strings."""

    READ = "read"
    WRITE = "write"
    METADATA = "metadata"
    ROLLBACK = "rollback"


def parse_file_operation(value: str | None) -> FileOperation | None:
    """Parse string to FileOperation. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return FileOperation(value)
    except ValueError:
        return None


async def validate_and_prepare_write_content(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    schema_validator: SchemaValidator | None,
    project_root: Path | None,
    validate_request_fn: Callable[[Path, str, str | None], str | None],
    verify_lock_fn: Callable[..., Awaitable[str | None]],
    validate_schema_fn: Callable[..., Awaitable[str | None]],
    prepare_content_fn: Callable[[str, str], str],
) -> tuple[str | None, str | None]:
    """Run write validations; return (error_json, None) or (None, prepared_content)."""
    if err := validate_request_fn(file_path, file_name, content):
        return (err, None)
    assert content is not None
    if err := await verify_lock_fn(
        project_root, file_name, content, change_description
    ):
        return (err, None)
    content = prepare_content_fn(file_name, content)
    if err := await validate_schema_fn(schema_validator, file_name, content):
        return (err, None)
    return (None, content)


async def execute_validated_write(
    file_path: Path,
    file_name: str,
    final_content: str,
    change_description: str | None,
    execute_fn: Callable[..., Awaitable[str]],
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    """Execute write with prepared content. Call after validation succeeds."""
    return await execute_fn(
        file_path,
        file_name,
        final_content,
        change_description,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )


def validate_write_content(content: str | None) -> str | None:
    """Validate content for write operation (required, no null bytes)."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    if "\x00" in content:
        return json.dumps(
            {
                "status": "error",
                "error": "Content must not contain null bytes (invalid for text files)",
                "hint": "Remove binary or control characters and retry.",
            },
            indent=2,
        )
    return None


def validate_write_request(
    file_path: Path, file_name: str, content: str | None
) -> str | None:
    """Validate write request parameters. Returns error JSON or None."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    if not file_path.exists():
        return build_new_file_creation_error(file_name, file_path.parent)
    return validate_write_content(content)


def validate_manage_file_operation(
    operation: str | None,
    file_name: str | None,
    version: int | None = None,
) -> tuple[FileOperation | None, str | None]:
    """Validate operation, file_name, and version. Returns (parsed_op, None) or (None, error_json)."""
    parsed_op = parse_file_operation(operation)
    if parsed_op is None:
        if operation is None:
            missing_params: list[str] = []
            if not file_name:
                missing_params.append("file_name")
            missing_params.append("operation")
            return (None, build_missing_parameters_error(missing_params))
        return (None, build_invalid_operation_error(str(operation)))
    if not file_name:
        return (None, build_missing_parameters_error(["file_name"]))
    if parsed_op == FileOperation.ROLLBACK and version is None:
        return (
            None,
            json.dumps(
                {
                    "status": "error",
                    "error": "Version is required for rollback operation",
                    "hint": "Call manage_file(operation='rollback', file_name='...', version=<int>)",
                },
                indent=2,
            ),
        )
    return (parsed_op, None)
