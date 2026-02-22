"""CRUD entry points for Memory Bank: manage_file tool and get_file_resource.

Thin layer that delegates to file_manage_file_helpers. Kept separate to meet
file size limit while preserving full manage_file docstring.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp
from cortex.tools.file_manage_file_helpers import (
    execute_file_operation,
    manage_file_validate_and_run,
)
from cortex.tools.file_operation_helpers import FileOperation
from cortex.tools.tool_categories import ALLOWED_CALLERS_CODE_EXECUTION

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
    meta={
        "input_examples": MANAGE_FILE_INPUT_EXAMPLES,
        "allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION),
    },
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def manage_file(
    file_name: str | None = None,
    operation: FileOperation | None = None,
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

        Example 3: Get metadata only
        >>> await manage_file(
        ...     file_name="systemPatterns.md",
        ...     operation="metadata"
        ... )

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
    return await manage_file_validate_and_run(
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
    return await execute_file_operation(
        root,
        file_name,
        FileOperation.READ,
        None,
        False,
        None,
        None,  # sections
    )
