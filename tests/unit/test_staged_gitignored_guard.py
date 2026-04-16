"""Tests for check_staged_gitignored — the gitignored-files-in-staging guard.

Covers the fix that prevents accidentally committing gitignored files by
detecting them in the staging area before Phase A runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from cortex.tools.execution.pre_commit_submodule_guard import check_staged_gitignored


def _make_completed(
    stdout: str, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout, "")


class TestCheckStagedGitignored:
    def test_returns_empty_when_no_git_dir(self, tmp_path: Path) -> None:
        result = check_staged_gitignored(tmp_path)
        assert result == []

    def test_returns_empty_when_nothing_staged(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed("")
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            return_value=diff_proc,
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == []

    def test_returns_empty_when_no_ignored_files_staged(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed("src/foo.py\nsrc/bar.py\n")
        # check-ignore returns exit 1 (no matches) with empty stdout
        ignore_proc = _make_completed("", returncode=1)
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            side_effect=[diff_proc, ignore_proc],
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == []

    def test_returns_ignored_files_when_present(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed(
            "src/foo.py\n.cortex/history/activeContext_v11.md\n"
        )
        ignore_proc = _make_completed(".cortex/history/activeContext_v11.md\n")
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            side_effect=[diff_proc, ignore_proc],
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == [".cortex/history/activeContext_v11.md"]

    def test_returns_multiple_ignored_files(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed(
            "src/foo.py\n"
            + ".cortex/history/activeContext_v11.md\n"
            + ".cortex/history/progress_v11.md\n"
        )
        ignore_proc = _make_completed(
            ".cortex/history/activeContext_v11.md\n"
            + ".cortex/history/progress_v11.md\n"
        )
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            side_effect=[diff_proc, ignore_proc],
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == [
            ".cortex/history/activeContext_v11.md",
            ".cortex/history/progress_v11.md",
        ]

    def test_returns_empty_on_diff_timeout(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 60),
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == []

    def test_returns_empty_on_check_ignore_error_exit(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed(".cortex/history/activeContext_v11.md\n")
        ignore_proc = _make_completed("", returncode=128)
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            side_effect=[diff_proc, ignore_proc],
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == []

    def test_returns_empty_on_diff_nonzero_exit(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        diff_proc = _make_completed("", returncode=128)
        with patch(
            "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
            return_value=diff_proc,
        ):
            result = check_staged_gitignored(tmp_path)
        assert result == []
