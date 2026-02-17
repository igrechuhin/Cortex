"""
File Operations Tools

This module contains the consolidated file management tool and read resource
for Memory Bank.

Total: 1 tool, 1 resource
- manage_file: Read/write/metadata operations (unified)
- get_file_resource: Read file via cortex://memory-bank/file/{file_name}

Note: write_file has been merged into manage_file with operation="write"
"""

import json
import logging
import time
from pathlib import Path
from typing import Literal, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict, SectionMetadata, VersionMetadata
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.core.version_manager import VersionManager
from cortex.managers.initialization import get_managers
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.file_operation_helpers import (
    FileOperation,
    build_invalid_operation_error,
    build_new_file_creation_error,
    build_read_error_response,
    build_schema_validation_error_response,
    build_write_error_response,
    validate_manage_file_operation,
)
from cortex.tools.file_section_helpers import (
    extract_content_sections,
)
from cortex.tools.roadmap_corruption import fix_memory_bank_content_if_needed
from cortex.validation.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

# Valid operation values for manage_file() (must match FileOperation enum).
ManageFileOperationName = Literal["read", "write", "metadata"]

MANAGE_FILE_INPUT_EXAMPLES: list[dict[str, object]] = [
    {
        "file_name": MemoryBankFile.PROJECT_BRIEF,
        "operation": "read",
        "include_metadata": True,
    },
    {
        "file_name": MemoryBankFile.ACTIVE_CONTEXT,
        "operation": "write",
        "content": "# Active Context\n\n## Current Work\n\n...",
        "change_description": "Updated current work focus",
    },
    {"file_name": MemoryBankFile.ROADMAP, "operation": "metadata"},
]


