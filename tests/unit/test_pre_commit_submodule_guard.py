"""Tests for submodule hygiene guard used by Phase A / detached worker."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from cortex.tools.execution.pre_commit_submodule_guard import (
    SubmoduleHygieneCode,
    precommit_block_response,
    scan_submodule_hygiene,
)


def test_scan_skips_when_no_git_dir(tmp_path: Path) -> None:
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run"
    ) as mock_run:
        report = scan_submodule_hygiene(tmp_path)
    assert report.violations == ()
    mock_run.assert_not_called()


def test_scan_reports_out_of_sync_from_status_prefix(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    fake = subprocess.CompletedProcess(
        ["git", "submodule", "status"],
        0,
        "+abcd1234abcdef12 sub (heads/main)\n",
        "",
    )
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        return_value=fake,
    ):
        report = scan_submodule_hygiene(tmp_path)
    assert len(report.violations) == 1
    v = report.violations[0]
    assert v.path == "sub"
    assert v.code is SubmoduleHygieneCode.OUT_OF_SYNC


def test_scan_reports_merge_conflict(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    fake = subprocess.CompletedProcess(
        ["git", "submodule", "status"],
        0,
        "Uabcd1234abcdef12 sub (heads/main)\n",
        "",
    )
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        return_value=fake,
    ):
        report = scan_submodule_hygiene(tmp_path)
    assert len(report.violations) == 1
    assert report.violations[0].code is SubmoduleHygieneCode.MERGE_CONFLICT


def test_scan_reports_dirty_worktree_when_porcelain_nonempty(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "sub").mkdir(parents=True)
    (tmp_path / "sub" / ".git").mkdir()

    def fake_run(
        cmd: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if "submodule" in cmd:
            return subprocess.CompletedProcess(cmd, 0, " abcd1234abcdef12 sub\n", "")
        if "--porcelain" in cmd:
            return subprocess.CompletedProcess(cmd, 0, " M file.txt\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected")

    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        side_effect=fake_run,
    ):
        report = scan_submodule_hygiene(tmp_path)
    assert len(report.violations) == 1
    assert report.violations[0].code is SubmoduleHygieneCode.DIRTY_WORKTREE


def test_scan_ignores_git_submodule_failure(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    fake = subprocess.CompletedProcess(
        ["git", "submodule", "status"],
        1,
        "",
        "fatal: no submodule mapping",
    )
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        return_value=fake,
    ):
        report = scan_submodule_hygiene(tmp_path)
    assert report.violations == ()


def test_precommit_block_response_none_when_clean(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    fake = subprocess.CompletedProcess(
        ["git", "submodule", "status"],
        0,
        "",
        "",
    )
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        return_value=fake,
    ):
        assert precommit_block_response(tmp_path) is None


def test_precommit_block_response_shape_when_dirty(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    fake = subprocess.CompletedProcess(
        ["git", "submodule", "status"],
        0,
        "+abcd1234abcdef12 sub\n",
        "",
    )
    with patch(
        "cortex.tools.execution.pre_commit_submodule_guard.subprocess.run",
        return_value=fake,
    ):
        blocked = precommit_block_response(tmp_path)
    assert blocked is not None
    assert blocked.get("status") == "error"
    assert blocked.get("success") is False
    assert blocked.get("total_errors") == 1
    results = blocked.get("results")
    assert isinstance(results, dict)
    sub = results.get("submodule_hygiene")
    assert isinstance(sub, dict)
    assert sub.get("success") is False
    assert blocked.get("remediation") == "git submodule update --init --recursive"
