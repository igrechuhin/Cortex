"""Helper functions for file operations error handling."""

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.validation.models import ValidationResult
from cortex.validation.schema_validator import SchemaValidator


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


def build_missing_parameters_error(missing: list[str]) -> str:
    """Build error response for missing required parameters."""
    import json

    from cortex.core.models import JsonValue
    from cortex.tools.tool_error_formatters import format_missing_parameter_error

    example: dict[str, JsonValue] = {
        "file_name": "activeContext.md",
        "operation": "read",
    }
    result = format_missing_parameter_error(missing, "manage_file", example=example)
    parsed = json.loads(result)

    # Add backward-compatible details field for manage_file
    required = ["file_name", "operation"]
    valid_operations = [op.value for op in FileOperation]
    parsed["details"] = {
        "missing": missing,
        "required": required,
        "operation_values": valid_operations,
    }
    parsed["hint"] = (
        "Call manage_file(file_name=..., operation=...) for "
        "read/write/metadata operations. See docs/api/tools.md#manage_file."
    )

    return json.dumps(parsed, indent=2)


def build_new_file_creation_error(file_name: str, memory_bank_dir: Path) -> str:
    """Build error response when attempting to create a new Memory Bank file.

    Cortex Memory Bank files are treated as a fixed, user-controlled set.
    Tools and automated workflows MUST NOT create new files in the
    .cortex/memory-bank/ directory. Only existing files may be modified.
    """
    available_files = [f.name for f in memory_bank_dir.glob("*.md") if f.is_file()]
    return json.dumps(
        {
            "status": "error",
            "error": (
                "Cannot create new Memory Bank file via manage_file: "
                f"{file_name} does not exist. Only existing Memory Bank files "
                "may be modified."
            ),
            "file_name": file_name,
            "available_files": sorted(available_files),
            "hint": (
                "Memory Bank files are managed as a fixed set under "
                ".cortex/memory-bank/. Create new files there manually (with "
                'explicit user approval) before using manage_file(operation="write") '
                "to modify them."
            ),
        },
        indent=2,
    )


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