@mcp.tool(
    annotations=safe_write_annotations("Manage Memory Bank Files"),
    meta={"input_examples": MANAGE_FILE_INPUT_EXAMPLES},
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def manage_file(
    file_name: str | None = None,
    operation: ManageFileOperationName | None = None,
    content: str | None = None,
    include_metadata: bool = False,
    change_description: str | None = None,
    sections: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Manage Memory Bank file operations: read, write, or get metadata.

    USE WHEN: User needs to read/write memory bank files, user requests file
    content, user needs file metadata, user wants to update project context
    files.

    EXAMPLES: 'read projectBrief.md', 'update activeContext.md', 'get metadata
    for roadmap.md', 'write new content to systemPatterns.md'.

    RETURNS: JSON with file content (read), success status (write), or metadata
    object (metadata operation).

    This unified tool handles all file operations within the Memory Bank system,
    providing version control, conflict detection, and metadata tracking. All files
    are stored in the memory-bank/ directory relative to the project root.

    The tool consolidates three distinct operations:
    - read: Retrieve file content with optional metadata (size, tokens, hash, sections)
    - write: Write file content with automatic versioning, conflict
      detection, and metadata updates
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

        include_metadata: For read operation, include metadata in response.
            When true, response includes size_bytes, token_count, content_hash,
            sections, and version_history alongside content.
            Default: False

        change_description: Optional description for write operation.
            Stored in version history for tracking changes.
            Example: "Updated project goals and milestones"
            Default: "Updated via MCP"

        sections: For read operation, extract one or more sections by heading.
            Example: ["## Current Focus"] for single section
            Example: ["## Current Focus", "## Next Steps"] for multiple sections
            Supports nested headings using "/" separator (e.g., ["## Completed Work/### 2026-02-11"]).
            If section not found, returns full file with warning.
            Returns concatenated content of all requested sections (separated by "---").

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
            "content_hash": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
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
        ...     content=(
        ...         "# Active Context\\n\\n## Current Work\\n\\n"
        ...         "Implementing DRY linking..."
        ...     ),
        ...     change_description="Updated current work focus"
        ... )
        {
          "status": "success",
          "file_name": "activeContext.md",
          "message": "File activeContext.md written successfully",
          "snapshot_id": (
              "/Users/username/projects/my-app/.cortex/history/"
              "activeContext.md.v3.snapshot"
          ),
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
        - All file operations are performed within .cortex/memory-bank/
          directory for security
        - Write operations create versioned snapshots in .cortex/history/
        - Conflict detection prevents concurrent modification
          (uses content_hash)
        - File locking prevents race conditions during write operations
        - Token counts use tiktoken encoding (cl100k_base) for accurate
          context sizing
        - Section extraction is simplified (only extracts level 2 headings
          starting with "##")
        - Invalid file names with path traversal attempts (.., /, \\) are
          rejected
        - If file doesn't exist during read/metadata operations, returns
          available files list
        - Write operations update both the file content and metadata index
          atomically
    """
    await log_client(
        ctx,
        "info",
        f"manage_file: starting file_name={file_name!r} operation={operation!r}",
        logger_name=__name__,
    )
    return await _manage_file_validate_and_run(
        ctx,
        file_name,
        operation,
        content,
        include_metadata,
        change_description,
        sections,
    )


@mcp.resource(uri="cortex://memory-bank/file/{file_name}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_file_resource(file_name: str) -> str:
    """Resource: Read a Memory Bank file. Read via cortex://memory-bank/file/{file_name}."""
    root = await get_or_resolve_project_root(None)
    return await _execute_file_operation(
        root,
        file_name,
        FileOperation.READ,
        None,
        False,
        None,
        None,  # sections
    )


async def _manage_file_get_root(ctx: MCPContext | None) -> Path:
    """Return current project root or resolve via ctx."""
    return await get_or_resolve_project_root(ctx)


async def _log_validation_failure(
    ctx: MCPContext | None, file_name: str | None, operation: str | None
) -> None:
    """Log validation failure for manage_file.

    Args:
        ctx: MCP context
        file_name: File name (may be None)
        operation: Operation (may be None)
    """
    await log_client(
        ctx,
        "warning",
        f"manage_file: validation failed file_name={file_name!r} operation={operation!r}",
        logger_name=__name__,
    )


async def _manage_file_validate_and_run(
    ctx: MCPContext | None,
    file_name: str | None,
    operation: str | None,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Validate manage_file inputs and run operation or return error."""
    parsed_op, err = validate_manage_file_operation(operation, file_name)
    if err is not None:
        await _log_validation_failure(ctx, file_name, operation)
        return err

    assert parsed_op is not None and file_name is not None
    root = await _manage_file_get_root(ctx)
    return await _manage_file_run_or_error(
        ctx,
        file_name,
        parsed_op,
        content,
        root,
        include_metadata,
        change_description,
        sections,
    )


def _manage_file_error_response(exc: Exception) -> str:
    """Build JSON error response for manage_file failures."""
    return json.dumps(
        {"status": "error", "error": str(exc), "error_type": type(exc).__name__},
        indent=2,
    )


async def _log_manage_file_result(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    error: Exception | None,
) -> None:
    """Log manage_file completion or failure."""
    if error is None:
        await log_client(
            ctx,
            "info",
            f"manage_file: completed file_name={file_name!r} operation={parsed_op!r}",
            logger_name=__name__,
        )
    else:
        await log_client(
            ctx,
            "error",
            f"manage_file: operation failed file_name={file_name!r} operation={parsed_op!r}: {error}",
            logger_name=__name__,
        )


async def _log_result_by_status(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    result: str,
) -> None:
    """Log manage_file result from JSON response status (error vs success)."""
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            p = cast(dict[str, object], parsed)
            if p.get("status") == "error":
                err_msg = str(p.get("error") or "Operation failed")
                await _log_manage_file_result(
                    ctx, file_name, parsed_op, ValueError(err_msg)
                )
            else:
                await _log_manage_file_result(ctx, file_name, parsed_op, None)
        else:
            await _log_manage_file_result(ctx, file_name, parsed_op, None)
    except (json.JSONDecodeError, TypeError):
        await _log_manage_file_result(ctx, file_name, parsed_op, None)


async def _manage_file_run_or_error(
    ctx: MCPContext | None,
    file_name: str,
    parsed_op: FileOperation,
    content: str | None,
    root: Path,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Run _execute_file_operation and handle exceptions with logging."""
    try:
        result = await _execute_file_operation(
            root,
            file_name,
            parsed_op,
            content,
            include_metadata,
            change_description,
            sections,
        )
        await _log_result_by_status(ctx, file_name, parsed_op, result)
        return result
    except Exception as e:
        await _log_manage_file_result(ctx, file_name, parsed_op, e)
        return _manage_file_error_response(e)


async def _get_managers_for_root(root: Path) -> tuple[ManagersDict, FileSystemManager]:
    """Resolve managers for root; reuse current when root matches."""
    current_mgrs = get_current_managers()
    current_root = get_current_project_root()
    if (
        current_mgrs is not None
        and current_root is not None
        and current_root.resolve() == root.resolve()
    ):
        logger.debug(
            "file_operations: reusing current managers for root %s",
            root,
        )
        managers = ManagersDict.model_validate(current_mgrs)
    else:
        t0 = time.monotonic()
        managers = await get_managers(root)
        logger.debug(
            "file_operations: get_managers(%s) took %.3fs",
            root,
            time.monotonic() - t0,
        )
    return managers, managers.fs


async def _execute_file_operation(
    root: Path,
    file_name: str,
    operation: FileOperation,
    content: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
) -> str:
    """Execute file operation after validation. Reuses current managers when root matches."""
    managers, fs_manager = await _get_managers_for_root(root)
    file_path_result = _validate_and_get_path(fs_manager, root, file_name)
    if file_path_result[0] is None:
        return file_path_result[1]
    return await _dispatch_operation(
        operation,
        file_path_result[0],
        file_name,
        content,
        change_description,
        include_metadata,
        root,
        managers,
        sections,
    )


def _validate_file_path(
    fs_manager: FileSystemManager, memory_bank_dir: Path, file_name: str
) -> tuple[Path | None, str]:
    """Validate file name and construct safe path.

    Returns:
        Tuple of (file_path, error_json). If file_path is None,
        error_json contains the error.
    """
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
        return (file_path, "")
    except (ValueError, PermissionError) as e:
        error_json = json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
        return (None, error_json)


async def _build_read_response(
    file_name: str,
    extracted_content: str,
    section_warning: str | None,
    include_metadata: bool,
    metadata_index: MetadataIndex,
) -> str:
    """Build read operation JSON response.

    Args:
        file_name: Name of file
        extracted_content: Content to include
        section_warning: Optional warning message
        include_metadata: Whether to include metadata
        metadata_index: Metadata index instance

    Returns:
        JSON response string
    """
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


async def _handle_read_operation(
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


def _validate_write_request(
    file_path: Path, file_name: str, content: str | None
) -> str | None:
    """Validate write request parameters."""
    if content is None:
        return json.dumps(
            {"status": "error", "error": "Content is required for write operation"},
            indent=2,
        )
    if not file_path.exists():
        return build_new_file_creation_error(file_name, file_path.parent)
    return validate_write_content(content)


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


async def _handle_write_operation(
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
    """Handle write operation with pre-write schema and content validation."""
    if validation_error := _validate_write_request(file_path, file_name, content):
        return validation_error
    assert content is not None

    if lock_error := await _verify_write_lock(
        project_root, file_name, content, change_description
    ):
        return lock_error

    if file_name in (MemoryBankFile.ROADMAP, MemoryBankFile.PROGRESS):
        content = fix_memory_bank_content_if_needed(content, file_name)
    if schema_validator is not None and schema_validator.get_schema(file_name):
        result = await schema_validator.validate_file(file_name, content)
        if not result.valid:
            return build_schema_validation_error_response(file_name, result)
    return await _execute_write_with_error_handling(file_path, file_name, content, change_description, fs_manager, metadata_index, token_counter, version_manager)


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


async def _handle_metadata_operation(
    file_path: Path, file_name: str, metadata_index: MetadataIndex
) -> str:
    """Handle metadata operation."""
    if not file_path.exists():
        return json.dumps(
            {
                "status": "error",
                "error": f"File {file_name} does not exist",
                "file_name": file_name,
            },
            indent=2,
        )

    metadata = await metadata_index.get_file_metadata(file_name)
    if not metadata:
        return json.dumps(
            {
                "status": "warning",
                "file_name": file_name,
                "metadata": None,
                "message": f"No metadata found for {file_name}",
            },
            indent=2,
        )

    return json.dumps(
        {
            "status": "success",
            "file_name": file_name,
            "metadata": metadata,
        },
        indent=2,
    )


def compute_file_metrics(
    content: str, fs_manager: FileSystemManager, token_counter: TokenCounter
) -> ModelDict:
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
    file_metrics: ModelDict,
    version_manager: VersionManager,
    change_description: str | None,
) -> VersionMetadata:
    """Create version snapshot."""
    file_name = file_path.name
    version = await version_manager.get_version_count(file_name)
    snapshot = await version_manager.create_snapshot(
        file_path,
        version=version + 1,
        content=content,
        size_bytes=cast(int, file_metrics.get("size_bytes", 0)),
        token_count=cast(int, file_metrics.get("token_count", 0)),
        content_hash=cast(str, file_metrics.get("content_hash", "")),
        change_type="modified",
        change_description=change_description or "Updated via MCP",
    )
    return snapshot


async def update_file_metadata(
    file_name: str,
    file_path: Path,
    content: str,
    file_metrics: ModelDict,
    metadata_index: MetadataIndex,
    version_info: VersionMetadata,
    token_counter: TokenCounter | None = None,
) -> None:
    """Update file metadata and version history."""
    sections_raw = extract_sections(content, token_counter=token_counter)
    sections = [section.model_dump(mode="json") for section in sections_raw]
    await metadata_index.update_file_metadata(
        file_name,
        path=file_path,
        exists=True,
        size_bytes=cast(int, file_metrics.get("size_bytes", 0)),
        token_count=cast(int, file_metrics.get("token_count", 0)),
        content_hash=cast(str, file_metrics.get("content_hash", "")),
        sections=sections,
        change_source="internal",
    )
    await metadata_index.add_version_to_history(
        file_name, version_info.model_dump(mode="json")
    )


def _close_section_and_add(
    current_section: dict[str, str | int],
    line_end: int,
    lines: list[str],
    sections: list[SectionMetadata],
    token_counter: TokenCounter,
) -> None:
    """Close a section and add it to sections list.

    Args:
        current_section: Section dictionary with heading, level, line_start
        line_end: Ending line number (exclusive)
        lines: All file lines
        sections: List to append section to
        token_counter: Token counter instance
    """
    import hashlib

    line_start = int(current_section["line_start"])
    section_lines = lines[line_start - 1 : line_end]
    section_content = "\n".join(section_lines)
    section_tokens = token_counter.count_tokens(section_content)
    section_hash = (
        "sha256:" + hashlib.sha256(section_content.encode("utf-8")).hexdigest()
    )

    sections.append(
        SectionMetadata(
            heading=str(current_section["heading"]),
            level=int(current_section["level"]),
            line_start=line_start,
            line_end=line_end,
            content_hash=section_hash,
            token_count=section_tokens,
        )
    )


def extract_sections(
    content: str, token_counter: TokenCounter | None = None
) -> list[SectionMetadata]:
    """Extract sections from markdown content with proper boundaries and token counts.

    Extracts all markdown headings (# through ######) and calculates:
    - Proper line_end by finding next heading of same or higher level
    - Token count for each section
    - Content hash for each section

    Args:
        content: Markdown file content
        token_counter: Optional TokenCounter instance. If None, creates one.

    Returns:
        List of SectionMetadata with proper boundaries and token counts
    """
    import re

    lines = content.split("\n")
    sections: list[SectionMetadata] = []
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    if token_counter is None:
        token_counter = TokenCounter()
    current_section: dict[str, str | int] | None = None

    for i, line in enumerate(lines, start=1):
        match = heading_pattern.match(line.strip())

        if match:
            if current_section is not None:
                _close_section_and_add(
                    current_section, i - 1, lines, sections, token_counter
                )

            level = len(match.group(1))
            current_section = {
                "heading": line.strip(),
                "level": level,
                "line_start": i,
            }

    if current_section is not None:
        _close_section_and_add(
            current_section, len(lines), lines, sections, token_counter
        )

    return sections


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


async def _write_file_with_hash_check(
    file_path: Path, content: str, fs_manager: FileSystemManager
) -> None:
    """Write file using on-disk hash as conflict baseline.

    Rationale: `MetadataIndex` may be stale relative to disk (e.g. external edits,
    editor save, git operations). Using the cached hash can incorrectly block
    writes with FileConflictError even when the caller is acting on the latest
    file contents.
    """
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
    file_path, err = _validate_file_path(fs_manager, memory_bank_dir, file_name)
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


def _validate_and_get_path(fs_manager: FileSystemManager, root: Path, file_name: str) -> tuple[Path | None, str]:
    """Validate file name and get safe file path."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    return _validate_file_path(fs_manager, memory_bank_dir, file_name)


async def _dispatch_operation(
    operation: FileOperation,
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    include_metadata: bool,
    root: Path,
    managers: ManagersDict,
    sections: list[str] | None,
) -> str:
    """Dispatch operation to appropriate handler."""
    if operation == FileOperation.READ:
        return await _dispatch_read_operation(file_path, file_name, root, managers, include_metadata, sections)
    if operation == FileOperation.WRITE:
        return await _dispatch_write_operation(file_path, file_name, content, change_description, managers, root)
    if operation == FileOperation.METADATA:
        return await _dispatch_metadata_operation(file_path, file_name, managers)
    return build_invalid_operation_error(operation.value)


async def _dispatch_read_operation(
    file_path: Path,
    file_name: str,
    root: Path,
    managers: ManagersDict,
    include_metadata: bool,
    sections: list[str] | None,
) -> str:
    """Dispatch read operation."""
    return await _handle_read_operation(file_path, file_name, root, managers.fs, managers.index, include_metadata, sections)


async def _resolve_schema_validator(managers: ManagersDict) -> SchemaValidator | None:
    """Resolve schema validator from managers if available."""
    try:
        return await get_manager(managers, "schema_validator", SchemaValidator)
    except (KeyError, TypeError, AttributeError):
        return None


async def _dispatch_write_operation(
    file_path: Path,
    file_name: str,
    content: str | None,
    change_description: str | None,
    managers: ManagersDict,
    root: Path,
) -> str:
    """Dispatch write operation."""
    if content is None:
        return json.dumps({"status": "error", "error": "Content is required for write operation"}, indent=2)
    schema_validator = await _resolve_schema_validator(managers)
    return await _handle_write_operation(file_path, file_name, content, change_description, managers.fs, managers.index, managers.tokens, managers.versions, schema_validator, project_root=root)


async def _dispatch_metadata_operation(file_path: Path, file_name: str, managers: ManagersDict) -> str:
    """Dispatch metadata operation."""
    return await _handle_metadata_operation(file_path, file_name, managers.index)
