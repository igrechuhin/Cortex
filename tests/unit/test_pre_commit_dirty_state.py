"""Tests for pre-commit dirty-state tracking (Phase 89).

Tests PipelineDirtyTracker and skip_if_clean behavior to verify
redundant checks are skipped when no source files change between
Phase A and Step 12.
"""

# pyright: reportUnusedFunction=false
from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.core.models import ModelDict
from cortex.tools.execution.pre_commit_dirty_state import (
    CheckCleanResult,
    PipelineDirtyTracker,
    PipelineFingerprint,
    SkipDecision,
    compute_git_file_hash,
)

_HASH_TARGET = "cortex.tools.execution.pre_commit_dirty_state.compute_git_file_hash"
_SUBPROC = "cortex.tools.execution.pre_commit_dirty_state.subprocess.run"

_FP_BASE = PipelineFingerprint("abc123", "def456", 5, 10)
_FP_SRC_CHANGED = PipelineFingerprint("xyz789", "changed", 6, 12)
_FP_DOCS_ONLY = PipelineFingerprint("abc123", "changed", 5, 12)


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    PipelineDirtyTracker.reset()


def _make_tracker(tmp_path: Path, *, passed: bool = True) -> PipelineDirtyTracker:
    tracker = PipelineDirtyTracker.get_instance()
    with patch(_HASH_TARGET, return_value=_FP_BASE):
        tracker.record_phase_a(tmp_path, passed=passed)
    return tracker


def _git_side_effect(
    staged: str = "",
    unstaged: str = "",
    untracked: str = "",
):  # noqa: ANN202
    def _inner(args: list[str], **_kw: object) -> object:
        class _R:
            returncode = 0
            stdout = ""

        r = _R()
        if "ls-files" in args:
            r.stdout = untracked
        elif "--cached" in args:
            r.stdout = staged
        else:
            r.stdout = unstaged
        return r

    return _inner


# --- compute_git_file_hash -------------------------------------------------


class TestComputeGitFileHash:
    def test_empty_diff(self, tmp_path: Path) -> None:
        with patch(_SUBPROC) as m:
            m.return_value.returncode = 0
            m.return_value.stdout = ""
            fp = compute_git_file_hash(tmp_path)
        assert fp.source_file_count == 0 and fp.total_file_count == 0

    def test_python_as_source(self, tmp_path: Path) -> None:
        with patch(
            _SUBPROC,
            side_effect=_git_side_effect(
                staged="M\tsrc/foo.py\nA\tsrc/bar.py",
            ),
        ):
            fp = compute_git_file_hash(tmp_path)
        assert fp.source_file_count == 2

    def test_markdown_not_source(self, tmp_path: Path) -> None:
        with patch(
            _SUBPROC,
            side_effect=_git_side_effect(
                staged="M\tdocs/readme.md\nM\tsrc/main.py",
            ),
        ):
            fp = compute_git_file_hash(tmp_path)
        assert fp.source_file_count == 1 and fp.total_file_count == 2

    def test_git_failure(self, tmp_path: Path) -> None:
        with patch(_SUBPROC) as m:
            m.return_value.returncode = 1
            m.return_value.stdout = ""
            fp = compute_git_file_hash(tmp_path)
        assert fp.source_file_count == 0

    def test_untracked_included(self, tmp_path: Path) -> None:
        with patch(
            _SUBPROC,
            side_effect=_git_side_effect(
                untracked="src/new_module.py\n",
            ),
        ):
            fp = compute_git_file_hash(tmp_path)
        assert fp.source_file_count == 1


# --- PipelineDirtyTracker -------------------------------------------------


