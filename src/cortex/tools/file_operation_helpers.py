"""Helper functions for file operations error handling."""

import json
from pathlib import Path

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def build_missing_parameters_error(missing: list[str]) -> str:
    """Build error response for missing required parameters."""
    required = ["file_name", "operation"]
    valid_operations = ["read", "write", "metadata"]
    return json.dumps(
        {
            "status": "error",
            "error": f"Missing required parameters: {', '.join(missing)}",
            "details": {
                "missing": missing,
                "required": required,
                "operation_values": valid_operations,
            },
            "hint": (
                "Call manage_file(file_name=..., operation=...) for "
                "read/write/metadata operations. See docs/api/tools.md#manage_file."
            ),
        },
        indent=2,
    )


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


def build_read_error_response(file_name: str, root: Path) -> str:
    """Build error response for read operation when file doesn't exist."""
    available_files = [
        f.name
        for f in get_cortex_path(root, CortexResourceType.MEMORY_BANK).glob("*.md")
        if f.is_file()
    ]
    return json.dumps(
        {
            "status": "error",
            "error": f"File {file_name} does not exist",
            "file_name": file_name,
            "available_files": available_files,
            "context": {"file_name": file_name, "available_files": available_files},
        },
        indent=2,
    )


def _get_file_conflict_details(
    error: FileConflictError,
) -> tuple[str, dict[str, str]]:
    """Get action_required and context for FileConflictError."""
    action_required = (
        f"File '{error.file_name}' was modified externally. "
        "Read the file again to get the latest content, review changes, "
        "and merge your changes before writing. "
        "Use 'manage_file(operation=\"read\")' to get current content."
    )
    context = {
        "file_name": error.file_name,
        "expected_hash": error.expected_hash[:8] + "...",
        "actual_hash": error.actual_hash[:8] + "...",
    }
    return action_required, context


def _get_lock_timeout_details(
    error: FileLockTimeoutError,
) -> tuple[str, dict[str, str | int]]:
    """Get action_required and context for FileLockTimeoutError."""
    action_required = (
        f"Could not acquire lock for '{error.file_name}' after "
        f"{error.timeout_seconds}s. Wait and retry, check for stale lock "
        "files in memory-bank directory, or verify no other process is "
        "accessing the file. "
        "If locks are stale, remove .lock files manually."
    )
    context = {
        "file_name": error.file_name,
        "timeout_seconds": error.timeout_seconds,
    }
    return action_required, context


def build_write_error_response(
    error: FileConflictError | FileLockTimeoutError | GitConflictError,
) -> str:
    """Build error response for write operation with recovery suggestions."""
    if isinstance(error, FileConflictError):
        action_required, context = _get_file_conflict_details(error)
    elif isinstance(error, FileLockTimeoutError):
        action_required, context = _get_lock_timeout_details(error)
    else:
        # error must be GitConflictError based on type signature
        action_required = (
            f"File '{error.file_name}' contains Git conflict markers. "
            "Resolve the Git merge conflict first by removing conflict markers "
            "(<<<<<<<, =======, >>>>>>>) and choosing the desired content. "
            "Then retry the write operation."
        )
        context = {"file_name": error.file_name}
    return json.dumps(
        {
            "status": "error",
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context,
            "suggestion": action_required,
        },
        indent=2,
    )


def build_invalid_operation_error(operation: str) -> str:
    """Build error response for invalid operation."""
    valid_operations = ["read", "write", "metadata"]
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid operation: {operation}",
            "valid_operations": valid_operations,
            "hint": (
                "Use one of: 'read', 'write', or 'metadata' for the operation "
                "parameter."
            ),
        },
        indent=2,
    )
