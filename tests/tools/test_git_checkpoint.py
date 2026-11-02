"""Commit-preflight checkpoint tests use only disposable Git repositories."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import GitCommandResult, OperationStatus
from cortex.tools.session.dispatcher import session
from cortex.tools.session.git_checkpoint import (
    GitCheckpointResult,
    GitCheckpointState,
    create_git_checkpoint,
)
from cortex.tools.session.start_tools import run_git_command
from tests.helpers.tool_call_helpers import get_tool_fn


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate identities/configuration and require an existing HEAD."""
    for name in tuple(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")  # cspell:ignore NOSYSTEM
    root = tmp_path / "repository with spaces"
    root.mkdir()
    _ = _git(root, "init")
    _ = _git(root, "config", "user.name", "Checkpoint Test")
    _ = _git(root, "config", "user.email", "checkpoint@example.invalid")
    _ = (root / "tracked.txt").write_text("original\n")
    _ = _git(root, "add", "tracked.txt")
    _ = _git(root, "commit", "-m", "initial")
    return root


def _index_bytes(root: Path) -> bytes:
    index = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "index")
    return Path(index.strip()).read_bytes()


def _dirty(root: Path) -> None:
    _ = (root / "tracked.txt").write_text("staged\n")
    _ = _git(root, "add", "tracked.txt")
    _ = (root / "tracked.txt").write_text("unstaged\n")


def _assert_snapshot_contents(root: Path, result: GitCheckpointResult) -> None:
    assert result.snapshot_ref is not None
    assert result.snapshot_ref.startswith("refs/cortex/checkpoints/")
    assert (
        _git(root, "rev-parse", result.snapshot_ref).strip() == result.snapshot_commit
    )
    assert _git(root, "show", f"{result.snapshot_ref}:tracked.txt") == "unstaged\n"
    assert _git(root, "show", f"{result.snapshot_ref}^2:tracked.txt") == "staged\n"
    assert _git(root, "rev-parse", f"{result.snapshot_ref}^1").strip() == result.head
    assert _git(root, "rev-parse", "HEAD").strip() == result.head


@pytest.mark.asyncio
async def test_checkpoint_preserves_index_worktree_and_existing_stash(
    repository: Path,
) -> None:
    root = repository
    _ = (root / "tracked.txt").write_text("existing user stash\n")
    _ = _git(root, "stash", "push", "-m", "user-owned")
    stash = _git(root, "rev-parse", "refs/stash")
    _dirty(root)
    _ = (root / "untracked.txt").write_bytes(b"untracked\x00content")
    index, staged, unstaged = (
        _index_bytes(root),
        _git(root, "diff", "--cached", "--binary"),
        _git(root, "diff", "--binary"),
    )
    result = await create_git_checkpoint(root)
    assert result.status == OperationStatus.SUCCESS
    assert result.state == GitCheckpointState.CREATED
    assert result.worktree_clean is False
    _assert_snapshot_contents(root, result)
    assert _index_bytes(root) == index
    assert _git(root, "diff", "--cached", "--binary") == staged
    assert _git(root, "diff", "--binary") == unstaged
    assert _git(root, "rev-parse", "refs/stash") == stash
    assert (root / "untracked.txt").read_bytes() == b"untracked\x00content"


@pytest.mark.asyncio
async def test_clean_checkpoint_creates_no_ref(repository: Path) -> None:
    index = _index_bytes(repository)
    result = await create_git_checkpoint(repository)
    assert result.status == OperationStatus.SUCCESS
    assert result.state == GitCheckpointState.CLEAN
    assert result.worktree_clean is True
    assert result.head == _git(repository, "rev-parse", "HEAD").strip()
    assert result.snapshot_ref is None
    assert result.snapshot_commit is None
    assert _git(repository, "for-each-ref", "refs/cortex/checkpoints/") == ""
    assert _index_bytes(repository) == index


@pytest.mark.asyncio
async def test_untracked_only_is_not_clean_or_captured(repository: Path) -> None:
    _ = (repository / "untracked.txt").write_text("keep me")
    index = _index_bytes(repository)
    result = await create_git_checkpoint(repository)
    assert result.status == OperationStatus.ERROR
    assert result.state == GitCheckpointState.ERROR
    assert result.worktree_clean is False
    assert result.snapshot_ref is None
    assert result.error is not None and "Untracked files" in result.error
    assert _index_bytes(repository) == index
    assert (repository / "untracked.txt").read_text() == "keep me"
    assert _git(repository, "for-each-ref", "refs/cortex/checkpoints/") == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["stash", "update-ref"])
