"""Error response builders for file operations.

Extracted from file_operation_helpers to keep that file under 400 lines.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.models import JsonValue
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.models import ValidationResult


def _get_file_operation_enum():
    """Late import to avoid circular dependency with file_operation_helpers."""
    from cortex.tools.file_operation_helpers import FileOperation

    return FileOperation


def build_missing_parameters_error(missing: list[str]) -> str:
    """Build error response for missing required parameters."""
    from cortex.tools.tool_error_formatters import format_missing_parameter_error

    example: dict[str, JsonValue] = {
        "file_name": "activeContext.md",
        "operation": "read",
    }
    result = format_missing_parameter_error(missing, "manage_file", example=example)
    parsed = json.loads(result)

    required = ["file_name", "operation"]
    FileOperation = _get_file_operation_enum()
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
    """Build error response when attempting to create a new Memory Bank file."""
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


def build_read_error_response(file_name: str, root: Path) -> str:
    """Build error response for read operation when file doesn't exist."""
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
    from cortex.tools.tool_error_formatters import format_invalid_parameter_error

    FileOperation = _get_file_operation_enum()
    valid_operations = [op.value for op in FileOperation]
    result = format_invalid_parameter_error(
        "operation", operation, valid_operations, "manage_file"
    )
    parsed = json.loads(result)

    parsed["valid_operations"] = valid_operations
    parsed["hint"] = (
        "Use one of: 'read', 'write', 'metadata', or 'rollback' for the operation parameter."
    )

    return json.dumps(parsed, indent=2)


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
        for e in validation_result.errors[:5]
    ]

    return violations, fix_suggestions


def _build_validation_error_payload(
    file_name: str,
    validation_result: ValidationResult,
) -> dict[str, JsonValue]:
    """Build the validation error payload dictionary."""
    errors_payload, warnings_payload = _validation_errors_warnings_payloads(
        validation_result
    )

    example: dict[str, JsonValue] = {
        "file_name": file_name,
        "operation": "write",
        "content": "# File content with required sections\n...",
    }

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
    """Build JSON error response when pre-write schema validation fails."""
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

    payload = _build_validation_error_payload(file_name, validation_result)
    parsed.update(payload)

    return json.dumps(parsed, indent=2)
