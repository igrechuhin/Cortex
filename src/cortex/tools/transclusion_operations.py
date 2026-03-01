"""Transclusion resolution operations for Memory Bank files.

This module contains the resolve_transclusions MCP tool and its helper functions
for resolving {{include:}} transclusion directives.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import (
    ensure_usage_context,
    execute_tool_with_stability,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.managers.initialization import get_managers
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.context_auxiliary_models import (
    ResolveTransclusionsErrorResult,
    ResolveTransclusionsResult,
)
from cortex.tools.transclusion_response_helpers import (
    build_transclusion_success_response,
    resolve_transclusions_error_json,
)


# Tool consolidated into query_memory_bank (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def resolve_transclusions(
    file_name: str,
    max_depth: int = 5,
    ctx: MCPContext | None = None,
) -> str:
    """Resolve all {{include:}} transclusion directives in a file by
    replacing them with actual content.

    USE WHEN: User needs expanded file content, user wants to see
    transcluded content, user requests transclusion resolution, user needs
    full file content without transclusions.

    EXAMPLES: 'resolve transclusions in projectBrief.md', 'expand
    transclusions', 'get full content with transclusions resolved'.

    RETURNS: JSON with resolved content where all {{include:}} directives
    are replaced with actual file content.

    Reads the specified file and recursively resolves all transclusion
    directives by replacing them with the actual content from referenced
    files. Supports nested transclusions where included files can themselves
    contain transclusion directives.

    The resolution process:
    1. Parses file for {{include:file.md}} or {{include:file.md#section}} directives
    2. Loads referenced content (entire file or specific section)
    3. Recursively resolves transclusions in included content
    4. Replaces directives with resolved content
    5. Caches results to avoid redundant file reads

    Args:
        file_name: Name of the file to resolve, relative to memory-bank
            directory (e.g., "activeContext.md", "projectBrief.md")
        max_depth: Maximum nesting level for transclusions to prevent
            infinite recursion (default: 5, range: 1-10)

    Returns:
        JSON string containing original and resolved content:
        - status: "success" or "error"
        - file: Name of the resolved file
        - original_content: Original file content with transclusion directives
        - resolved_content: Fully resolved content with all transclusions expanded
        - has_transclusions: Boolean indicating if file contained any
          transclusion directives
        - cache_stats: Statistics about cache hits and misses (only if
          has_transclusions is true)
        - message: Additional information about the result (only if no
          transclusions found)
        - error: Error message (only if status is "error")
        - error_type: Type of error - "CircularDependencyError",
          "MaxDepthExceededError", or exception name

    Example (Success with transclusions):
        ```json
        {
          "status": "success",
          "file": "activeContext.md",
          "original_content": (
              "# Active Context\\n\\n{{include:techContext.md#stack}}\\n\\n"
              "Current work..."
          ),
          "resolved_content": (
              "# Active Context\\n\\n## Technology Stack\\n\\n"
              "Python 3.13+, FastAPI...\\n\\nCurrent work..."
          ),
          "has_transclusions": true,
          "cache_stats": {
            "hits": 2,
            "misses": 3,
            "size": 5
          }
        }
        ```

    Example (Success without transclusions):
        ```json
        {
          "status": "success",
          "file": "progress.md",
          "original_content": (
              "# Progress\\n\\n## Completed\\n- Feature A\\n- Feature B"
          ),
          "resolved_content": (
              "# Progress\\n\\n## Completed\\n- Feature A\\n- Feature B"
          ),
          "has_transclusions": false,
          "message": "No transclusions found in file"
        }
        ```

    Example (Error - circular dependency):
        ```json
        {
          "status": "error",
          "error": (
              "Circular dependency detected: activeContext.md -> "
              "techContext.md -> activeContext.md"
          ),
          "error_type": "CircularDependencyError",
          "message": (
              "Circular transclusion detected. Fix the circular reference "
              "and try again."
          ),
        }
        ```

    Example (Error - max depth exceeded):
        ```json
        {
          "status": "error",
          "error": "Maximum depth 5 exceeded while resolving systemPatterns.md",
          "error_type": "MaxDepthExceededError",
          "message": "Maximum transclusion depth (5) exceeded"
        }
        ```

    Note:
        - Section references use GitHub markdown header slug format
          (lowercase, hyphens for spaces)
        - Transclusions are resolved recursively, allowing nested includes
        - Circular dependencies are detected and reported as errors
        - Cache statistics include hits (reused content), misses (new reads),
          and cache size
        - Missing section references will include the entire file as fallback
        - Content is cached during resolution to optimize performance for
          repeated includes
        - Maximum depth prevents stack overflow from deeply nested or
          circular transclusions
    """
    await log_client(
        ctx, "info", "resolve_transclusions: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    return await _resolve_transclusions_run_or_error(ctx, file_name, root, max_depth)


@mcp.resource(uri="cortex://links/transclusions/{file_name}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def resolve_transclusions_resource(file_name: str) -> str:
    """Resource: Resolve transclusions for a file. Read via cortex://links/transclusions/{file_name}."""
    return await resolve_transclusions(file_name=file_name, max_depth=5)


async def _resolve_transclusions_run_or_error(
    ctx: MCPContext | None,
    file_name: str,
    root: Path,
    max_depth: int,
) -> str:
    """Run resolve_transclusions and handle errors with logging."""
    try:
        result = await execute_tool_with_stability(
            _execute_transclusion_resolution, file_name, str(root), max_depth
        )
        await log_client(
            ctx,
            "info",
            "resolve_transclusions: completed",
            logger_name=__name__,
        )
        return json.dumps(result.model_dump(), indent=2)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"resolve_transclusions: {e!s}",
            logger_name=__name__,
        )
        return resolve_transclusions_error_json(e, max_depth)


async def _execute_transclusion_resolution(
    file_name: str, root: str, max_depth: int
) -> ResolveTransclusionsResult | ResolveTransclusionsErrorResult:
    """Execute transclusion resolution workflow.

    Args:
        file_name: Name of file to resolve
        root: Project root path
        max_depth: Maximum transclusion depth

    Returns:
        Result dictionary (success or error)
    """
    root_path = Path(root)
    mgrs = await get_managers(root_path)

    file_path = await _validate_transclusion_file(mgrs, root_path, file_name)
    if isinstance(file_path, ResolveTransclusionsErrorResult):
        return file_path

    fs_manager = await get_manager(mgrs, "fs", FileSystemManager)
    link_parser = await get_manager(mgrs, "link_parser", LinkParser)
    transclusion_engine = await get_manager(mgrs, "transclusion", TransclusionEngine)

    original_content, _ = await fs_manager.read_file(file_path)

    no_transclusions_result = _check_no_transclusions(
        link_parser, file_name, original_content
    )
    if no_transclusions_result:
        return no_transclusions_result

    transclusion_engine.max_depth = max_depth
    resolved_content = await transclusion_engine.resolve_content(
        content=original_content, source_file=file_name, depth=0
    )
    cache_stats = transclusion_engine.get_cache_stats()

    return build_transclusion_success_response(
        file_name,
        original_content,
        resolved_content,
        cast(ModelDict, cache_stats),
    )


async def _validate_transclusion_file(
    mgrs: ManagersDict, root: Path, file_name: str
) -> Path | ResolveTransclusionsErrorResult:
    """Validate file for transclusion resolution.

    Args:
        mgrs: Managers dictionary
        root: Project root path
        file_name: Name of file

    Returns:
        File path or error model
    """
    fs_manager = await get_manager(mgrs, "fs", FileSystemManager)
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return ResolveTransclusionsErrorResult(
            error=f"Invalid file name: {e}",
            file=file_name,
        )

    if not file_path.exists():
        return ResolveTransclusionsErrorResult(
            error=f"File not found: {file_name}",
            file=file_name,
        )

    return file_path


def _check_no_transclusions(
    link_parser: LinkParser, file_name: str, content: str
) -> ResolveTransclusionsResult | None:
    """Check if file has transclusions, return early response if not.

    Args:
        link_parser: Link parser instance
        file_name: Name of file
        content: File content

    Returns:
        Early response model if no transclusions, None otherwise
    """
    has_transclusions = link_parser.has_transclusions(content)
    if not has_transclusions:
        return ResolveTransclusionsResult(
            file=file_name,
            original_content=content,
            resolved_content=content,
            has_transclusions=False,
            message="No transclusions found in file",
        )
    return None
