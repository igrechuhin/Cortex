"""Shared git fixtures for canonical read regression tests."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
    )
    return result.stdout.strip()


def init_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _ = _git(root, "init", "-q")
    _ = _git(root, "config", "user.email", "test@example.com")
    _ = _git(root, "config", "user.name", "Test")


def commit_all(root: Path, message: str) -> str:
    _ = _git(root, "add", "-A")
    _ = _git(root, "commit", "-qm", message)
    return _git(root, "rev-parse", "HEAD")


def build_canonical_main(main: Path) -> None:
    """Create a canonical main worktree with plans, results and artifacts."""

    init_git_repo(main)
    memory_bank = main / ".cortex" / "memory-bank"
    plans = main / ".cortex" / "plans"
    reviews = main / ".cortex" / "reviews"
    for directory in (memory_bank, plans, reviews):
        directory.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank / "activeContext.md").write_text(
        (
            "# Active Context\n\n## Completed Work (2026-10-24)\n\n"
            "- **Approved result** - COMPLETE.\n"
        ),
        encoding="utf-8",
    )
    _ = (memory_bank / "progress.md").write_text(
        "# Progress\n\n- **Approved result** - COMPLETE.\n", encoding="utf-8"
    )
    _ = (plans / "shared-base.md").write_text(
        "---\ntitle: Shared base\nstatus: DONE\n---\n# Shared base\n",
        encoding="utf-8",
    )
    _ = (reviews / "approved-report.md").write_text(
        "# Approved Report\n\nValidated conclusion.\n", encoding="utf-8"
    )
    _ = commit_all(main, "base")


def add_linked_worktree(main: Path, worktree: Path) -> None:
    _ = _git(main, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")


def snapshot_tree(root: Path) -> dict[str, str]:
    """Map relative file path to content digest, excluding .git."""

    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            snapshot[path.relative_to(root).as_posix()] = "symlink"
            continue
        snapshot[path.relative_to(root).as_posix()] = sha256(
            path.read_bytes()
        ).hexdigest()
    return snapshot


def digest_of(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
