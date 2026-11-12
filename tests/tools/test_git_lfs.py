"""Git LFS MCP routing tests without a dependency on the host's LFS installation."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import GitCommandResult, OperationStatus
from cortex.tools.session.dispatcher import session
from cortex.tools.session.git_lfs import GitLfsResult
from tests.helpers.tool_call_helpers import get_tool_fn


def _ok(output: str = "") -> GitCommandResult:
    return GitCommandResult(success=True, stdout=output, stderr="", returncode=0)


def _failed(stderr: str, returncode: int = 1) -> GitCommandResult:
    return GitCommandResult(
        success=False, stdout="", stderr=stderr, returncode=returncode
    )


@pytest.fixture
def git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other"))
    with (
        patch(
            "cortex.tools.session.git_lfs.get_or_resolve_project_root",
            AsyncMock(return_value=tmp_path),
        ),
        patch("cortex.tools.session.git_lfs.run_git_command") as runner,
    ):
        yield runner


async def _call(operation: str, pattern: str | None = None) -> GitLfsResult:
    value = await get_tool_fn(session)(operation=operation, lfs_pattern=pattern)
    assert isinstance(value, str)
    return GitLfsResult.model_validate_json(value)


@pytest.mark.asyncio
async def test_lfs_status_is_read_only(git: AsyncMock, tmp_path: Path) -> None:
    git.side_effect = [
        _ok(str(tmp_path)),
        _ok("git-lfs/3.6.1"),
        _ok("filter.lfs.process\nfilter.lfs.clean\nfilter.lfs.process"),
        _ok("Listing tracked patterns\n    *.zip (.gitattributes)"),
    ]

    result = await _call("lfs_status")

    assert result.status == OperationStatus.SUCCESS
    assert result.available is True
    assert result.version == "git-lfs/3.6.1"
    assert result.filter_keys == ["filter.lfs.clean", "filter.lfs.process"]
    assert "*.zip" in (result.output or "")
    assert [call.args[0][1] for call in git.await_args_list] == [
        "rev-parse",
        "lfs",
        "config",
        "lfs",
    ]
    assert git.await_args_list[-1].args[0] == ["git", "lfs", "track"]
    for call in git.await_args_list:
        assert call.kwargs["cwd"] == tmp_path
        assert "GIT_DIR" not in call.kwargs["env"]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["lfs_status", "lfs_install", "lfs_track"])
async def test_missing_lfs(git: AsyncMock, tmp_path: Path, operation: str) -> None:
    git.side_effect = [
        _ok(str(tmp_path)),
        _failed("git: 'lfs' is not a git command. See 'git --help'."),
        _failed(""),
    ]

    result = await _call(operation, "*.zip" if operation == "lfs_track" else None)

    assert result.available is False
    if operation == "lfs_status":
        assert result.status == OperationStatus.SUCCESS
        assert result.filter_keys == []
    else:
        assert result.status == OperationStatus.ERROR
        assert "Cortex MCP host" in (result.error or "")
        assert git.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("external_hooks", [False, True])
async def test_install_scopes_hooks_and_uses_local_config(
    git: AsyncMock, tmp_path: Path, external_hooks: bool
) -> None:
    common = tmp_path / ".git"
    hooks = tmp_path.parent / "outside" if external_hooks else common / "hooks"
    git.side_effect = [
        _ok(str(tmp_path)),
        _ok("git-lfs/3.6.1"),
        _ok(str(common)),
        _ok(str(hooks)),
        _ok("Git LFS initialized."),
    ]

    result = await _call("lfs_install")

    if external_hooks:
        assert result.status == OperationStatus.ERROR
        assert git.await_count == 4
    else:
        assert result.status == OperationStatus.SUCCESS
        assert git.await_args_list[-1].args[0] == ["git", "lfs", "install", "--local"]


@pytest.mark.asyncio
async def test_track_passes_one_pattern_and_releases_lock(
    git: AsyncMock, tmp_path: Path
) -> None:
    git.side_effect = [_ok(str(tmp_path)), _ok("git-lfs/3.6.1"), _failed("", 2)]

    result = await _call("lfs_track", "--example *.zip")

    assert result.status == OperationStatus.ERROR
    assert git.await_args_list[-1].args[0] == [
        "git",
        "lfs",
        "track",
        "--",
        "--example *.zip",
    ]
    assert not (tmp_path / ".gitattributes.lock").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("pattern", [None, "", "a\nb", "!*.zip", "assets/"])
async def test_rejects_invalid_tracking_pattern(
    git: AsyncMock, tmp_path: Path, pattern: str | None
) -> None:
    git.side_effect = [_ok(str(tmp_path)), _ok("git-lfs/3.6.1")]

    result = await _call("lfs_track", pattern)

    assert result.status == OperationStatus.ERROR
    assert git.await_count == 2


@pytest.mark.asyncio
async def test_rejects_symlinked_attributes(git: AsyncMock, tmp_path: Path) -> None:
    (tmp_path / ".gitattributes").symlink_to(tmp_path.parent / "outside")
    git.side_effect = [_ok(str(tmp_path)), _ok("git-lfs/3.6.1")]

    result = await _call("lfs_track", "*.zip")

    assert result.status == OperationStatus.ERROR
    assert git.await_count == 2


@pytest.mark.asyncio
async def test_rejects_parent_worktree(git: AsyncMock, tmp_path: Path) -> None:
    git.return_value = _ok(str(tmp_path.parent))

    result = await _call("lfs_install")

    assert result.status == OperationStatus.ERROR
    assert git.await_count == 1
