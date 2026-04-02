"""rumdl binary resolution for detached pre-commit workers.

Centralises all strategies for locating the ``rumdl`` CLI across virtualenvs,
sandboxed IDE environments, and minimal-PATH MCP subprocesses so neither
:mod:`pre_commit_worker` nor :mod:`pre_commit_fix_worker` need to re-implement
the fallback chain.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from cortex.core.path_resolver import (
    augmented_environ_with_project_venv_bins,
    get_legacy_venv_bin_path,
    get_venv_bin_path,
    iter_venv_executable_candidates,
)

# ── uv discovery ──────────────────────────────────────────────────────────────

_UV_COMMON_PATHS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin/uv"),  # macOS Homebrew (Apple Silicon)
    Path("/usr/local/bin/uv"),  # macOS Homebrew (Intel) / Linux system
    Path("/usr/bin/uv"),  # Linux package manager
    Path.home() / ".local/bin/uv",  # pip/uv user install (XDG)
    Path.home() / ".cargo/bin/uv",  # cargo install
)


def uv_executable() -> str | None:
    """Resolve ``uv`` for ``uv run rumdl`` when PATH is minimal (e.g. MCP subprocess)."""
    found = shutil.which("uv")
    if found:
        return found
    for candidate in _UV_COMMON_PATHS:
        if candidate.is_file():
            return str(candidate.resolve())
    return None


# ── rumdl path resolution ─────────────────────────────────────────────────────


def _rumdl_from_virtual_env_var() -> str | None:
    """Return rumdl path from ``$VIRTUAL_ENV`` if set and the binary exists."""
    venv_env = os.environ.get("VIRTUAL_ENV")
    if not venv_env:
        return None
    ve_rumdl = Path(venv_env) / "bin" / "rumdl"
    return str(ve_rumdl.resolve()) if ve_rumdl.is_file() else None


def _rumdl_from_project_venv(root: Path) -> str | None:
    """Return rumdl path from project ``.venv`` or ``venv`` if the file exists."""
    for candidate in iter_venv_executable_candidates(root, "rumdl"):
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def _rumdl_from_shutil_which(root: Path) -> str | None:
    """Return rumdl path found only inside project venv bins (not full PATH)."""
    venv_path = os.pathsep.join(
        [
            str(get_venv_bin_path(root).resolve()),
            str(get_legacy_venv_bin_path(root).resolve()),
        ]
    )
    return shutil.which("rumdl", path=venv_path)


def _rumdl_forced_venv_path(root: Path) -> str:
    """Return a conventional ``.venv/bin/rumdl`` path (may not exist on disk).

    Used as last resort when stat()-based probes fail (sandbox environments that
    hide the venv tree from the filesystem layer while still executing it).
    """
    return str(next(iter_venv_executable_candidates(root, "rumdl")).resolve())


def resolve_rumdl_path(project_root: str | Path | None = None) -> str:
    """Resolve rumdl binary from running Python env or project ``.venv``.

    Checks in order: interpreter-adjacent binary, ``$VIRTUAL_ENV``, project
    venv ``is_file()`` probe, ``shutil.which`` restricted to venv bins,
    forced conventional path (sandbox bypass), bare ``"rumdl"`` sentinel.
    """
    venv_bin = Path(sys.executable).parent / "rumdl"
    if venv_bin.is_file():
        return str(venv_bin)

    from_env = _rumdl_from_virtual_env_var()
    if from_env:
        return from_env

    if project_root is not None:
        root = Path(project_root)
        from_venv = _rumdl_from_project_venv(root)
        if from_venv:
            return from_venv
        from_which = _rumdl_from_shutil_which(root)
        if from_which:
            return from_which
        # stat() may fail in sandboxes — return conventional path unconditionally.
        return _rumdl_forced_venv_path(root)

    return "rumdl"


# ── argv builders ─────────────────────────────────────────────────────────────


def coerce_rumdl_argv0(root: Path, cmd: list[str]) -> list[str]:
    """Replace bare ``"rumdl"`` argv0 with an absolute path when possible."""
    if not cmd or cmd[0] != "rumdl":
        return cmd
    env = augmented_environ_with_project_venv_bins(root)
    found = shutil.which("rumdl", path=env.get("PATH", ""))
    if found:
        return [found, *cmd[1:]]
    from_venv = _rumdl_from_project_venv(root)
    if from_venv:
        return [from_venv, *cmd[1:]]
    # Sandbox fallback: use conventional path even without is_file() confirmation.
    return [_rumdl_forced_venv_path(root), *cmd[1:]]


def markdown_rumdl_argv(root: Path, *, with_fix: bool) -> list[str]:
    """Build ``rumdl check [--fix]`` argv with config, preferring ``uv run``.

    Prefer ``uv run rumdl`` so the worker does not depend on exec-ing
    ``.venv/bin/rumdl`` directly — some sandboxes hide the venv tree from
    ``execve`` even when the path is otherwise correct.
    """
    rumdl_config = root / ".rumdl.toml"
    config_args: list[str] = (
        ["--config", str(rumdl_config)] if rumdl_config.is_file() else []
    )
    fix_args: list[str] = ["--fix"] if with_fix else []

    uv_bin = uv_executable()
    if uv_bin:
        return [uv_bin, "run", "rumdl", "check", *fix_args, *config_args]

    exe = resolve_rumdl_path(root)
    if exe != "rumdl":
        return [exe, "check", *fix_args, *config_args]

    # resolve_rumdl_path returned the bare sentinel — force an absolute path.
    forced = str((root / ".venv/bin/rumdl").resolve())
    return [forced, "check", *fix_args, *config_args]
