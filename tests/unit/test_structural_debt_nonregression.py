"""Non-regression guard: src/cortex must stay within structural size limits.

Uses the same logical-line metric as the production quality gate so this
test and the gate are always in agreement.  Any new file or function that
exceeds the limits will fail here *before* a commit is attempted.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.constants import FUNCTION_LENGTH_EXCLUDED_PATHS
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_file_sizes,
    check_function_lengths_in_file,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_no_oversized_files_in_src() -> None:
    """No file under src/cortex/ may exceed MAX_FILE_LINES logical lines."""
    violations = check_file_sizes(_repo_root())
    if violations:
        lines = [
            f"  {v.file}: {v.lines} logical lines (max {v.max_lines}, excess {v.excess})"
            for v in sorted(violations, key=lambda x: -x.excess)
        ]
        raise AssertionError(
            f"{len(violations)} oversized file(s) detected:\n" + "\n".join(lines)
        )


def test_no_oversized_functions_in_src() -> None:
    """No function under src/cortex/ may exceed MAX_FUNCTION_LINES logical lines."""
    src = _repo_root() / "src" / "cortex"
    excluded = frozenset(FUNCTION_LENGTH_EXCLUDED_PATHS)
    all_violations: list[tuple[str, str, int, int]] = []

    for py_file in sorted(src.glob("**/*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        try:
            rel = py_file.relative_to(_repo_root()).as_posix()
        except ValueError:
            rel = str(py_file)
        if rel in excluded:
            continue
        for func_name, logical_lines, start_line in check_function_lengths_in_file(
            py_file
        ):
            all_violations.append((rel, func_name, start_line, logical_lines))

    if all_violations:
        lines = [
            f"  {rel}:{start_line} {func}() — {ll} logical lines"
            for rel, func, start_line, ll in sorted(all_violations, key=lambda x: -x[3])
        ]
        raise AssertionError(
            f"{len(all_violations)} oversized function(s) detected:\n"
            + "\n".join(lines)
        )
