"""Link parsing operations for Memory Bank files.

This module contains the parse_file_links MCP tool and its helper functions
for parsing markdown links and transclusion directives.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.link_parser import LinkParser
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

        memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
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
