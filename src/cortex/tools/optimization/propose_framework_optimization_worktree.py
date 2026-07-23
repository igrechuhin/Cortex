"""Isolated git worktree lifecycle for propose_framework_optimization.

Reuses the existing :mod:`cortex.core.execution_env` abstraction (no new
worktree mechanism): worktree creation/removal runs ``git worktree`` via the
injected :class:`~cortex.core.execution_env.ExecutionEnvironment`, and
:class:`~cortex.core.execution_env.WorktreeExecutionEnvironment` is available
for any command that must execute scoped to the created worktree path.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cortex.core.execution_env import ExecutionEnvironment


class WorktreeLifecycleError(RuntimeError):
    """Raised when git worktree creation fails."""


def _worktree_cache_root(project_root: Path) -> Path:
    return project_root / ".cortex" / ".cache" / "propose-optimization-worktrees"


def _new_worktree_path(project_root: Path) -> Path:
    return _worktree_cache_root(project_root) / f"wt-{uuid.uuid4().hex[:12]}"


def create_worktree(project_root: Path, env: ExecutionEnvironment) -> Path:
    """Create a detached git worktree at ``HEAD``; never touches the live branch."""
    worktree_path = _new_worktree_path(project_root)
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    result = env.execute(
        "git",
        ["worktree", "add", "--detach", str(worktree_path), "HEAD"],
        project_root,
    )
    if result.returncode != 0:
        raise WorktreeLifecycleError(
            f"git worktree add failed: {result.stderr.strip()}"
        )
    return worktree_path


def remove_worktree(
    project_root: Path, worktree_path: Path, env: ExecutionEnvironment
) -> None:
    """Remove *worktree_path*; guarantees cleanup even if git bookkeeping is stale."""
    result = env.execute(
        "git", ["worktree", "remove", "--force", str(worktree_path)], project_root
    )
    if result.returncode != 0:
        shutil.rmtree(worktree_path, ignore_errors=True)
        _ = env.execute("git", ["worktree", "prune"], project_root)


@contextmanager
def isolated_worktree(project_root: Path, env: ExecutionEnvironment) -> Iterator[Path]:
    """Yield an isolated worktree path; guarantees teardown via ``try``/``finally``.

    # AI: try/finally (not just success-path cleanup) is required so a crash
    # or exception raised anywhere inside the ``with`` block (apply, self-test,
    # diff generation) still removes the worktree — no orphaned worktrees.
    """
    worktree_path = create_worktree(project_root, env)
    try:
        yield worktree_path
    finally:
        remove_worktree(project_root, worktree_path, env)
