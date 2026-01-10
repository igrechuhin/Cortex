#!/usr/bin/env python3
"""Pre-commit hook to enforce file size limits.

This script checks that all Python files in src/cortex/ are under 400 lines
(excluding blank lines, comments, and docstrings).
"""

import sys
from pathlib import Path

MAX_LINES = 400
SRC_DIR = Path("src/cortex")


def count_lines(path: Path) -> int:
    """Count non-blank, non-comment, non-docstring lines.

    Args:
        path: Path to Python file to count

    Returns:
        Number of logical lines of code
    """
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return 0

    count = 0
    in_docstring = False

    for line in lines:
        stripped = line.strip()

        # Track docstrings
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue

        if in_docstring:
            continue

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        count += 1

    return count


def main():
    """Check all Python files for size violations."""
    # Get the project root (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / SRC_DIR

    if not src_dir.exists():
        print(f"Error: Source directory {src_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    violations = []

    for py_file in src_dir.glob("**/*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue

        lines = count_lines(py_file)
        if lines > MAX_LINES:
            violations.append((py_file, lines))

    if violations:
        print("❌ File size violations detected:", file=sys.stderr)
        print(file=sys.stderr)
        for path, lines in sorted(violations, key=lambda x: x[1], reverse=True):
            try:
                relative_path = path.relative_to(project_root)
            except ValueError:
                relative_path = path
            excess = lines - MAX_LINES
            print(
                f"  {relative_path}: {lines} lines (max: {MAX_LINES}, excess: {excess})",
                file=sys.stderr,
            )
        print(file=sys.stderr)
        print(
            f"Total violations: {len(violations)} file(s) exceed {MAX_LINES} lines",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✅ All files within size limits ({MAX_LINES} lines)")
    sys.exit(0)


if __name__ == "__main__":
    main()
