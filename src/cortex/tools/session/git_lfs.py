"""Bounded, repository-scoped Git LFS operations for the session tool."""

from enum import StrEnum
from pathlib import Path

from cortex.core.context_logging import MCPContext
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import GitCommandResult, OperationStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.session.start_tools import git_worktree_environment, run_git_command


class GitLfsOperation(StrEnum):
    """Explicit Git LFS operations exposed by the session dispatcher."""

    STATUS = "lfs_status"
    INSTALL = "lfs_install"
    TRACK = "lfs_track"


class GitLfsResult(StrictBaseModel):
    """Local LFS observations or the outcome of an explicit configuration step."""

    status: OperationStatus = OperationStatus.ERROR
    operation: GitLfsOperation
    project_root: str
    available: bool | None = None
    version: str | None = None
    filter_keys: list[str] | None = None
    output: str | None = None
    error: str | None = None


class _GitLfsError(RuntimeError):
    """A Git LFS operation failed or its preconditions were not met."""


def _require_success(result: GitCommandResult, command: str) -> str:
    if not result.success:
        detail = result.error or f"exit status {result.returncode}"
        raise _GitLfsError(f"{command} failed ({detail})")
    return result.stdout.strip()


def _validate_pattern(pattern: str | None) -> str:
    if (
        not pattern
        or not pattern.strip()
        or pattern.startswith(("!", "[attr]"))
        or pattern.endswith("/")
        or any(ord(char) < 32 or ord(char) == 127 for char in pattern)
    ):
        raise _GitLfsError("lfs_track requires one valid Git attributes lfs_pattern")
    return pattern


async def _install(root: Path, env: dict[str, str]) -> str:
    git_dir = await run_git_command(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        env=env,
    )
    common = Path(_require_success(git_dir, "git rev-parse --git-common-dir")).resolve()
    hooks_path = await run_git_command(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
        cwd=root,
        env=env,
    )
    hooks = Path(_require_success(hooks_path, "git rev-parse --git-path")).resolve()
    if not (hooks.is_relative_to(root) or hooks.is_relative_to(common)):
        raise _GitLfsError(
            "Git hooks directory is outside the repository; integrate LFS manually"
        )
    installed = await run_git_command(
        ["git", "lfs", "install", "--local"], cwd=root, env=env
    )
    return _require_success(installed, "git lfs install --local (check existing hooks)")


async def _track(root: Path, env: dict[str, str], pattern: str) -> str:
    manager = FileSystemManager(root)
    lock = root / ".gitattributes.lock"
    await manager.acquire_lock(lock)
    try:
        return await _track_locked(root, env, pattern)
    finally:
        await manager.release_lock(lock)


async def _track_locked(root: Path, env: dict[str, str], pattern: str) -> str:
    attributes = root / ".gitattributes"
    if attributes.is_symlink() or (
        attributes.exists()
        and (not attributes.is_file() or attributes.stat().st_nlink > 1)
    ):
        raise _GitLfsError(".gitattributes must be an ordinary worktree file")
    tracked = await run_git_command(
        ["git", "lfs", "track", "--", pattern], cwd=root, env=env
    )
    return _require_success(tracked, "git lfs track")


async def _read_status(root: Path, env: dict[str, str], result: GitLfsResult) -> None:
    keys = await run_git_command(
        ["git", "config", "--name-only", "--get-regexp", r"^filter\.lfs\."],
        cwd=root,
        env=env,
    )
    if keys.returncode == 1:
        result.filter_keys = []
    else:
        result.filter_keys = sorted(
            set(_require_success(keys, "git config filter.lfs").splitlines())
        )
    if result.available:
        tracked = await run_git_command(["git", "lfs", "track"], cwd=root, env=env)
        result.output = _require_success(tracked, "git lfs track (list patterns)")


async def _run(
    root: Path, operation: GitLfsOperation, pattern: str | None, result: GitLfsResult
) -> None:
    env = git_worktree_environment()
    env["LC_ALL"] = "C"
    top = await run_git_command(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, env=env
    )
    if Path(_require_success(top, "git rev-parse")).resolve() != root:
        raise _GitLfsError("Resolved project root is not the Git worktree root")
    version = await run_git_command(["git", "lfs", "version"], cwd=root, env=env)
    if not version.success and "'lfs' is not a git command" in version.stderr:
        result.available = False
        if operation != GitLfsOperation.STATUS:
            raise _GitLfsError("Install Git LFS on the Cortex MCP host first")
    else:
        result.version = _require_success(version, "git lfs version")
        result.available = True

    if operation == GitLfsOperation.STATUS:
        await _read_status(root, env, result)
    elif operation == GitLfsOperation.INSTALL:
        result.output = await _install(root, env)
    else:
        result.output = await _track(root, env, _validate_pattern(pattern))
    result.status = OperationStatus.SUCCESS


async def run_session_git_lfs(
    operation: GitLfsOperation, pattern: str | None, ctx: MCPContext | None
) -> str:
    """Use the attached project root, with no caller-supplied path override."""
    root = (await get_or_resolve_project_root(ctx)).resolve()
    result = GitLfsResult(operation=operation, project_root=str(root))
    try:
        if pattern is not None and operation != GitLfsOperation.TRACK:
            raise _GitLfsError("lfs_pattern is only accepted by lfs_track")
        await _run(root, operation, pattern, result)
    except (_GitLfsError, FileLockTimeoutError, OSError) as exc:
        result.error = str(exc)
    return result.model_dump_json()
