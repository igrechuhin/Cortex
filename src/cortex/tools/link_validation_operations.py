"""Link validation operations for Memory Bank files.

This module contains the validate_links MCP tool and its helper functions
for validating markdown links and transclusion directives.
"""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.link_validator import LinkValidator
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


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
        fs_manager = await get_manager(mgrs, "fs", FileSystemManager)
        memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)

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
