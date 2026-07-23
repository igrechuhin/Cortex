"""Apply proposed file changes inside an isolated worktree only."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.optimization.propose_framework_optimization_allowlist import (
    resolve_in_worktree,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
)


def apply_changes_to_worktree(
    worktree_root: Path, changes: list[ProposedFileChange]
) -> list[Path]:
    """Validate every target path, then write all changes.

    All paths are resolved (and allowlist-validated) up front so a single bad
    path rejects the whole batch before any file in the batch is written.
    """
    targets = [resolve_in_worktree(worktree_root, c.relative_path) for c in changes]
    for target, change in zip(targets, changes, strict=True):
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(change.new_content, encoding="utf-8")
    return targets
