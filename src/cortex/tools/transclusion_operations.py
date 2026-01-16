"""Transclusion resolution operations for Memory Bank files.

This module contains the resolve_transclusions MCP tool and its helper functions
for resolving {{include:}} transclusion directives.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import execute_tool_with_stability
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
    TransclusionEngine,
)
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


@mcp.tool()
async def resolve_transclusions(
    file_name: str, project_root: str | None = None, max_depth: int = 5
) -> str:
    """Resolve all {{include:}} transclusion directives in a file by replacing them with actual content.

    Reads the specified file and recursively resolves all transclusion directives by replacing
    them with the actual content from referenced files. Supports nested transclusions where
    included files can themselves contain transclusion directives.

    The resolution process:
    1. Parses file for {{include:file.md}} or {{include:file.md#section}} directives
    2. Loads referenced content (entire file or specific section)
    3. Recursively resolves transclusions in included content
    4. Replaces directives with resolved content
    5. Caches results to avoid redundant file reads

    Args:
        file_name: Name of the file to resolve, relative to memory-bank directory (e.g., "activeContext.md", "projectBrief.md")
        project_root: Optional absolute path to project root directory; if None, uses current working directory
        max_depth: Maximum nesting level for transclusions to prevent infinite recursion (default: 5, range: 1-10)

    Returns:
        JSON string containing original and resolved content:
        - status: "success" or "error"
        - file: Name of the resolved file
        - original_content: Original file content with transclusion directives
        - resolved_content: Fully resolved content with all transclusions expanded
        - has_transclusions: Boolean indicating if file contained any transclusion directives
        - cache_stats: Statistics about cache hits and misses (only if has_transclusions is true)
        - message: Additional information about the result (only if no transclusions found)
        - error: Error message (only if status is "error")
        - error_type: Type of error - "CircularDependencyError", "MaxDepthExceededError", or exception name

    Example (Success with transclusions):
        ```json
        {
          "status": "success",
          "file": "activeContext.md",
          "original_content": "# Active Context\\n\\n{{include:techContext.md#stack}}\\n\\nCurrent work...",
          "resolved_content": "# Active Context\\n\\n## Technology Stack\\n\\nPython 3.13+, FastAPI...\\n\\nCurrent work...",
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
          "original_content": "# Progress\\n\\n## Completed\\n- Feature A\\n- Feature B",
          "resolved_content": "# Progress\\n\\n## Completed\\n- Feature A\\n- Feature B",
          "has_transclusions": false,
          "message": "No transclusions found in file"
        }
        ```

    Example (Error - circular dependency):
        ```json
        {
          "status": "error",
          "error": "Circular dependency detected: activeContext.md -> techContext.md -> activeContext.md",
          "error_type": "CircularDependencyError",
          "message": "Circular transclusion detected. Fix the circular reference and try again."
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
        - Section references use GitHub markdown header slug format (lowercase, hyphens for spaces)
        - Transclusions are resolved recursively, allowing nested includes
        - Circular dependencies are detected and reported as errors
        - Cache statistics include hits (reused content), misses (new reads), and cache size
        - Missing section references will include the entire file as fallback
        - Content is cached during resolution to optimize performance for repeated includes
        - Maximum depth prevents stack overflow from deeply nested or circular transclusions
    """
    try:
        result = await execute_tool_with_stability(
            _execute_transclusion_resolution, file_name, project_root, max_depth
        )
        return json.dumps(result, indent=2)
    except CircularDependencyError as e:
        return json.dumps(_build_circular_dependency_error(str(e)), indent=2)
    except MaxDepthExceededError as e:
        return json.dumps(_build_max_depth_error(str(e), max_depth), indent=2)
    except Exception as e:
        return json.dumps(_build_transclusion_error(str(e), type(e).__name__), indent=2)


async def _execute_transclusion_resolution(
    file_name: str, project_root: str | None, max_depth: int
) -> dict[str, object]:
    """Execute transclusion resolution workflow.

    Args:
        file_name: Name of file to resolve
        project_root: Optional project root path
        max_depth: Maximum transclusion depth

    Returns:
        Result dictionary (success or error)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)

    file_path = await _validate_transclusion_file(mgrs, root, file_name)
    if isinstance(file_path, dict):
        return cast(dict[str, object], file_path)

    fs_manager = cast(FileSystemManager, mgrs["fs"])
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

    return _build_transclusion_success_response(
        file_name,
        original_content,
        resolved_content,
        cast(dict[str, object], cache_stats),
    )


async def _validate_transclusion_file(
    mgrs: dict[str, object], root: Path, file_name: str
) -> Path | dict[str, str]:
    """Validate file for transclusion resolution.

    Args:
        mgrs: Managers dictionary
        root: Project root path
        file_name: Name of file

    Returns:
        File path or error dict
    """
    fs_manager = cast(FileSystemManager, mgrs["fs"])
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return {"status": "error", "error": f"Invalid file name: {e}"}

    if not file_path.exists():
        return {"status": "error", "error": f"File not found: {file_name}"}

    return file_path


def _check_no_transclusions(
    link_parser: LinkParser, file_name: str, content: str
) -> dict[str, object] | None:
    """Check if file has transclusions, return early response if not.

    Args:
        link_parser: Link parser instance
        file_name: Name of file
        content: File content

    Returns:
        Early response dict if no transclusions, None otherwise
    """
    has_transclusions = link_parser.has_transclusions(content)
    if not has_transclusions:
        return {
            "status": "success",
            "file": file_name,
            "original_content": content,
            "resolved_content": content,
            "has_transclusions": False,
            "message": "No transclusions found in file",
        }
    return None


def _build_transclusion_success_response(
    file_name: str,
    original_content: str,
    resolved_content: str,
    cache_stats: dict[str, object],
) -> dict[str, object]:
    """Build success response for transclusion resolution.

    Args:
        file_name: Name of file
        original_content: Original file content
        resolved_content: Resolved content with transclusions
        cache_stats: Cache statistics

    Returns:
        Success response dict
    """
    return {
        "status": "success",
        "file": file_name,
        "original_content": original_content,
        "resolved_content": resolved_content,
        "has_transclusions": True,
        "cache_stats": cache_stats,
    }


def _build_circular_dependency_error(error_message: str) -> dict[str, object]:
    """Build error response for circular dependency.

    Args:
        error_message: Error message

    Returns:
        Error response dict
    """
    return {
        "status": "error",
        "error": error_message,
        "error_type": "CircularDependencyError",
        "message": "Circular transclusion detected. Fix the circular reference and try again.",
    }


def _build_max_depth_error(error_message: str, max_depth: int) -> dict[str, object]:
    """Build error response for max depth exceeded.

    Args:
        error_message: Error message
        max_depth: Maximum depth that was exceeded

    Returns:
        Error response dict
    """
    return {
        "status": "error",
        "error": error_message,
        "error_type": "MaxDepthExceededError",
        "message": f"Maximum transclusion depth ({max_depth}) exceeded",
    }


def _build_transclusion_error(error_message: str, error_type: str) -> dict[str, object]:
    """Build error response for general transclusion errors.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response dict
    """
    return {"status": "error", "error": error_message, "error_type": error_type}
