#!/usr/bin/env python3
"""Analyze function lengths to identify violations of 30-line limit.

This script performs AST-based analysis to find functions exceeding 30 logical lines.
Logical lines exclude:
- Blank lines
- Comment-only lines
- Docstrings
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FunctionViolation:
    """Function that violates the 30-line limit."""

    file_path: str
    function_name: str
    start_line: int
    end_line: int
    logical_lines: int
    over_limit: int


def count_logical_lines(
    node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]
) -> int:
    """Count logical lines in a function, excluding blanks, comments, and docstrings.

    Args:
        node: Function AST node
        source_lines: List of source code lines

    Returns:
        Number of logical lines
    """
    start = node.lineno - 1  # Convert to 0-indexed
    end = node.end_lineno if node.end_lineno else start + 1

    # Skip docstring if present
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        # Skip past docstring
        if node.body[0].end_lineno:
            start = node.body[0].end_lineno

    logical_count = 0
    for line_num in range(start, end):
        if line_num >= len(source_lines):
            break

        line = source_lines[line_num].strip()

        # Skip blank lines
        if not line:
            continue

        # Skip comment-only lines
        if line.startswith("#"):
            continue

        logical_count += 1

    return logical_count


def analyze_file(file_path: Path, project_root: Path) -> list[FunctionViolation]:
    """Analyze a Python file for function length violations.

    Args:
        file_path: Path to Python file
        project_root: Path to project root

    Returns:
        List of function violations
    """
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
        source_lines = source.splitlines()
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return []

    violations: list[FunctionViolation] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip if no line info
        if not node.lineno or not node.end_lineno:
            continue

        logical_lines = count_logical_lines(node, source_lines)

        if logical_lines > 30:
            violations.append(
                FunctionViolation(
                    file_path=str(file_path.relative_to(project_root)),
                    function_name=node.name,
                    start_line=node.lineno,
                    end_line=node.end_lineno,
                    logical_lines=logical_lines,
                    over_limit=logical_lines - 30,
                )
            )

    return violations


def main() -> int:
    """Main entry point."""
    # Get absolute path to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src" / "cortex"

    if not src_dir.exists():
        print(f"Error: {src_dir} not found", file=sys.stderr)
        return 1

    # Collect all violations
    all_violations: list[FunctionViolation] = []

    for py_file in src_dir.rglob("*.py"):
        # Skip __init__.py files
        if py_file.name == "__init__.py":
            continue

        violations = analyze_file(py_file, project_root)
        all_violations.extend(violations)

    # Sort by severity (most over limit first)
    all_violations.sort(key=lambda v: v.over_limit, reverse=True)

    # Print report
    print("# Function Length Violations Report")
    print()
    print(f"**Total Violations:** {len(all_violations)}")
    print(f"**Files Affected:** {len(set(v.file_path for v in all_violations))}")
    print()
    print("## Top 50 Violations (by severity)")
    print()
    print("| # | File | Function | Lines | Over Limit | Location |")
    print("|---|------|----------|-------|------------|----------|")

    for idx, v in enumerate(all_violations[:50], 1):
        file_name = Path(v.file_path).name
        severity = "🔴" if v.over_limit > 50 else "🟠" if v.over_limit > 20 else "🟡"
        print(
            f"| {idx} | {file_name} | `{v.function_name}` | "
            + f"{v.logical_lines} | +{v.over_limit} {severity} | "
            + f"{v.file_path}:{v.start_line} |"
        )

    print()
    print("## Summary by File")
    print()

    # Group by file
    violations_by_file: dict[str, list[FunctionViolation]] = {}
    for v in all_violations:
        violations_by_file.setdefault(v.file_path, []).append(v)

    # Sort files by number of violations
    sorted_files = sorted(
        violations_by_file.items(), key=lambda x: len(x[1]), reverse=True
    )

    print("| File | Violations | Total Over Limit |")
    print("|------|------------|------------------|")

    for file_path, violations in sorted_files[:30]:
        file_name = Path(file_path).name
        total_over = sum(v.over_limit for v in violations)
        print(f"| {file_name} | {len(violations)} | +{total_over} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())
