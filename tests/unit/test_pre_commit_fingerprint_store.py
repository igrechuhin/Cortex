"""Tests for Phase A fingerprint persistence and per-check skipping.

The Phase A gate records its fingerprint in the MCP server process, but the
checks run in a detached worker with a fresh interpreter. These tests cover
the file round-trip that makes the worker see Phase A's state, the guards
that stop a stale fingerprint from skipping real checks, and the per-check
partition that lets an always-run check coexist with skipped ones.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from cortex.tools.execution.pre_commit_dirty_state import (
    PipelineDirtyTracker,
    PipelineFingerprint,
    partition_skippable_checks,
)
from cortex.tools.execution.pre_commit_fingerprint_store import (
    PersistedFingerprint,
    clear_phase_a_fingerprint,
    fingerprint_path,
    load_fingerprint_record,
)

_HASH_TARGET = "cortex.tools.execution.pre_commit_dirty_state.compute_git_file_hash"
_HEAD_TARGET = "cortex.tools.execution.pre_commit_fingerprint_store.git_head"

_FP_BASE = PipelineFingerprint("abc123", "def456", 5, 10)
_FP_SRC_CHANGED = PipelineFingerprint("xyz789", "changed", 6, 12)
_FP_DOCS_ONLY = PipelineFingerprint("abc123", "changed", 5, 12)

_MIXED_CHECKS = ["tests", "type_check", "spelling", "eval_fast"]


def _record_phase_a(root: Path, fingerprint: PipelineFingerprint) -> None:
    """Record a passing Phase A, persisting the given fingerprint."""
    tracker = PipelineDirtyTracker.get_instance()
    with patch(_HASH_TARGET, return_value=fingerprint):
        tracker.record_phase_a(root, True)


def _simulate_fresh_process() -> None:
    """Drop the in-memory singleton, keeping persisted state (detached worker)."""
    PipelineDirtyTracker._instance = None  # pyright: ignore[reportPrivateUsage]


class TestFingerprintRoundTrip:
    """Persisted fingerprint must survive into a fresh interpreter."""

    def test_fresh_process_sees_persisted_fingerprint(self, tmp_path: Path) -> None:
        # Arrange: Phase A passes and persists its fingerprint, then the
        # recording process disappears (detached worker starts cold).
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
            _simulate_fresh_process()

            # Act: the worker partitions with an unchanged source hash.
            with patch(_HASH_TARGET, return_value=_FP_DOCS_ONLY):
                to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert to_run == []
        assert "tests" in skipped
        PipelineDirtyTracker.reset(tmp_path)

    def test_record_writes_readable_file(self, tmp_path: Path) -> None:
        # Arrange / Act
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
            record = load_fingerprint_record(tmp_path)

        # Assert
        assert fingerprint_path(tmp_path).exists()
        assert record is not None
        assert record.source_hash == _FP_BASE.source_hash
        assert record.head == "head1"
        PipelineDirtyTracker.reset(tmp_path)

    def test_source_change_blocks_skip_across_processes(self, tmp_path: Path) -> None:
        # Arrange
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
            _simulate_fresh_process()

            # Act: source hash differs from the persisted Phase A hash.
            with patch(_HASH_TARGET, return_value=_FP_SRC_CHANGED):
                to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert to_run == ["tests"]
        assert skipped == {}
        PipelineDirtyTracker.reset(tmp_path)


class TestStaleFingerprintNeverSkips:
    """Any doubt about the persisted record must force checks to run."""

    def test_no_file_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange
        _simulate_fresh_process()

        # Act
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert to_run == ["tests"]
        assert skipped == {}

    def test_cleared_fingerprint_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
        clear_phase_a_fingerprint(tmp_path)
        _simulate_fresh_process()

        # Act
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert not fingerprint_path(tmp_path).exists()
        assert to_run == ["tests"]
        assert skipped == {}

    def test_reset_removes_persisted_file(self, tmp_path: Path) -> None:
        # Arrange
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)

        # Act
        PipelineDirtyTracker.reset()

        # Assert
        assert not fingerprint_path(tmp_path).exists()

    def test_failed_phase_a_removes_persisted_file(self, tmp_path: Path) -> None:
        # Arrange
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)

            # Act
            tracker = PipelineDirtyTracker.get_instance()
            tracker.record_phase_a(tmp_path, False)

        # Assert
        assert not fingerprint_path(tmp_path).exists()
        PipelineDirtyTracker.reset(tmp_path)

    def test_moved_head_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange: recorded at head1, but HEAD is now head2 (a commit landed).
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
        _simulate_fresh_process()

        # Act
        with (
            patch(_HEAD_TARGET, return_value="head2"),
            patch(_HASH_TARGET, return_value=_FP_BASE),
        ):
            to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert to_run == ["tests"]
        assert skipped == {}
        PipelineDirtyTracker.reset(tmp_path)

    def test_expired_record_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange: a fingerprint older than the TTL.
        expired = PersistedFingerprint(
            source_hash=_FP_BASE.source_hash,
            all_files_hash=_FP_BASE.all_files_hash,
            source_file_count=5,
            total_file_count=10,
            head="head1",
            recorded_at=time.time() - 7200.0,
        )
        _ = fingerprint_path(tmp_path).write_text(expired.model_dump_json())
        _simulate_fresh_process()

        # Act
        with (
            patch(_HEAD_TARGET, return_value="head1"),
            patch(_HASH_TARGET, return_value=_FP_BASE),
        ):
            to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert to_run == ["tests"]
        assert skipped == {}

    def test_corrupt_record_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange
        _ = fingerprint_path(tmp_path).write_text("{not json")
        _simulate_fresh_process()

        # Act
        with patch(_HASH_TARGET, return_value=_FP_BASE):
            to_run, skipped = partition_skippable_checks(tmp_path, ["tests"])

        # Assert
        assert load_fingerprint_record(tmp_path) is None
        assert to_run == ["tests"]
        assert skipped == {}

    def test_schema_drift_means_no_skip(self, tmp_path: Path) -> None:
        # Arrange: a record missing required fields.
        _ = fingerprint_path(tmp_path).write_text(json.dumps({"source_hash": "abc123"}))
        _simulate_fresh_process()

        # Act
        record = load_fingerprint_record(tmp_path)

        # Assert
        assert record is None


class TestSourceHashTracksContent:
    """The source hash must change when file bytes change, not just names."""

    def test_content_edit_changes_hash(self, tmp_path: Path) -> None:
        # Arrange: one changed source file, same name across both snapshots.
        from cortex.tools.execution.pre_commit_dirty_state import compute_git_file_hash

        src = tmp_path / "mod.py"
        _ = src.write_text("x = 1\n")
        subproc = "cortex.tools.execution.pre_commit_dirty_state.subprocess.run"

        class _R:
            returncode = 0
            stdout = "M\tmod.py\n"

        # Act
        with patch(subproc, return_value=_R()):
            before = compute_git_file_hash(tmp_path)
            _ = src.write_text("x = 2\n")
            after = compute_git_file_hash(tmp_path)

        # Assert: an autofix-style rewrite must invalidate the fingerprint.
        assert before.source_hash != after.source_hash

    def test_identical_content_keeps_hash(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.tools.execution.pre_commit_dirty_state import compute_git_file_hash

        src = tmp_path / "mod.py"
        _ = src.write_text("x = 1\n")
        subproc = "cortex.tools.execution.pre_commit_dirty_state.subprocess.run"

        class _R:
            returncode = 0
            stdout = "M\tmod.py\n"

        # Act
        with patch(subproc, return_value=_R()):
            before = compute_git_file_hash(tmp_path)
            after = compute_git_file_hash(tmp_path)

        # Assert
        assert before.source_hash == after.source_hash


class TestPerCheckPartition:
    """Always-run checks must not drag skippable checks along with them."""

    def test_mixed_checks_skip_only_source_dependent(self, tmp_path: Path) -> None:
        # Arrange: source hash unchanged since Phase A, docs changed.
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
            _simulate_fresh_process()

            # Act
            with patch(_HASH_TARGET, return_value=_FP_DOCS_ONLY):
                to_run, skipped = partition_skippable_checks(tmp_path, _MIXED_CHECKS)

        # Assert: the expensive source-dependent checks are skipped, the
        # always-run ones still execute.
        assert sorted(skipped) == ["tests", "type_check"]
        assert to_run == ["spelling", "eval_fast"]
        PipelineDirtyTracker.reset(tmp_path)

    def test_dirty_marked_check_still_runs(self, tmp_path: Path) -> None:
        # Arrange
        with patch(_HEAD_TARGET, return_value="head1"):
            _record_phase_a(tmp_path, _FP_BASE)
            tracker = PipelineDirtyTracker.get_instance()
            tracker.mark_dirty("tests")

            # Act
            with patch(_HASH_TARGET, return_value=_FP_DOCS_ONLY):
                to_run, skipped = partition_skippable_checks(
                    tmp_path, ["tests", "type_check"]
                )

        # Assert
        assert to_run == ["tests"]
        assert sorted(skipped) == ["type_check"]
        PipelineDirtyTracker.reset(tmp_path)
