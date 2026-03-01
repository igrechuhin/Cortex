"""File size and function length quality checks.

Extracted from pre_commit_helpers to keep modules under 400 lines.
"""

import ast
from pathlib import Path

from cortex.core.constants import (
    FILE_SIZE_EXCLUDED_FILENAMES,
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
)
from cortex.tools.execution.pre_commit_helpers_models import FileSizeViolation


def get_docstring_range(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[int, int] | None:
    """Get docstring line range if function has a docstring."""
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        start = node.body[0].lineno
        end = node.body[0].end_lineno
        if end is not None:
            return (start, end)
    return None


class _FunctionVisitor(ast.NodeVisitor):
    """AST visitor to find and check function lengths."""

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.violations: list[tuple[str, int, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        start_line = node.lineno
        end_line = node.end_lineno
        if end_line is None:
            return
        docstring_range = get_docstring_range(node)
        logical_lines = self._count_logical_lines(start_line, end_line, docstring_range)
        if logical_lines > MAX_FUNCTION_LINES:
            self.violations.append((node.name, logical_lines, start_line))

    def _count_logical_lines(
        self,
        start_line: int,
        end_line: int,
        docstring_range: tuple[int, int] | None,
    ) -> int:
        logical_lines = 0
        for line_num in range(start_line, end_line + 1):
            if self._should_skip_line(line_num, start_line, docstring_range):
                continue
            logical_lines += 1
        return logical_lines

    def _should_skip_line(
        self,
        line_num: int,
        start_line: int,
        docstring_range: tuple[int, int] | None,
    ) -> bool:
        if line_num <= 0 or line_num > len(self.source_lines):
            return True
        line = self.source_lines[line_num - 1].strip()
        if line_num == start_line:
            return True
        if docstring_range and docstring_range[0] <= line_num <= docstring_range[1]:
            return True
        if not line or line.startswith("#"):
            return True
        return False


def check_function_lengths_in_file(path: Path) -> list[tuple[str, int, int]]:
    """Check all functions in file for length violations."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
            source_lines = source.split("\n")
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    visitor = _FunctionVisitor(source_lines)
    visitor.visit(tree)
    return visitor.violations


def count_file_lines(path: Path) -> int:
    """Count non-blank, non-comment, non-docstring lines in a file."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return 0

    count = 0
    in_docstring = False

    for line in lines:
        stripped = line.strip()
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        count += 1

    return count


def check_file_sizes(
    project_root: Path,
    max_lines: int | None = None,
) -> list[FileSizeViolation]:
    """Check all Python files under src for size violations."""
    if max_lines is None:
        max_lines = MAX_FILE_LINES
    violations: list[FileSizeViolation] = []
    src_dir = project_root / "src"
    excluded_files = frozenset(FILE_SIZE_EXCLUDED_FILENAMES)

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        if py_file.name in excluded_files:
            continue
        lines = count_file_lines(py_file)
        if lines > max_lines:
            try:
                relative_path = str(py_file.relative_to(project_root))
            except ValueError:
                relative_path = str(py_file)
            violations.append(
                FileSizeViolation(
                    file=relative_path,
                    lines=lines,
                    max_lines=max_lines,
                    excess=lines - max_lines,
                )
            )

    return violations
