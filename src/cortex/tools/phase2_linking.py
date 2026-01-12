"""
Phase 2: Link Management Tools

This module contains tools for parsing, resolving, and validating
markdown links and transclusions within Memory Bank files.

Total: 4 tools
- parse_file_links
- resolve_transclusions
- validate_links
- get_link_graph
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import execute_tool_with_stability
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
    TransclusionEngine,
)
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


@mcp.tool()
async def parse_file_links(file_name: str, project_root: str | None = None) -> str:
    """Parse and extract all markdown links and transclusion directives from a Memory Bank file.

    Scans the specified file for two types of links:
    - Markdown links: Standard [text](target) format for references
    - Transclusion directives: {{include:file.md}} or {{include:file.md#section}} for content inclusion

    Each link is extracted with its text, target, line number, and position information.
    The tool also provides a summary with counts of each link type and unique file references.

    Args:
        file_name: Name of the file to parse, relative to memory-bank directory (e.g., "activeContext.md", "systemPatterns.md")
        project_root: Optional absolute path to project root directory; if None, uses current working directory

    Returns:
        JSON string containing parsed links and summary statistics:
        - status: "success" or "error"
        - file: Name of the parsed file
        - markdown_links: List of markdown link objects with text, target, line, column
        - transclusions: List of transclusion objects with target, line, column
        - summary: Statistics including counts and unique file references
        - error: Error message (only if status is "error")
        - error_type: Type of error that occurred (only if status is "error")

    Example (Success with links):
        ```json
        {
          "status": "success",
          "file": "activeContext.md",
          "markdown_links": [
            {
              "text": "System Patterns",
              "target": "systemPatterns.md",
              "line": 10,
              "column": 5
            },
            {
              "text": "API Documentation",
              "target": "docs/api.md#endpoints",
              "line": 15,
              "column": 8
            }
          ],
          "transclusions": [
            {
              "target": "techContext.md",
              "line": 25,
              "column": 1
            },
            {
              "target": "productContext.md#overview",
              "line": 30,
              "column": 1
            }
          ],
          "summary": {
            "markdown_links": 2,
            "transclusions": 2,
            "total": 4,
            "unique_files": 4
          }
        }
        ```

    Example (Success with no links):
        ```json
        {
          "status": "success",
          "file": "progress.md",
          "markdown_links": [],
          "transclusions": [],
          "summary": {
            "markdown_links": 0,
            "transclusions": 0,
            "total": 0,
            "unique_files": 0
          }
        }
        ```

    Example (Error - file not found):
        ```json
        {
          "status": "error",
          "error": "File not found: nonexistent.md"
        }
        ```

    Note:
        - Transclusions can reference specific sections using #section-name syntax
        - Section anchors in transclusions follow GitHub markdown header slug format
        - Duplicate links to the same file are counted separately but counted once in unique_files
        - Line and column numbers are 1-indexed for editor compatibility
        - Relative paths in links are resolved relative to the memory-bank directory
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        fs_manager = cast(FileSystemManager, mgrs["fs"])
        link_parser = await get_manager(mgrs, "link_parser", LinkParser)

        memory_bank_dir = root / "memory-bank"
        file_path, error_response = _validate_and_get_file_path(
            fs_manager, memory_bank_dir, file_name
        )
        if error_response or file_path is None:
            return error_response or json.dumps(
                {"status": "error", "error": "File path validation failed"}, indent=2
            )

        content, _ = await fs_manager.read_file(file_path)
        parsed, summary = await _parse_and_count_links(link_parser, content)

        return json.dumps(
            {
                "status": "success",
                "file": file_name,
                "markdown_links": parsed["markdown_links"],
                "transclusions": parsed["transclusions"],
                "summary": summary,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _parse_and_count_links(
    link_parser: LinkParser, content: str
) -> tuple[dict[str, object], dict[str, int]]:
    """Parse links and count them.

    Args:
        link_parser: Link parser instance
        content: File content to parse

    Returns:
        Tuple of (parsed result, summary dictionary)
    """
    parsed = await link_parser.parse_file(content)
    markdown_links: list[dict[str, object]] = parsed.get("markdown_links", [])
    transclusions: list[dict[str, object]] = parsed.get("transclusions", [])

    unique_files: set[str] = set()
    for link in markdown_links:
        target = link.get("target", "")
        if isinstance(target, str) and target:
            unique_files.add(target)
    for trans in transclusions:
        target = trans.get("target", "")
        if isinstance(target, str) and target:
            unique_files.add(target)

    summary = {
        "markdown_links": len(markdown_links),
        "transclusions": len(transclusions),
        "total": len(markdown_links) + len(transclusions),
        "unique_files": len(unique_files),
    }

    return cast(dict[str, object], parsed), summary


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
    memory_bank_dir = root / "memory-bank"
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


@mcp.tool()
async def validate_links(
    file_name: str | None = None, project_root: str | None = None
) -> str:
    """Validate all markdown links and transclusion directives to ensure they point to existing targets.

    Performs comprehensive link validation by checking:
    - Target files exist in the memory-bank directory or project
    - Referenced sections exist in target markdown files
    - Transclusion directives use correct syntax
    - Links are not broken by file moves or deletions

    Can validate a single file or all files in the memory-bank directory. For each broken link,
    provides detailed error information including the source location, target, and suggested fixes.

    Args:
        file_name: Optional specific file to validate relative to memory-bank directory (e.g., "activeContext.md"); if None, validates all files in memory-bank
        project_root: Optional absolute path to project root directory; if None, uses current working directory

    Returns:
        JSON string containing validation results and detailed error reports:
        - status: "success" or "error"
        - mode: "single_file" or "all_files" indicating validation scope
        - files_checked: Number of files validated
        - total_links: Total number of links found
        - valid_links: Number of links that passed validation
        - broken_links: Number of links with errors
        - warnings: Number of non-critical issues found
        - validation_errors: List of broken link objects with file, line, target, error details
        - validation_warnings: List of warning objects with file, line, target, warning details
        - report: Human-readable summary report (only in all_files mode)
        - error: Error message (only if status is "error")
        - error_type: Type of error that occurred (only if status is "error")

    Example (Success - single file with issues):
        ```json
        {
          "status": "success",
          "mode": "single_file",
          "files_checked": 1,
          "total_links": 8,
          "valid_links": 6,
          "broken_links": 2,
          "warnings": 0,
          "validation_errors": [
            {
              "file": "activeContext.md",
              "line": 15,
              "link_type": "markdown",
              "target": "docs/missing.md",
              "error": "Target file does not exist",
              "suggestion": "Check if file was moved or renamed"
            },
            {
              "file": "activeContext.md",
              "line": 23,
              "link_type": "transclusion",
              "target": "techContext.md#nonexistent-section",
              "error": "Section 'nonexistent-section' not found in target file",
              "suggestion": "Available sections: stack, dependencies, architecture"
            }
          ],
          "validation_warnings": []
        }
        ```

    Example (Success - all files):
        ```json
        {
          "status": "success",
          "mode": "all_files",
          "files_checked": 7,
          "total_links": 45,
          "valid_links": 42,
          "broken_links": 3,
          "warnings": 2,
          "validation_errors": [
            {
              "file": "systemPatterns.md",
              "line": 30,
              "link_type": "transclusion",
              "target": "deleted.md",
              "error": "Target file does not exist",
              "suggestion": "Remove transclusion or restore file"
            }
          ],
          "validation_warnings": [
            {
              "file": "productContext.md",
              "line": 12,
              "link_type": "markdown",
              "target": "external-link.md",
              "warning": "External link may become stale",
              "suggestion": "Consider using transclusion for internal content"
            }
          ],
          "report": "Link Validation Report\\n===================\\n\\nFiles checked: 7\\nTotal links: 45\\nValid: 42 (93%)\\nBroken: 3 (7%)\\n\\nFiles with errors:\\n- systemPatterns.md: 3 errors\\n"
        }
        ```

    Example (Success - no issues):
        ```json
        {
          "status": "success",
          "mode": "all_files",
          "files_checked": 7,
          "total_links": 45,
          "valid_links": 45,
          "broken_links": 0,
          "warnings": 0,
          "validation_errors": [],
          "validation_warnings": [],
          "report": "Link Validation Report\\n===================\\n\\nAll links valid! ✓\\n\\nFiles checked: 7\\nTotal links: 45"
        }
        ```

    Example (Error - file not found):
        ```json
        {
          "status": "error",
          "error": "File not found: nonexistent.md"
        }
        ```

    Note:
        - Validation checks both file existence and section existence for section links
        - Section references are case-sensitive and use GitHub markdown slug format
        - Warnings are non-critical issues that don't break links but may need attention
        - Suggestions provide actionable guidance for fixing broken links
        - All file paths in errors are relative to memory-bank directory
        - External URLs in markdown links are not validated (only local file links)
        - The report in all_files mode provides a summary suitable for display to users
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        link_validator = await get_manager(mgrs, "link_validator", LinkValidator)
        fs_manager = cast(FileSystemManager, mgrs["fs"])
        memory_bank_dir = root / "memory-bank"

        if file_name:
            return await _validate_single_file(
                file_name, fs_manager, link_validator, memory_bank_dir
            )
        return await _validate_all_files(link_validator, memory_bank_dir)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def get_link_graph(
    project_root: str | None = None,
    include_transclusions: bool = True,
    format: str = "json",
) -> str:
    """Build and return a dependency graph showing how Memory Bank files reference each other through links.

    Analyzes all Memory Bank files to construct a directed graph where:
    - Nodes represent files in the memory-bank directory
    - Edges represent links between files (markdown links and/or transclusions)
    - Edge types distinguish between reference links and transclusion dependencies

    The graph includes cycle detection to identify circular dependencies that could cause
    issues during transclusion resolution. Can output in JSON format for programmatic use
    or Mermaid diagram format for visualization.

    Args:
        project_root: Optional absolute path to project root directory; if None, uses current working directory
        include_transclusions: Whether to include transclusion links in the graph (default: True); if False, only markdown reference links are included
        format: Output format - "json" for structured data or "mermaid" for diagram syntax (default: "json")

    Returns:
        JSON string containing link graph in requested format:
        - status: "success" or "error"
        - format: "json" or "mermaid" indicating output format
        - nodes: List of file nodes with metadata (only in JSON format)
        - edges: List of edges with source, target, type, and metadata (only in JSON format)
        - cycles: List of detected circular dependency paths
        - summary: Statistics about graph structure (only in JSON format)
        - diagram: Mermaid diagram syntax string (only in Mermaid format)
        - error: Error message (only if status is "error")
        - error_type: Type of error that occurred (only if status is "error")

    Example (JSON format with cycles):
        ```json
        {
          "status": "success",
          "format": "json",
          "nodes": [
            {
              "id": "activeContext.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "systemPatterns.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "techContext.md",
              "type": "file",
              "exists": true
            }
          ],
          "edges": [
            {
              "source": "activeContext.md",
              "target": "systemPatterns.md",
              "type": "reference",
              "line": 15
            },
            {
              "source": "activeContext.md",
              "target": "techContext.md",
              "type": "transclusion",
              "line": 25
            },
            {
              "source": "systemPatterns.md",
              "target": "techContext.md",
              "type": "reference",
              "line": 42
            }
          ],
          "cycles": [
            [
              "productContext.md",
              "activeContext.md",
              "productContext.md"
            ]
          ],
          "summary": {
            "total_files": 7,
            "total_links": 23,
            "reference_links": 15,
            "transclusion_links": 8,
            "has_cycles": true,
            "cycle_count": 1
          }
        }
        ```

    Example (JSON format without transclusions):
        ```json
        {
          "status": "success",
          "format": "json",
          "nodes": [
            {
              "id": "activeContext.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "systemPatterns.md",
              "type": "file",
              "exists": true
            }
          ],
          "edges": [
            {
              "source": "activeContext.md",
              "target": "systemPatterns.md",
              "type": "reference",
              "line": 15
            }
          ],
          "cycles": [],
          "summary": {
            "total_files": 7,
            "total_links": 15,
            "reference_links": 15,
            "transclusion_links": 0,
            "has_cycles": false,
            "cycle_count": 0
          }
        }
        ```

    Example (Mermaid format):
        ```json
        {
          "status": "success",
          "format": "mermaid",
          "diagram": "graph TD\\n  activeContext[activeContext.md]\\n  systemPatterns[systemPatterns.md]\\n  techContext[techContext.md]\\n  activeContext -->|reference| systemPatterns\\n  activeContext -.->|transclusion| techContext\\n  systemPatterns -->|reference| techContext\\n  style activeContext fill:#e1f5ff\\n  style systemPatterns fill:#e1f5ff\\n  style techContext fill:#e1f5ff",
          "cycles": []
        }
        ```

    Example (Error):
        ```json
        {
          "status": "error",
          "error": "Failed to parse links in systemPatterns.md: Invalid syntax",
          "error_type": "ParseError"
        }
        ```

    Note:
        - Cycles indicate circular dependencies that will cause transclusion resolution to fail
        - Reference links (markdown links) are shown with solid arrows in Mermaid diagrams
        - Transclusion links are shown with dashed arrows in Mermaid diagrams
        - The graph only includes files that exist in the memory-bank directory
        - Nodes include an 'exists' flag to identify broken links to non-existent files
        - Edge line numbers indicate where in the source file the link appears
        - Setting include_transclusions=False is useful for analyzing reference structure only
        - The summary includes has_cycles and cycle_count for quick cycle detection
    """
    try:
        link_graph, cycles = await _build_link_graph_data(project_root)

        if format == "mermaid":
            return _generate_mermaid_response(link_graph, cycles)

        return _generate_json_response(link_graph, cycles, include_transclusions)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _build_link_graph_data(
    project_root: str | None,
) -> tuple[DependencyGraph, list[list[str]]]:
    """Build link graph and detect cycles.

    Args:
        project_root: Optional path to project root

    Returns:
        Tuple of (link_graph, cycles)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)

    memory_bank_dir = root / "memory-bank"
    link_parser = cast(LinkParser, mgrs["link_parser"])
    link_graph = cast(DependencyGraph, mgrs["graph"])

    await link_graph.build_from_links(memory_bank_dir, link_parser)
    cycles = link_graph.detect_cycles()

    return link_graph, cycles


def _generate_mermaid_response(
    link_graph: DependencyGraph, cycles: list[list[str]]
) -> str:
    """Generate mermaid format response.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles

    Returns:
        JSON string with mermaid diagram
    """
    mermaid = link_graph.to_mermaid()

    return json.dumps(
        {
            "status": "success",
            "format": "mermaid",
            "diagram": mermaid,
            "cycles": cycles,
        },
        indent=2,
    )


def _calculate_link_summary(
    link_graph: DependencyGraph, cycles: list[list[str]]
) -> dict[str, int | bool]:
    """Calculate link summary statistics.

    Reduced nesting: Extracted link counting to helper function.
    Nesting: 2 levels (down from 5 levels)

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles

    Returns:
        Summary dictionary
    """
    reference_links, transclusion_links = _count_links_by_type(link_graph)

    return {
        "total_files": len(link_graph.get_all_files()),
        "total_links": reference_links + transclusion_links,
        "reference_links": reference_links,
        "transclusion_links": transclusion_links,
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
    }


def _count_links_by_type(link_graph: DependencyGraph) -> tuple[int, int]:
    """Count reference and transclusion links in the graph.

    Args:
        link_graph: Dependency graph instance

    Returns:
        Tuple of (reference_count, transclusion_count)
    """
    reference_links = 0
    transclusion_links = 0

    for source_file in link_graph.get_all_files():
        if source_file in link_graph.link_types:
            for _target, link_type in link_graph.link_types[source_file].items():
                if link_type == "reference":
                    reference_links += 1
                elif link_type == "transclusion":
                    transclusion_links += 1

    return reference_links, transclusion_links


def _generate_json_response(
    link_graph: DependencyGraph,
    cycles: list[list[str]],
    include_transclusions: bool,
) -> str:
    """Generate JSON format response.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles
        include_transclusions: Whether to include transclusion links

    Returns:
        JSON string with graph data
    """
    if include_transclusions:
        graph_data = link_graph.to_dict()
    else:
        graph_data = link_graph.get_reference_graph()

    summary = _calculate_link_summary(link_graph, cycles)

    return json.dumps(
        {
            "status": "success",
            "format": "json",
            **graph_data,
            "cycles": cycles,
            "summary": summary,
        },
        indent=2,
    )


async def _validate_single_file(
    file_name: str,
    fs_manager: FileSystemManager,
    link_validator: LinkValidator,
    memory_bank_dir: Path,
) -> str:
    """Validate links in a single file.

    Args:
        file_name: Name of file to validate
        fs_manager: File system manager
        link_validator: Link validator instance
        memory_bank_dir: Memory bank directory

    Returns:
        JSON string with validation results
    """
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"},
            indent=2,
        )

    if not file_path.exists():
        return json.dumps(
            {"status": "error", "error": f"File not found: {file_name}"},
            indent=2,
        )

    validation_result = await link_validator.validate_file(file_path)
    return json.dumps(
        {"status": "success", "mode": "single_file", **validation_result},
        indent=2,
    )


async def _validate_all_files(
    link_validator: LinkValidator, memory_bank_dir: Path
) -> str:
    """Validate links in all files.

    Args:
        link_validator: Link validator instance
        memory_bank_dir: Memory bank directory

    Returns:
        JSON string with validation results
    """
    validation_result = await link_validator.validate_all(memory_bank_dir)
    report = link_validator.generate_report(validation_result)

    return json.dumps(
        {
            "status": "success",
            "mode": "all_files",
            **validation_result,
            "report": report,
        },
        indent=2,
    )


def _validate_and_get_file_path(
    fs_manager: FileSystemManager, memory_bank_dir: Path, file_name: str
) -> tuple[Path | None, str | None]:
    """Validate file name and get file path.

    Args:
        fs_manager: File system manager instance
        memory_bank_dir: Memory bank directory path
        file_name: File name to validate

    Returns:
        Tuple of (file_path, error_response). error_response is None if valid.
    """
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return None, json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )

    if not file_path.exists():
        return None, json.dumps(
            {"status": "error", "error": f"File not found: {file_name}"}, indent=2
        )

    return file_path, None
