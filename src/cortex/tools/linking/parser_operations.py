"""Link parsing operations for Memory Bank files.

This module contains the parse_file_links MCP tool and its helper functions
for parsing markdown links and transclusion directives.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.linking.parser import LinkParser
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager


# Tool consolidated into query_memory_bank (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def parse_file_links(
    file_name: str,
    ctx: MCPContext | None = None,
) -> str:
    """Parse and extract all markdown links and transclusion directives
    from a Memory Bank file.

    USE WHEN: User needs to find all links in a file, user wants to extract
    transclusions, user requests link parsing, user needs to analyze file
    references.

    EXAMPLES: 'parse links in projectBrief.md', 'extract transclusions from
    activeContext.md', 'find all links in roadmap.md'.

    RETURNS: JSON with arrays of markdown links and transclusion directives
    found in the file.

    Scans the specified file for two types of links:
    - Markdown links: Standard [text](target) format for references
    - Transclusion directives: {{include:file.md}} or
      {{include:file.md#section}} for content inclusion

    Each link is extracted with its text, target, line number, and position
    information. The tool also provides a summary with counts of each link
    type and unique file references.

    Args:
        file_name: Name of the file to parse, relative to memory-bank
            directory (e.g., "activeContext.md", "systemPatterns.md")

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
        - Duplicate links to the same file are counted separately but
          counted once in unique_files
        - Line and column numbers are 1-indexed for editor compatibility
        - Relative paths in links are resolved relative to the memory-bank directory
    """
    await log_client(ctx, "info", "parse_file_links: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        return await _parse_file_links_run_or_error(ctx, file_name, str(root))
    except Exception as e:
        await log_client(
            ctx, "error", f"parse_file_links: failed: {e}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def parse_file_links_resource(file_name: str) -> str:
    """Resource: Parse links for a file. Read via cortex://links/parse/{file_name}."""
    return await parse_file_links(file_name=file_name)


async def _parse_file_links_run_or_error(
    ctx: MCPContext | None,
    file_name: str,
    project_root: str | None,
) -> str:
    """Run parse_file_links and handle validation/errors with logging."""
    try:
        result, status = await _parse_file_links_impl(file_name, project_root)
        if status == "completed":
            await log_client(
                ctx, "info", "parse_file_links: completed", logger_name=__name__
            )
        elif status == "validation_failed":
            await log_client(ctx, "warning", "parse_file_links: validation failed")
        return result
    except Exception as e:
        await log_client(
            ctx, "error", f"parse_file_links: failed: {e}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _parse_file_links_impl(
    file_name: str, project_root: str | None
) -> tuple[str, str]:
    """Run parse and return (result_json, 'completed' | 'validation_failed')."""
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    file_path, error_response = await _get_validated_file_path(mgrs, root, file_name)
    if error_response or file_path is None:
        err = error_response or json.dumps(
            {"status": "error", "error": "File path validation failed"},
            indent=2,
        )
        return (err, "validation_failed")
    parsed, summary = await _parse_file_content(mgrs, file_path)
    return (
        _build_parse_file_links_success(parsed, file_name, summary),
        "completed",
    )


def _build_parse_file_links_success(
    parsed: ModelDict, file_name: str, summary: ModelDict
) -> str:
    """Build success JSON string for parse_file_links."""
    return json.dumps(
        {
            "status": "success",
            "file": file_name,
            "markdown_links": cast(list[JsonValue], parsed.get("markdown_links", [])),
            "transclusions": cast(list[JsonValue], parsed.get("transclusions", [])),
            "summary": summary,
        },
        indent=2,
    )


async def _parse_and_count_links(
    link_parser: LinkParser, content: str
) -> tuple[ModelDict, ModelDict]:
    """Parse links and count them.

    Args:
        link_parser: Link parser instance
        content: File content to parse

    Returns:
        Tuple of (parsed result, summary dictionary)
    """
    parsed = await link_parser.parse_file(content)

    markdown_links_raw: JsonValue = parsed.get("markdown_links", [])
    transclusions_raw: JsonValue = parsed.get("transclusions", [])
    markdown_links = markdown_links_raw if isinstance(markdown_links_raw, list) else []
    transclusions = transclusions_raw if isinstance(transclusions_raw, list) else []

    unique_files: set[str] = set()
    for link in markdown_links:
        if isinstance(link, dict):
            target = link.get("target")
            if isinstance(target, str) and target:
                unique_files.add(target)
    for trans in transclusions:
        if isinstance(trans, dict):
            target = trans.get("target")
            if isinstance(target, str) and target:
                unique_files.add(target)

    summary: ModelDict = {
        "markdown_links": len(markdown_links),
        "transclusions": len(transclusions),
        "total": len(markdown_links) + len(transclusions),
        "unique_files": len(unique_files),
    }

    return parsed, summary


async def _parse_file_content(
    mgrs: ManagersDict, file_path: Path
) -> tuple[ModelDict, ModelDict]:
    """Parse file content and extract links."""
    link_parser = await get_manager(mgrs, "link_parser", LinkParser)
    fs_manager = await get_manager(mgrs, "fs", FileSystemManager)
    content, _ = await fs_manager.read_file(file_path)
    parsed, summary = await _parse_and_count_links(link_parser, content)
    return parsed, summary


async def _get_validated_file_path(
    mgrs: ManagersDict, root: Path, file_name: str
) -> tuple[Path | None, str | None]:
    """Get validated file path for parsing."""
    fs_manager = await get_manager(mgrs, "fs", FileSystemManager)
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    return _validate_and_get_file_path(fs_manager, memory_bank_dir, file_name)


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