class TestPipelineDirtyTracker:
    def test_singleton(self) -> None:
        assert (
            PipelineDirtyTracker.get_instance() is PipelineDirtyTracker.get_instance()
        )

    def test_reset(self) -> None:
        t1 = PipelineDirtyTracker.get_instance()
        PipelineDirtyTracker.reset()
        assert t1 is not PipelineDirtyTracker.get_instance()

    def test_inactive_before_phase_a(self) -> None:
        assert not PipelineDirtyTracker.get_instance().is_active

    def test_active_after_pass(self, tmp_path: Path) -> None:
        t = _make_tracker(tmp_path)
        assert t.is_active and t.phase_a_fingerprint is not None

    def test_inactive_after_fail(self, tmp_path: Path) -> None:
        assert not _make_tracker(tmp_path, passed=False).is_active

    def test_mark_dirty_and_clean_metadata(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        tracker.mark_dirty("tests")
        assert tracker.dirty_checks.get("tests") is True

        tracker.mark_clean(
            "tests",
            step="A.5",
            timestamp="2026-03-11T00:00:00Z",
        )
        assert tracker.dirty_checks.get("tests") is False
        result = tracker.last_clean_results.get("tests")
        assert isinstance(result, CheckCleanResult)
        assert result.passed is True
        assert result.step == "A.5"


# --- Skip decisions --------------------------------------------------------


class TestSkipDecisions:
    _SOURCE_CHECKS = ("type_check", "tests", "format", "quality")

    def test_skip_no_source_changes(self, tmp_path: Path) -> None:
        t = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_DOCS_ONLY):
            for name in self._SOURCE_CHECKS:
                assert t.can_skip_check(name).can_skip, name

    def test_no_skip_source_changed(self, tmp_path: Path) -> None:
        t = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_SRC_CHANGED):
            for name in self._SOURCE_CHECKS:
                assert not t.can_skip_check(name).can_skip, name

    def test_non_source_always_runs(self, tmp_path: Path) -> None:
        t = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            assert not t.can_skip_check("test_naming").can_skip

    def test_no_skip_when_inactive(self) -> None:
        assert not PipelineDirtyTracker.get_instance().can_skip_check("tests").can_skip


# --- try_skip_clean_checks ------------------------------------------------


class TestTrySkipCleanChecks:
    @pytest.mark.asyncio()
    async def test_skip_result(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
        from cortex.tools.execution.pre_commit_tools_execute_checks import (
            try_skip_clean_checks,
        )

        _ = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_DOCS_ONLY):
            result = await try_skip_clean_checks(
                [PreCommitCheck.TYPE_CHECK, PreCommitCheck.QUALITY],
                None,
            )
        assert result is not None and result["skipped"] is True

    @pytest.mark.asyncio()
    async def test_no_skip_source_changed(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
        from cortex.tools.execution.pre_commit_tools_execute_checks import (
            try_skip_clean_checks,
        )

        _ = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_SRC_CHANGED):
            assert await try_skip_clean_checks([PreCommitCheck.TESTS], None) is None

    @pytest.mark.asyncio()
    async def test_no_skip_inactive(self) -> None:
        from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
        from cortex.tools.execution.pre_commit_tools_execute_checks import (
            try_skip_clean_checks,
        )

        assert await try_skip_clean_checks([PreCommitCheck.FORMAT], None) is None

    @pytest.mark.asyncio()
    async def test_no_skip_mixed_checks(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
        from cortex.tools.execution.pre_commit_tools_execute_checks import (
            try_skip_clean_checks,
        )

        _ = _make_tracker(tmp_path)
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            result = await try_skip_clean_checks(
                [PreCommitCheck.TYPE_CHECK, PreCommitCheck.TEST_NAMING],
                None,
            )
        assert result is None


# --- record_phase_a_fingerprint --------------------------------------------


class TestRecordPhaseAFingerprint:
    def test_records_on_pass(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_phase_dispatch import (
            record_phase_a_fingerprint,
        )

        result = cast(ModelDict, {"preflight_passed": True, "status": "success"})
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            record_phase_a_fingerprint(result, tmp_path)
        assert PipelineDirtyTracker.get_instance().is_active

    def test_inactive_on_fail(self, tmp_path: Path) -> None:
        from cortex.tools.execution.pre_commit_phase_dispatch import (
            record_phase_a_fingerprint,
        )

        result = cast(ModelDict, {"preflight_passed": False, "status": "error"})
        record_phase_a_fingerprint(result, tmp_path)
        assert not PipelineDirtyTracker.get_instance().is_active


# --- SkipDecision ----------------------------------------------------------


class TestSkipDecision:
    def test_fields(self) -> None:
        d = SkipDecision(can_skip=True, reason="test")
        assert d.can_skip is True and d.reason == "test"
