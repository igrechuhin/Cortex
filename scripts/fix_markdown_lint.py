#!/usr/bin/env python3
"""
Markdown Lint Fix Tool (CLI Wrapper).

CLI wrapper for the fix_markdown_lint MCP tool.
Automatically scans modified markdown files in the working copy,
detects markdownlint errors, and fixes them automatically.

This script is a thin CLI wrapper around the MCP tool implementation
in src/cortex/tools/markdown_operations.py.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the MCP tool function
# Note: This is a CLI wrapper - agents should use the MCP tool directly
try:
    from cortex.tools.markdown_operations import fix_markdown_lint
except ImportError as e:
    print(
        f"Error: Failed to import MCP tool. This script requires the Cortex package to be installed.\n{e}",
        file=sys.stderr,
    )
    sys.exit(1)


async def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    parser = argparse.ArgumentParser(
        description="Fix markdownlint errors in modified markdown files"
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for errors without fixing them",
    )
    _ = parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Include untracked markdown files",
    )
    _ = parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all markdown files in project, not just modified ones",
    )
    _ = parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    _ = parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    # Call MCP tool function
    project_root_str = str(args.project_root) if args.project_root else None
    result_json = await fix_markdown_lint(
        project_root=project_root_str,
        include_untracked=args.include_untracked,
        dry_run=args.dry_run,
        check_all_files=args.check_all,
    )

    # Parse result
    result = json.loads(result_json)

    # Output results
    if args.json:
        print(result_json)
    else:
        if result.get("error_message"):
            print(f"Error: {result['error_message']}", file=sys.stderr)
        else:
            files_processed = result.get("files_processed", 0)
            files_fixed = result.get("files_fixed", 0)
            files_unchanged = result.get("files_unchanged", 0)
            files_with_errors = result.get("files_with_errors", 0)

            if files_processed == 0:
                print("No modified markdown files found.")
            else:
                print(f"\nProcessed {files_processed} markdown file(s):")
                print(f"  Fixed: {files_fixed}")
                print(f"  Unchanged: {files_unchanged}")
                print(f"  Errors: {files_with_errors}")

                results_list = result.get("results", [])
                if files_fixed > 0:
                    print("\nFixed files:")
                    for r in results_list:
                        if r.get("fixed"):
                            print(f"  - {r.get('file', 'unknown')}")

                if files_with_errors > 0:
                    print("\nFiles with errors:")
                    for r in results_list:
                        if r.get("error_message"):
                            print(
                                f"  - {r.get('file', 'unknown')}: {r.get('error_message')}"
                            )

    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
