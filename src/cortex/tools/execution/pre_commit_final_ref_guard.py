"""Per-process Git reference guard for a verified staged tree.

No hook is installed or replaced. The guard checks the proposed commit in
Git's prepared reference transaction, after the repository's ordinary hooks.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

_HOOK = "cortex-staged-candidate"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, timeout=30
    ).strip()


def commit_verified_tree(
    root: Path, branch: str, head: str, tree: str, message: str
) -> str:
    """Commit via ordinary Git only if the prepared transaction matches."""
    if not message.strip() or not branch.startswith("refs/heads/"):
        raise ValueError("A commit message and a local branch are required")
    if _git(root, "symbolic-ref", "HEAD") != branch:
        raise ValueError("Staged candidate branch changed")
    # AI: Git can invoke the hook several times. Run its standard-library
    # entry point directly to avoid loading the Cortex tool registry each time.
    command = shlex.join(
        (sys.executable, str(Path(__file__).resolve()), branch, head, tree)
    )
    config = (
        "-c",
        f"hook.{_HOOK}.event=reference-transaction",
        "-c",
        f"hook.{_HOOK}.command={command}",
        "-c",
        f"hook.{_HOOK}.enabled=true",
    )
    hooks = _git(root, *config, "hook", "list", "reference-transaction").splitlines()
    if _HOOK not in hooks:
        raise ValueError("Git cannot protect an exact staged reference transaction")
    _ = subprocess.run(
        ["git", *config, "commit", "-m", message],
        cwd=root,
        check=True,
        timeout=300,
    )
    return _committed_revision(root, branch, tree)


def _committed_revision(root: Path, branch: str, tree: str) -> str:
    if (
        _git(root, "symbolic-ref", "HEAD") != branch
        or _git(root, "rev-parse", "HEAD^{tree}") != tree
    ):
        raise ValueError(
            "The committed tree or branch no longer matches the verified candidate"
        )
    return _git(root, "rev-parse", "HEAD")


def _prepared(branch: str, head: str, tree: str) -> bool:
    seen_branch = False
    seen_head = False
    for line in sys.stdin:
        old, new, ref = line.split()
        if ref not in {branch, "HEAD"}:
            if ref.startswith("refs/heads/"):
                return False
            continue
        if old != head or _git(Path.cwd(), "rev-parse", f"{new}^{{tree}}") != tree:
            return False
        seen_branch = seen_branch or ref == branch
        seen_head = seen_head or ref == "HEAD"
    # Ordinary commits may clean unrelated temporary references such as AUTO_MERGE.
    return seen_branch or not seen_head


def main() -> int:
    """Check only prepared reference updates; unrelated references are unchanged."""
    if len(sys.argv) != 5:
        return 1
    _, branch, head, tree, phase = sys.argv
    if phase != "prepared":
        return 0
    try:
        return 0 if _prepared(branch, head, tree) else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
