#!/usr/bin/env python3
"""Pre-commit hook to enforce function length limits.

This script checks that all functions in src/cortex/ are under 30 logical
lines (excluding docstrings, comments, and blank lines).
"""

import ast
import sys
from pathlib import Path

MAX_FUNCTION_LINES = 30
SRC_DIR = Path("src/cortex")


class FunctionVisitor(ast.NodeVisitor):
    """AST visitor to find and check function lengths."""

    def __init__(self, source_lines: list[str]):
        """Initialize visitor.

        Args:
            source_lines: List of source code lines
        """
        self.source_lines = source_lines
        self.violations: list[tuple[str, int, int, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit a function definition.

        Args:
            node: AST node for function definition
        """
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit an async function definition.

        Args:
            node: AST node for async function definition
        """
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """Check if function exceeds length limit.

        Args:
            node: Function node to check
        """
        start_line = node.lineno
        end_line = node.end_lineno

        if end_line is None:
            return

        # Count logical lines (excluding docstrings, comments, blank lines)
        logical_lines = 0
        docstring_start = None

        # Check if first statement is a docstring
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            # Skip the docstring lines
            docstring_start = node.body[0].lineno
            docstring_end = node.body[0].end_lineno
        else:
            docstring_end = start_line

        for line_num in range(start_line, end_line + 1):
            if line_num <= 0 or line_num > len(self.source_lines):
                continue

            line = self.source_lines[line_num - 1].strip()

            # Skip function signature line
            if line_num == start_line:
                continue

            # Skip docstring lines
            if (
                docstring_start
                and docstring_end is not None
                and docstring_start <= line_num <= docstring_end
            ):
                continue

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            logical_lines += 1

        if logical_lines > MAX_FUNCTION_LINES:
            self.violations.append((node.name, logical_lines, start_line, end_line))


def check_function_length(path: Path) -> list[tuple[str, int, int, int]]:
    """Check all functions in file for length violations.

    Args:
        path: Path to Python file to check

    Returns:
        List of violations as (function_name, logical_lines, start_line, end_line)
    """
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
            source_lines = source.split("\n")
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        print(f"Syntax error in {path}: {e}", file=sys.stderr)
        return []

    visitor = FunctionVisitor(source_lines)
    visitor.visit(tree)

    return visitor.violations


def main():
    """Check all Python files for function length violations."""
    # Get the project root (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / SRC_DIR

    if not src_dir.exists():
        print(f"Error: Source directory {src_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    all_violations: list[tuple[Path, str, int, int, int]] = []

    for py_file in src_dir.glob("**/*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue

        violations = check_function_length(py_file)
        for func_name, logical_lines, start_line, end_line in violations:
            all_violations.append(
                (py_file, func_name, logical_lines, start_line, end_line)
            )

    if all_violations:
        print("❌ Function length violations detected:", file=sys.stderr)
        print(file=sys.stderr)

        # Group by file
        by_file: dict[Path, list[tuple[str, int, int, int]]] = {}
        for path, func_name, logical_lines, start_line, end_line in all_violations:
            if path not in by_file:
                by_file[path] = []
            by_file[path].append((func_name, logical_lines, start_line, end_line))

        for path in sorted(by_file.keys()):
            try:
                relative_path = path.relative_to(project_root)
            except ValueError:
                relative_path = path
            print(f"  {relative_path}:", file=sys.stderr)
            for func_name, logical_lines, start_line, _end_line in sorted(
                by_file[path], key=lambda x: x[1], reverse=True
            ):
                excess = logical_lines - MAX_FUNCTION_LINES
                print(
                    f"    {func_name}() at line {start_line}: {logical_lines} lines "
                    + f"(max: {MAX_FUNCTION_LINES}, excess: {excess})",
                    file=sys.stderr,
                )
            print(file=sys.stderr)

        total_violations = len(all_violations)
        print(
            f"Total violations: {total_violations} function(s) exceed {MAX_FUNCTION_LINES} lines",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✅ All functions within length limits ({MAX_FUNCTION_LINES} lines)")
    sys.exit(0)


if __name__ == "__main__":
    main()
