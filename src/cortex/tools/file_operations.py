"""
File Operations Tools

This module contains the consolidated file management tool for Memory Bank.

Total: 1 tool
- manage_file: Read/write/metadata operations
"""

import json
from pathlib import Path
from typing import Literal, cast

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.responses import error_response
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.initialization import get_managers, get_project_root
from cortex.server import mcp


@mcp.tool()
async def manage_file(
    file_name: str,
    operation: Literal["read", "write", "metadata"],
    content: str | None = None,
    project_root: str | None = None,
    include_metadata: bool = False,
    change_description: str | None = None,
) -> str:
    """Manage Memory Bank file operations: read, write, or get metadata.

    This unified tool handles all file operations within the Memory Bank system,
    providing version control, conflict detection, and metadata tracking. All files
    are stored in the memory-bank/ directory relative to the project root.

    The tool consolidates three distinct operations:
    - read: Retrieve file content with optional metadata (size, tokens, hash, sections)
    - write: Write file content with automatic versioning, conflict detection, and metadata updates
    - metadata: Query file metadata without reading full content

    Args:
        file_name: Name of the file within memory-bank/ directory.
            Examples: "projectBrief.md", "activeContext.md", "systemPatterns.md"
            Must be a valid filename without path traversal characters.

        operation: Operation to perform on the file.
            - "read": Read file content, optionally with metadata
            - "write": Write content with versioning and conflict detection
            - "metadata": Get metadata only (size, tokens, hash, version history)

        content: Content to write to the file (required for write operation).
            Must be valid UTF-8 text. For Markdown files, the content should
            include proper headings and formatting.
            Example: "# Project Brief\n\n## Overview\n\nThis project..."

        project_root: Optional absolute path to project root directory.
            If not provided, uses current working directory.
            Example: "/Users/username/projects/my-app"

        include_metadata: For read operation, include metadata in response.
            When true, response includes size_bytes, token_count, content_hash,
            sections, and version_history alongside content.
            Default: False

        change_description: Optional description for write operation.
            Stored in version history for tracking changes.
            Example: "Updated project goals and milestones"
            Default: "Updated via MCP"

    Returns:
        JSON string with operation result. Structure varies by operation:

        Read operation (success):
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "content": "# Project Brief\\n\\n## Overview\\n...",
          "metadata": {  // Only if include_metadata=true
            "size_bytes": 1024,
            "token_count": 256,
            "content_hash": "abc123...",
            "sections": [
              {"heading": "## Overview", "level": 2},
              {"heading": "## Goals", "level": 2}
            ],
            "version_history": [
              {
                "version": 1,
                "timestamp": "2026-01-04T12:00:00Z",
                "change_description": "Initial version"
              }
            ]
          }
        }

        Write operation (success):
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "message": "File projectBrief.md written successfully",
          "snapshot_id": "/path/to/snapshots/projectBrief.md.v2.snapshot",
          "version": 2,
          "tokens": 256
        }

        Metadata operation (success):
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "metadata": {
            "size_bytes": 1024,
            "token_count": 256,
            "content_hash": "abc123...",
            "sections": [
              {"heading": "## Overview", "level": 2}
            ],
            "version_history": [...]
          }
        }

        Error responses:
        {
          "status": "error",
          "error": "File projectBrief.md does not exist",
          "available_files": ["activeContext.md", "systemPatterns.md"]
        }

    Examples:
        Example 1: Read file with metadata
        >>> await manage_file(
        ...     file_name="projectBrief.md",
        ...     operation="read",
        ...     include_metadata=True
        ... )
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "content": "# Project Brief\\n\\n## Overview\\n\\nMCP Memory Bank...",
          "metadata": {
            "size_bytes": 2048,
            "token_count": 512,
            "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sections": [
              {"heading": "## Overview", "level": 2},
              {"heading": "## Goals", "level": 2},
              {"heading": "## Architecture", "level": 2}
            ],
            "version_history": [
              {
                "version": 1,
                "timestamp": "2026-01-04T10:00:00Z",
                "change_description": "Initial version"
              },
              {
                "version": 2,
                "timestamp": "2026-01-04T11:30:00Z",
                "change_description": "Added architecture section"
              }
            ]
          }
        }

        Example 2: Write file with version control
        >>> await manage_file(
        ...     file_name="activeContext.md",
        ...     operation="write",
        ...     content="# Active Context\\n\\n## Current Work\\n\\nImplementing DRY linking...",
        ...     change_description="Updated current work focus"
        ... )
        {
          "status": "success",
          "file_name": "activeContext.md",
          "message": "File activeContext.md written successfully",
          "snapshot_id": "/Users/username/projects/my-app/.cortex/history/activeContext.md.v3.snapshot",
          "version": 3,
          "tokens": 128
        }

        Example 3: Get metadata only
        >>> await manage_file(
        ...     file_name="systemPatterns.md",
        ...     operation="metadata"
        ... )
        {
          "status": "success",
          "file_name": "systemPatterns.md",
          "metadata": {
            "size_bytes": 4096,
            "token_count": 1024,
            "content_hash": "f7c3bc1d808e04732adf679965ccc34ca7ae3441",
            "sections": [
              {"heading": "## Architecture Patterns", "level": 2},
              {"heading": "## Design Principles", "level": 2},
              {"heading": "## Integration Patterns", "level": 2}
            ],
            "version_history": [
              {
                "version": 1,
                "timestamp": "2026-01-03T14:00:00Z",
                "change_description": "Initial patterns documentation"
              }
            ]
          }
        }

    Note:
        - All file operations are performed within .cortex/memory-bank/ directory for security
        - Write operations create versioned snapshots in .cortex/history/
        - Conflict detection prevents concurrent modification (uses content_hash)
        - File locking prevents race conditions during write operations
        - Token counts use tiktoken encoding (cl100k_base) for accurate context sizing
        - Section extraction is simplified (only extracts level 2 headings starting with "##")
        - Invalid file names with path traversal attempts (.., /, \\) are rejected
        - If file doesn't exist during read/metadata operations, returns available files list
        - Write operations update both the file content and metadata index atomically
    """
    try:
        managers = await _initialize_managers(project_root)
        file_path_result = _validate_and_get_path(
            cast(FileSystemManager, managers["fs"]),
            cast(Path, managers["root"]),
            file_name,
        )
        if file_path_result[0] is None:
            return file_path_result[1]

        return await _dispatch_operation(
            operation,
            file_path_result[0],
            file_name,
            content,
            change_description,
            include_metadata,
            managers,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


def _validate_file_path(
    fs_manager: FileSystemManager, memory_bank_dir: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and construct safe path.

    Returns:
        Tuple of (file_path, error_json). If file_path is None, error_json contains the error.
    """
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
        return (file_path, "")
    except (ValueError, PermissionError) as e:
        error_json = json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
        return (None, error_json)


def _build_read_error_response(file_name: str, root: Path) -> str:
    """Build error response for read operation when file doesn't exist."""
    import json

    available_files = [
        f.name
        for f in get_cortex_path(root, CortexResourceType.MEMORY_BANK).glob("*.md")
        if f.is_file()
    ]
    base_response = json.loads(
        error_response(
            FileNotFoundError(f"File {file_name} does not exist"),
            action_required=(
                f"File '{file_name}' not found in memory bank. "
                f"Available files: {', '.join(available_files) if available_files else 'none'}. "
                "Check the file name spelling, or initialize the memory bank with 'initialize_memory_bank()' "
                "if no files exist yet."
            ),
            context={"file_name": file_name, "available_files": available_files},
        )
    )
    # Add available_files at top level for backward compatibility with tests
    base_response["available_files"] = available_files
    return json.dumps(base_response, indent=2)


async def _handle_read_operation(
    file_path: Path,
    file_name: str,
    root: Path,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    include_metadata: bool,
) -> str:
    """Handle read operation."""
    if not file_path.exists():
        return _build_read_error_response(file_name, root)

    content_str, _ = await fs_manager.read_file(file_path)
    result: dict[str, object] = {
        "status": "success",
        "file_name": file_name,
        "content": content_str,
    }

    if include_metadata:
        metadata = await metadata_index.get_file_metadata(file_name)
        if metadata:
            result["metadata"] = metadata

    return json.dumps(result, indent=2)


async def _handle_write_operation(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str:
    """Handle write operation."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    validation_error = validate_write_content(content)
    if validation_error:
        return validation_error

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


async def _handle_metadata_operation(
    file_path: Path, file_name: str, metadata_index: MetadataIndex
) -> str:
    """Handle metadata operation."""
    if not file_path.exists():
        return json.dumps(
            {"status": "error", "error": f"File {file_name} does not exist"}, indent=2
        )

    metadata = await metadata_index.get_file_metadata(file_name)
    if not metadata:
        return json.dumps(
            {
                "status": "warning",
                "message": f"No metadata found for {file_name}",
                "file_name": file_name,
            },
            indent=2,
        )

    return json.dumps(
        {"status": "success", "file_name": file_name, "metadata": metadata}, indent=2
    )


async def _get_expected_hash(
    metadata_index: MetadataIndex, file_name: str
) -> str | None:
    """Get expected hash from metadata for conflict detection."""
    metadata = await metadata_index.get_file_metadata(file_name)
    return (
        cast(str, metadata.get("content_hash"))
        if metadata and metadata.get("content_hash")
        else None
    )


def compute_file_metrics(
    content: str, fs_manager: FileSystemManager, token_counter: TokenCounter
) -> dict[str, object]:
    """Compute file size, token count, and hash."""
    content_bytes = content.encode("utf-8")
    return {
        "size_bytes": len(content_bytes),
        "token_count": token_counter.count_tokens(content),
        "content_hash": fs_manager.compute_hash(content),
    }


async def create_version_snapshot(
    file_path: Path,
    content: str,
    file_metrics: dict[str, object],
    version_manager: VersionManager,
    change_description: str | None,
) -> dict[str, object]:
    """Create version snapshot."""
    file_name = file_path.name
    version = await version_manager.get_version_count(file_name)
    return await version_manager.create_snapshot(
        file_path,
        version=version + 1,
        content=content,
        size_bytes=cast(int, file_metrics["size_bytes"]),
        token_count=cast(int, file_metrics["token_count"]),
        content_hash=cast(str, file_metrics["content_hash"]),
        change_type="modified",
        change_description=change_description or "Updated via MCP",
    )


async def update_file_metadata(
    file_name: str,
    file_path: Path,
    content: str,
    file_metrics: dict[str, object],
    metadata_index: MetadataIndex,
    version_info: dict[str, object],
) -> None:
    """Update file metadata and version history."""
    sections = extract_sections(content)
    await metadata_index.update_file_metadata(
        file_name,
        path=file_path,
        exists=True,
        size_bytes=cast(int, file_metrics["size_bytes"]),
        token_count=cast(int, file_metrics["token_count"]),
        content_hash=cast(str, file_metrics["content_hash"]),
        sections=sections,
        change_source="internal",
    )
    await metadata_index.add_version_to_history(file_name, version_info)


def extract_sections(content: str) -> list[dict[str, object]]:
    """Extract sections from content (simplified - just count headings)."""
    sections: list[dict[str, object]] = []
    for line in content.split("\n"):
        if line.startswith("##"):
            sections.append({"heading": line.strip(), "level": 2})
    return sections


def build_write_response(
    file_name: str,
    version_info: dict[str, object],
    token_counter: TokenCounter,
    content: str,
) -> str:
    """Build write operation response."""
    return json.dumps(
        {
            "status": "success",
            "file_name": file_name,
            "message": f"File {file_name} written successfully",
            "snapshot_id": version_info.get("snapshot_path"),
            "version": version_info.get("version"),
            "tokens": token_counter.count_tokens(content),
        },
        indent=2,
    )


def validate_write_content(content: str | None) -> str | None:
    """Validate content for write operation."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    return None


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
    expected_hash = await _get_expected_hash(metadata_index, file_name)
    _ = await fs_manager.write_file(file_path, content, expected_hash=expected_hash)

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
    )

    return build_write_response(file_name, version_info, token_counter, content)


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
        f"Could not acquire lock for '{error.file_name}' after {error.timeout_seconds}s. "
        "Wait and retry, check for stale lock files in memory-bank directory, "
        "or verify no other process is accessing the file. "
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
    error_type = type(error).__name__
    if isinstance(error, FileConflictError):
        action_required, context = _get_file_conflict_details(error)
    elif isinstance(error, FileLockTimeoutError):
        action_required, context = _get_lock_timeout_details(error)
    elif isinstance(error, GitConflictError):
        action_required = (
            f"File '{error.file_name}' contains Git conflict markers. "
            "Resolve the Git merge conflict first by removing conflict markers "
            "(<<<<<<<, =======, >>>>>>>) and choosing the desired content. "
            "Then retry the write operation."
        )
        context = {"file_name": error.file_name}
    else:
        action_required = (
            "Review the error details and retry the write operation. "
            "Check file permissions and ensure the memory bank directory is accessible."
        )
        context = {"error_type": error_type}

    # Type cast: context is dict[str, object] compatible
    import json
    from typing import cast

    context_dict = cast(dict[str, object], context)
    base_response = json.loads(
        error_response(error, action_required=action_required, context=context_dict)
    )
    # Add 'suggestion' field for backward compatibility with tests
    base_response["suggestion"] = action_required
    return json.dumps(base_response, indent=2)


def build_invalid_operation_error(operation: str) -> str:
    """Build error response for invalid operation."""
    import json

    valid_operations = ["read", "write", "metadata"]
    base_response = json.loads(
        error_response(
            ValueError(f"Invalid operation: {operation}"),
            action_required=(
                f"Use one of the valid operations: {', '.join(valid_operations)}. "
                f"Received: '{operation}'. "
                f"Example: {{'operation': '{valid_operations[0]}', 'file_name': 'projectBrief.md'}}"
            ),
            context={
                "invalid_operation": operation,
                "valid_operations": valid_operations,
            },
        )
    )
    # Add valid_operations at top level for backward compatibility with tests
    base_response["valid_operations"] = valid_operations
    return json.dumps(base_response, indent=2)


async def _initialize_managers(
    project_root: str | None,
) -> dict[str, object]:
    """Initialize all required managers."""
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    return {
        "root": root,
        "fs": cast(FileSystemManager, mgrs["fs"]),
        "index": cast(MetadataIndex, mgrs["index"]),
        "tokens": cast(TokenCounter, mgrs["tokens"]),
        "versions": cast(VersionManager, mgrs["versions"]),
    }


def _validate_and_get_path(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and get safe file path."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    return _validate_file_path(fs_manager, memory_bank_dir, file_name)


async def _dispatch_operation(
    operation: str,
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    include_metadata: bool,
    managers: dict[str, object],
) -> str:
    """Dispatch operation to appropriate handler."""
    if operation == "read":
        return await _dispatch_read_operation(
            file_path, file_name, managers, include_metadata
        )
    if operation == "write":
        return await _dispatch_write_operation(
            file_path, file_name, content, change_description, managers
        )
    if operation == "metadata":
        return await _dispatch_metadata_operation(file_path, file_name, managers)
    return build_invalid_operation_error(operation)


async def _dispatch_read_operation(
    file_path: Path,
    file_name: str,
    managers: dict[str, object],
    include_metadata: bool,
) -> str:
    """Dispatch read operation."""
    return await _handle_read_operation(
        file_path,
        file_name,
        cast(Path, managers["root"]),
        cast(FileSystemManager, managers["fs"]),
        cast(MetadataIndex, managers["index"]),
        include_metadata,
    )


async def _dispatch_write_operation(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    managers: dict[str, object],
) -> str:
    """Dispatch write operation."""
    if content is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Content is required for write operation",
            },
            indent=2,
        )
    return await _handle_write_operation(
        file_path,
        file_name,
        content,
        change_description,
        cast(FileSystemManager, managers["fs"]),
        cast(MetadataIndex, managers["index"]),
        cast(TokenCounter, managers["tokens"]),
        cast(VersionManager, managers["versions"]),
    )


async def _dispatch_metadata_operation(
    file_path: Path, file_name: str, managers: dict[str, object]
) -> str:
    """Dispatch metadata operation."""
    return await _handle_metadata_operation(
        file_path, file_name, cast(MetadataIndex, managers["index"])
    )