async def test_git_errors_never_fall_back_to_head(
    repository: Path, failure: str
) -> None:
    _dirty(repository)
    index = _index_bytes(repository)

    async def fail_command(
        cmd: list[str],
        cwd: Path | None = None,
        timeout: float = 5.0,
        *,
        env: dict[str, str] | None = None,
    ) -> GitCommandResult:
        if cmd[1] == failure:
            return GitCommandResult(
                success=False,
                stdout="",
                stderr="beyond a symbolic link",
                returncode=1,
                error=None,
            )
        return await run_git_command(cmd, cwd, timeout, env=env)

    with patch("cortex.tools.session.git_checkpoint.run_git_command", fail_command):
        result = await create_git_checkpoint(repository)
    assert result.status == OperationStatus.ERROR
    assert result.state == GitCheckpointState.ERROR
    assert result.snapshot_ref is None
    assert result.error is not None and "beyond a symbolic link" in result.error
    assert (result.attempted_ref is not None) == (failure == "update-ref")
    assert _index_bytes(repository) == index
    assert (repository / "tracked.txt").read_text() == "unstaged\n"
    assert _git(repository, "for-each-ref", "refs/cortex/checkpoints/") == ""


@pytest.mark.asyncio
async def test_non_repository_reports_error(tmp_path: Path) -> None:
    result = await create_git_checkpoint(tmp_path)
    assert result.status == OperationStatus.ERROR
    assert result.state == GitCheckpointState.ERROR
    assert result.worktree_clean is None
    assert result.snapshot_ref is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_unborn_head_reports_error(repository: Path) -> None:
    _ = _git(repository, "checkout", "--orphan", "unborn")
    result = await create_git_checkpoint(repository)
    assert result.status == OperationStatus.ERROR
    assert result.head is None
    assert result.snapshot_ref is None
    assert result.error is not None and "rev-parse" in result.error


@pytest.mark.asyncio
async def test_nested_project_root_is_refused(repository: Path) -> None:
    nested = repository / "nested"
    nested.mkdir()
    result = await create_git_checkpoint(nested)
    assert result.status == OperationStatus.ERROR
    assert result.error == "Resolved project root is not the Git worktree root"
    assert result.snapshot_ref is None


@pytest.mark.asyncio
async def test_linked_worktree_keeps_own_index_and_uses_shared_ref(
    repository: Path, tmp_path: Path
) -> None:
    linked = tmp_path / "linked"
    _ = _git(repository, "worktree", "add", "-b", "checkpoint-test", str(linked))
    _dirty(linked)
    index = _index_bytes(linked)
    result = await create_git_checkpoint(linked)
    assert result.status == OperationStatus.SUCCESS
    assert result.project_root == str(linked.resolve())
    assert result.snapshot_ref is not None
    assert (
        _git(repository, "rev-parse", result.snapshot_ref).strip()
        == result.snapshot_commit
    )
    assert _git(repository, "for-each-ref", "refs/stash") == ""
    assert _index_bytes(linked) == index
    assert (repository / "tracked.txt").read_text() == "original\n"
    assert _git(linked, "show", f"{result.snapshot_ref}^2:tracked.txt") == "staged\n"


@pytest.mark.asyncio
async def test_explicit_session_operation_uses_context_root(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dirty(repository)
    monkeypatch.chdir(tmp_path)
    with patch(
        "cortex.tools.session.git_checkpoint.get_or_resolve_project_root",
        new=AsyncMock(return_value=repository),
    ) as resolve:
        raw_result = await get_tool_fn(session)(operation="checkpoint", ctx=None)
        assert isinstance(raw_result, str)
        result = json.loads(raw_result)
    resolve.assert_awaited_once_with(None)
    assert result["state"] == "created"
    assert result["project_root"] == str(repository.resolve())


@pytest.mark.asyncio
async def test_inherited_git_redirection_does_not_replace_index(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dirty(repository)
    redirected_index = tmp_path / "foreign-index"
    _ = redirected_index.write_bytes(b"leave untouched")
    monkeypatch.setenv("GIT_INDEX_FILE", str(redirected_index))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-repository"))
    result = await create_git_checkpoint(repository)
    assert result.state == GitCheckpointState.CREATED
    assert redirected_index.read_bytes() == b"leave untouched"


@pytest.mark.asyncio
async def test_subprocess_timeout_is_error_with_bounded_argv_execution(
    repository: Path,
) -> None:
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=TimeoutError)
    process.wait = AsyncMock(return_value=1)
    with patch(
        "cortex.tools.session.start_tools.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=process),
    ) as execute:
        result = await create_git_checkpoint(repository)
    assert result.state == GitCheckpointState.ERROR
    assert result.snapshot_ref is None
    assert result.error is not None and "timed out after 5.0s" in result.error
    assert execute.await_args is not None
    assert execute.await_args.args == ("git", "rev-parse", "--show-toplevel")
    assert execute.await_args.kwargs["cwd"] == str(repository.resolve())
    assert "shell" not in execute.await_args.kwargs
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
