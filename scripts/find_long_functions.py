#!/usr/bin/env python3
"""Find all functions exceeding 30 logical lines."""

import ast
import sys
from pathlib import Path

MAX_LINES = 30
SRC_DIR = Path("src/cortex")


def count_logical_lines(
    node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]
) -> int:
    """Count logical lines in a function (excluding docstrings, comments, blank lines)."""
    if node.end_lineno is None:
        return 0

    logical_lines = 0
    docstring_end = node.lineno

    # Find docstring
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    ):
        if isinstance(node.body[0].value.value, str):
            docstring_end = node.body[0].end_lineno or node.lineno

    for line_num in range(node.lineno + 1, node.end_lineno + 1):
        if line_num > len(source_lines):
            break

        line = source_lines[line_num - 1].strip()

        # Skip docstring lines
        if line_num <= docstring_end:
            continue

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        logical_lines += 1

    return logical_lines


def analyze_file(file_path: Path) -> list[tuple[str, int, int, int]]:
    """Analyze a Python file for long functions."""
    try:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()
            source_lines = source.split("\n")
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []

    violations: list[tuple[str, int, int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            logical_lines = count_logical_lines(node, source_lines)
            if logical_lines > MAX_LINES:
                lineno = node.lineno
                end_lineno = node.end_lineno if node.end_lineno is not None else 0
                violations.append((node.name, logical_lines, lineno, end_lineno))

    return violations


def main():
    """Find all functions exceeding 30 logical lines."""
    all_violations: list[tuple[Path, str, int, int, int]] = []

    for py_file in sorted(SRC_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue

        violations = analyze_file(py_file)
        for func_name, logical_lines, start_line, end_line in violations:
            all_violations.append(
                (py_file, func_name, logical_lines, start_line, end_line)
            )

    # Sort by excess lines (descending)
    all_violations.sort(key=lambda x: x[2] - MAX_LINES, reverse=True)

    print(
        f"Found {len(all_violations)} functions exceeding {MAX_LINES} logical lines:\n"
    )

    project_root = Path.cwd()
    for file_path, func_name, logical_lines, start_line, _end_line in all_violations:
        excess = logical_lines - MAX_LINES
        try:
            relative_path = file_path.relative_to(project_root)
        except ValueError:
            relative_path = file_path
        print(
            f"{relative_path}:{start_line} {func_name}() - {logical_lines} lines (excess: {excess})"
        )

    return len(all_violations)


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count == 0 else 1)
