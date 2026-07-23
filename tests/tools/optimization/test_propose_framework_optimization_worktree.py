"""Tests for propose_framework_optimization isolated worktree lifecycle."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.core.execution_env import ExecutionEnvironment, ExecutionResult
from cortex.tools.optimization.propose_framework_optimization_worktree import (
    WorktreeLifecycleError,
    create_worktree,
    isolated_worktree,
    remove_worktree,
)


def _ok_result(stdout: str = "") -> ExecutionResult:
    return ExecutionResult(returncode=0, stdout=stdout, stderr="", duration_ms=1)


def _fail_result(stderr: str = "boom") -> ExecutionResult:
    return ExecutionResult(returncode=1, stdout="", stderr=stderr, duration_ms=1)


def test_create_worktree_invokes_git_worktree_add(tmp_path: Path) -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _ok_result()

    worktree_path = create_worktree(tmp_path, env)

    env.execute.assert_called_once()
    args = env.execute.call_args.args
    assert args[0] == "git"
    assert args[1][:3] == ["worktree", "add", "--detach"]
    assert str(worktree_path) in args[1]
    assert args[2] == tmp_path


def test_create_worktree_raises_on_git_failure(tmp_path: Path) -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _fail_result("no such HEAD")

    with pytest.raises(WorktreeLifecycleError):
        _ = create_worktree(tmp_path, env)


def test_remove_worktree_invokes_git_worktree_remove(tmp_path: Path) -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _ok_result()
    worktree_path = tmp_path / "wt-abc"
    worktree_path.mkdir()

    remove_worktree(tmp_path, worktree_path, env)

    args = env.execute.call_args.args
    assert args[1] == ["worktree", "remove", "--force", str(worktree_path)]


def test_remove_worktree_falls_back_to_rmtree_on_failure(tmp_path: Path) -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _fail_result("worktree not found")
    worktree_path = tmp_path / "wt-abc"
    worktree_path.mkdir()
    _ = (worktree_path / "leftover.txt").write_text("x", encoding="utf-8")

    remove_worktree(tmp_path, worktree_path, env)

    assert not worktree_path.exists()
    # git worktree remove + git worktree prune fallback
    assert env.execute.call_count == 2


def test_isolated_worktree_removes_worktree_on_success(tmp_path: Path) -> None:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _ok_result()
    seen_path: Path | None = None

    with isolated_worktree(tmp_path, env) as worktree_path:
        seen_path = worktree_path

    assert seen_path is not None
    remove_call = env.execute.call_args_list[-1]
    assert remove_call.args[1][:2] == ["worktree", "remove"]


def test_isolated_worktree_removes_worktree_on_exception(tmp_path: Path) -> None:
    """Guaranteed teardown: a forced exception mid-run must still remove the worktree."""
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.return_value = _ok_result()

    with pytest.raises(RuntimeError, match="forced failure"):
        with isolated_worktree(tmp_path, env):
            raise RuntimeError("forced failure")

    remove_call = env.execute.call_args_list[-1]
    assert remove_call.args[1][:2] == ["worktree", "remove"]
