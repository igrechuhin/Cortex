"""Explicit commit-preflight checkpoints; never restore or change user files.

A checkpoint saves tracked index/worktree content in a stash-shaped commit and
anchors it under a new shared refs/cortex/checkpoints/* ref. refs/stash is not
changed. Untracked/ignored files and submodule worktree contents are not saved.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from enum import Enum
from pathlib import Path
from uuid import uuid4

from cortex.core.context_logging import MCPContext
from cortex.core.models import OperationStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.session.start_tools import run_git_command


class GitCheckpointState(str, Enum):
    """Observed outcome, distinct from the session orientation status."""

    CREATED = "created"
    CLEAN = "clean"
    ERROR = "error"


class GitCheckpointResult(StrictBaseModel):
    """Checkpoint evidence; a failed ref write is not a durable snapshot."""

    status: OperationStatus = OperationStatus.ERROR
    state: GitCheckpointState = GitCheckpointState.ERROR
    project_root: str
    head: str | None = None
    worktree_clean: bool | None = None
    snapshot_ref: str | None = None
    snapshot_commit: str | None = None
    attempted_ref: str | None = None
    tracked_only: bool = True
    error: str | None = None


class _GitCheckpointError(RuntimeError):
    """A required Git step failed; no HEAD fallback is safe."""


def _git_environment() -> dict[str, str]:
    """Do not inherit a caller's repository/index/namespace redirection."""
    env = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        _ = env.pop(name, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


async def _git(root: Path, env: dict[str, str], *args: str) -> str:
    """Use the shared argv-only, rate-limited, bounded Git runner."""
    result = await run_git_command(["git", *args], cwd=root, timeout=5.0, env=env)
    if not result.success:
        detail = result.error or result.stderr or f"exit status {result.returncode}"
        raise _GitCheckpointError(f"git {args[0]} failed: {detail.strip()}")
    return result.stdout


async def _create_snapshot(root: Path, env: dict[str, str]) -> str:
    """Let stash update only a private index, never the user's real index."""
    index_path = await _git(
        root, env, "rev-parse", "--path-format=absolute", "--git-path", "index"
    )
    with tempfile.TemporaryDirectory(prefix="cortex-git-checkpoint-") as temporary:
        private_index = Path(temporary) / "index"
        _ = shutil.copyfile(Path(index_path.strip()), private_index)
        private_env = {**env, "GIT_INDEX_FILE": str(private_index)}
        return (
            await _git(root, private_env, "stash", "create", "cortex-commit-preflight")
        ).strip()


async def _save_dirty_checkpoint(
    root: Path, env: dict[str, str], result: GitCheckpointResult
) -> GitCheckpointResult:
    snapshot = await _create_snapshot(root, env)
    if not snapshot:
        raise _GitCheckpointError(
            "Git reported changes but created no tracked snapshot. "
            + "Untracked files and submodule worktree contents are not captured."
        )
    result.snapshot_commit = snapshot
    result.attempted_ref = f"refs/cortex/checkpoints/{uuid4().hex}"
    _ = await _git(root, env, "update-ref", result.attempted_ref, snapshot, "")
    result.snapshot_ref = result.attempted_ref
    result.status = OperationStatus.SUCCESS
    result.state = GitCheckpointState.CREATED
    return result


async def create_git_checkpoint(project_root: Path) -> GitCheckpointResult:
    """Save tracked changes without replacing the worktree, index, or stash.

    Refs are shared by linked worktrees. Each explicit invocation creates a new
    ref; retention/removal and any restoration require a separate user decision.
    Call only while other writers to this worktree are quiescent.
    """
    root = project_root.resolve()
    env = _git_environment()
    result = GitCheckpointResult(project_root=str(root))
    try:
        top = (await _git(root, env, "rev-parse", "--show-toplevel")).strip()
        if Path(top).resolve() != root:
            raise _GitCheckpointError(
                "Resolved project root is not the Git worktree root"
            )
        result.head = (await _git(root, env, "rev-parse", "--verify", "HEAD")).strip()
        status = await _git(
            root, env, "status", "--porcelain", "--untracked-files=normal"
        )
        result.worktree_clean = not bool(status)
        if status:
            return await _save_dirty_checkpoint(root, env, result)
        result.status = OperationStatus.SUCCESS
        result.state = GitCheckpointState.CLEAN
    except (_GitCheckpointError, OSError) as exc:
        result.error = str(exc)
    return result


async def checkpoint_session(ctx: MCPContext | None = None) -> str:
    """Resolve the active project like session(start), not the server's cwd."""
    project_root = await get_or_resolve_project_root(ctx)
    return (await create_git_checkpoint(project_root)).model_dump_json()