async def run_validate_prepare_then_execute(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    schema_validator: SchemaValidator | None,
    project_root: Path | None,
    validate_req_fn: Callable[[Path, str, str | None], str | None],
    verify_lock_fn: Callable[..., Awaitable[str | None]],
    validate_schema_fn: Callable[..., Awaitable[str | None]],
    prepare_fn: Callable[[str, str], str],
    execute_fn: Callable[..., Awaitable[str]],
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    """Run validate/prepare then execute write. Returns error JSON or write result."""
    # fmt: off
    err, final_content = await validate_and_prepare_write_content(
        file_path, file_name, content, change_description,
        schema_validator, project_root,
        validate_req_fn, verify_lock_fn, validate_schema_fn, prepare_fn,
    )
    if err is not None:
        return err
    assert final_content is not None
    return await execute_fn(
        file_path, file_name, final_content, change_description,
        fs_manager, metadata_index, token_counter, version_manager,
    )
    # fmt: on


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


def build_read_error_response(file_name: str, root: Path) -> str:
    """Build error response for read operation when file doesn't exist."""
    import json

    from cortex.tools.tool_error_formatters import format_file_not_found_error

    available_files = [
        f.name
        for f in get_cortex_path(root, CortexResourceType.MEMORY_BANK).glob("*.md")
        if f.is_file()
    ]
    result = format_file_not_found_error(
        file_name, available_files, tool_name="manage_file"
    )
    parsed = json.loads(result)

    # Add backward-compatible available_files at top level and in context
    parsed["file_name"] = file_name
    parsed["available_files"] = available_files
    if parsed.get("context"):
        parsed["context"]["available_files"] = available_files

    return json.dumps(parsed, indent=2)


def _build_file_conflict_error_response(
    error: FileConflictError,
) -> tuple[str, dict[str, JsonValue], dict[str, JsonValue]]:
    """Build error response components for FileConflictError."""
    suggestion = (
        f"File '{error.file_name}' was modified externally. "
        "Read the file again to get the latest content, review changes, "
        "and merge your changes before writing. "
        'Use manage_file(operation="read") to get current content.'
    )
    example: dict[str, JsonValue] = {
        "file_name": error.file_name,
        "operation": "read",
    }
    context: dict[str, JsonValue] = {
        "file_name": error.file_name,
        "expected_hash": error.expected_hash[:8] + "...",
        "actual_hash": error.actual_hash[:8] + "...",
    }
    return suggestion, example, context


def _build_lock_timeout_error_response(
    error: FileLockTimeoutError,
) -> tuple[str, dict[str, JsonValue], dict[str, JsonValue]]:
    """Build error response components for FileLockTimeoutError."""
    suggestion = (
        f"Could not acquire lock for '{error.file_name}' after "
        f"{error.timeout_seconds}s. Wait and retry, check for stale lock "
        "files in memory-bank directory, or verify no other process is "
        "accessing the file. If locks are stale, remove .lock files manually."
    )
    example: dict[str, JsonValue] = {
        "file_name": error.file_name,
        "operation": "read",
    }
    context: dict[str, JsonValue] = {
        "file_name": error.file_name,
        "timeout_seconds": error.timeout_seconds,
    }
    return suggestion, example, context


def _build_git_conflict_error_response(
    error: GitConflictError,
) -> tuple[str, dict[str, JsonValue], dict[str, JsonValue]]:
    """Build error response components for GitConflictError."""
    suggestion = (
        f"File '{error.file_name}' contains Git conflict markers. "
        "Resolve the Git merge conflict first by removing conflict markers "
        "(<<<<<<<, =======, >>>>>>>) and choosing the desired content. "
        "Then retry the write operation."
    )
    example: dict[str, JsonValue] = {
        "file_name": error.file_name,
        "operation": "write",
        "content": "# Fixed content without conflict markers\n...",
    }
    context: dict[str, JsonValue] = {"file_name": error.file_name}
    return suggestion, example, context


def build_write_error_response(
    error: FileConflictError | FileLockTimeoutError | GitConflictError,
) -> str:
    """Build error response for write operation with recovery suggestions."""
    from cortex.tools.tool_error_formatters import format_tool_error

    if isinstance(error, FileConflictError):
        suggestion, example, context = _build_file_conflict_error_response(error)
        action_required = suggestion
    elif isinstance(error, FileLockTimeoutError):
        suggestion, example, context = _build_lock_timeout_error_response(error)
        action_required = suggestion
    else:
        suggestion, example, context = _build_git_conflict_error_response(error)
        action_required = suggestion

    return format_tool_error(
        error,
        suggestion=suggestion,
        example=example,
        context=context,
        action_required=action_required,
    )


def build_invalid_operation_error(operation: str) -> str:
    """Build error response for invalid operation."""
    import json

    from cortex.tools.tool_error_formatters import format_invalid_parameter_error

    valid_operations = [op.value for op in FileOperation]
    result = format_invalid_parameter_error(
        "operation", operation, valid_operations, "manage_file"
    )
    parsed = json.loads(result)

    # Add backward-compatible valid_operations and hint at top level
    parsed["valid_operations"] = valid_operations
    parsed["hint"] = (
        "Use one of: 'read', 'write', 'metadata', or 'rollback' for the operation parameter."
    )

    return json.dumps(parsed, indent=2)


def validate_manage_file_operation(
    operation: str | None,
    file_name: str | None,
    version: int | None = None,
) -> tuple[FileOperation | None, str | None]:
    """Validate operation, file_name, and version (for rollback). Returns (parsed_op, None) or (None, error_json)."""
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


def _validation_errors_warnings_payloads(
    validation_result: ValidationResult,
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    """Build errors and warnings payload lists for schema validation JSON."""
    errors_payload = [
        {
            "type": e.type,
            "severity": e.severity,
            "message": e.message,
            "suggestion": e.suggestion,
        }
        for e in validation_result.errors
    ]
    warnings_payload = [
        {
            "type": w.type,
            "severity": w.severity,
            "message": w.message,
            "suggestion": w.suggestion,
        }
        for w in validation_result.warnings
    ]
    return (errors_payload, warnings_payload)


def _build_validation_violations(
    validation_result: ValidationResult,
) -> tuple[list[dict[str, str]], list[str]]:
    """Build violations and fix suggestions from validation result."""
    violations: list[dict[str, str]] = [
        {
            "type": e.type,
            "severity": e.severity,
            "message": e.message,
            "suggestion": e.suggestion or "",
        }
        for e in validation_result.errors
    ]

    fix_suggestions: list[str] = [
        f"{e.type}: {e.message}" + (f" ({e.suggestion})" if e.suggestion else "")
        for e in validation_result.errors[:5]  # Limit to first 5
    ]

    return violations, fix_suggestions


def _build_validation_error_payload(
    file_name: str,
    validation_result: ValidationResult,
) -> dict[str, JsonValue]:
    """Build the validation error payload dictionary."""
    from typing import cast

    errors_payload, warnings_payload = _validation_errors_warnings_payloads(
        validation_result
    )

    example: dict[str, JsonValue] = {
        "file_name": file_name,
        "operation": "write",
        "content": "# File content with required sections\n...",
    }

    # Cast nested dict to JsonValue for type compatibility
    validation_dict: dict[str, JsonValue] = {
        "valid": validation_result.valid,
        "errors": cast(list[JsonValue], errors_payload),
        "warnings": cast(list[JsonValue], warnings_payload),
        "score": validation_result.score,
    }

    return {
        "file_name": file_name,
        "example": example,
        "validation": validation_dict,
    }


def build_schema_validation_error_response(
    file_name: str, validation_result: ValidationResult
) -> str:
    """Build JSON error response when pre-write schema validation fails.

    Use when content does not meet Memory Bank schema (e.g. missing required
    sections) to prevent writing broken or corrupted records.
    """
    import json

    from cortex.tools.tool_error_formatters import format_validation_error

    violations, fix_suggestions = _build_validation_violations(validation_result)

    error = ValueError(
        f"Content for {file_name} does not meet Memory Bank schema. "
        + f"Found {len(validation_result.errors)} error(s)."
    )
    result = format_validation_error(
        error, violations=violations, fix_suggestions=fix_suggestions
    )
    parsed = json.loads(result)

    # Add file_name and example to response
    payload = _build_validation_error_payload(file_name, validation_result)
    parsed.update(payload)

    return json.dumps(parsed, indent=2)
