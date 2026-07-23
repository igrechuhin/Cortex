"""Reviewable diff generation for propose_framework_optimization.

Compares each proposed change's in-memory ``new_content`` against the current
*live* file content (read-only) — the live tree is never written to, only
read, so this is safe to compute outside the isolated worktree.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
)


def _read_live_content(project_root: Path, relative_path: str) -> str:
    path = project_root / relative_path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _diff_for_change(project_root: Path, change: ProposedFileChange) -> str:
    old_content = _read_live_content(project_root, change.relative_path)
    old_lines = old_content.splitlines(keepends=True)
    new_lines = change.new_content.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{change.relative_path}",
            tofile=f"b/{change.relative_path}",
        )
    )
    if not diff_lines:
        return f"# no changes: {change.relative_path}\n"
    return "".join(diff_lines)


def build_diff_and_rationale(
    project_root: Path, changes: list[ProposedFileChange]
) -> str:
    """Build a unified-diff artifact across all proposed changes."""
    return "\n".join(_diff_for_change(project_root, change) for change in changes)
