"""
Unit tests for commit_workflow_model module.

Tests step metadata, parallel block, and sequential ranges for commit workflow.
"""

import pytest
from pydantic import ValidationError

from cortex.validation.commit_workflow_model import (
    CommitStepMetadata,
    get_commit_steps_metadata,
    get_parallel_block_step_ids,
    get_sequential_step_ranges,
)


class TestGetCommitStepsMetadata:
    """Tests for get_commit_steps_metadata()."""

    def test_returns_fifteen_steps_in_order(self) -> None:
        """Metadata list has 15 steps with ids 0–14 in order."""
        steps = get_commit_steps_metadata()
        assert len(steps) == 15
        for i, meta in enumerate(steps):
            assert meta.step_id == i

    def test_step_names_match_expected_slugs(self) -> None:
        """Step names are expected slugs (error-fixer, timestamp-validator, etc.)."""
        steps = get_commit_steps_metadata()
        expected = [
            "error-fixer",
            "code-formatter",
            "type-checker",
            "quality-checker",
            "test-executor",
            "memory-bank-updater",
            "memory-bank-updater",
            "plan-archiver",
            "plan-archiver",
            "timestamp-validator",
            "roadmap-sync-validator",
            "submodule-handling",
            "final-validation-gate",
            "commit-creation",
            "push-branch",
        ]
        assert [s.name for s in steps] == expected

    def test_steps_9_10_11_can_run_in_parallel(self) -> None:
        """Steps 9, 10, 11 have can_run_in_parallel=True."""
        steps = get_commit_steps_metadata()
        for step_id in (9, 10, 11):
            meta = next(s for s in steps if s.step_id == step_id)
            assert meta.can_run_in_parallel is True
            assert meta.group_id == "validation_parallel_block_9_11"

    def test_all_other_steps_cannot_run_in_parallel(self) -> None:
        """Steps 0–8 and 12–14 have can_run_in_parallel=False and group_id=None."""
        steps = get_commit_steps_metadata()
        sequential_ids = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 14}
        for meta in steps:
            if meta.step_id in sequential_ids:
                assert meta.can_run_in_parallel is False
                assert meta.group_id is None


class TestGetParallelBlockStepIds:
    """Tests for get_parallel_block_step_ids()."""

    def test_returns_nine_ten_eleven(self) -> None:
        """Parallel block is exactly steps 9, 10, 11."""
        assert get_parallel_block_step_ids() == (9, 10, 11)


class TestGetSequentialStepRanges:
    """Tests for get_sequential_step_ranges()."""

    def test_returns_zero_eight_and_twelve_fourteen(self) -> None:
        """Sequential ranges are (0, 8) and (12, 14)."""
        assert get_sequential_step_ranges() == [(0, 8), (12, 14)]

    def test_ranges_cover_all_non_parallel_steps(self) -> None:
        """Sequential ranges cover steps 0–8 and 12–14 with no gap for 9–11."""
        ranges = get_sequential_step_ranges()
        parallel = set(get_parallel_block_step_ids())
        covered: set[int] = set()
        for start, end in ranges:
            for step_id in range(start, end + 1):
                covered.add(step_id)
        assert covered == set(range(15)) - parallel
        assert covered | parallel == set(range(15))


class TestCommitStepMetadataModel:
    """Tests for CommitStepMetadata Pydantic model."""

    def test_model_accepts_valid_fields(self) -> None:
        """CommitStepMetadata accepts step_id, name, can_run_in_parallel, group_id."""
        meta = CommitStepMetadata(
            step_id=9,
            name="timestamp-validator",
            can_run_in_parallel=True,
            group_id="validation_parallel_block_9_11",
        )
        assert meta.step_id == 9
        assert meta.name == "timestamp-validator"
        assert meta.can_run_in_parallel is True
        assert meta.group_id == "validation_parallel_block_9_11"

    def test_group_id_optional(self) -> None:
        """group_id may be None for sequential steps."""
        meta = CommitStepMetadata(
            step_id=0,
            name="error-fixer",
            can_run_in_parallel=False,
            group_id=None,
        )
        assert meta.group_id is None

    def test_model_forbids_extra_fields(self) -> None:
        """CommitStepMetadata forbids extra fields."""
        with pytest.raises(ValidationError):
            _ = CommitStepMetadata(
                step_id=0,
                name="error-fixer",
                can_run_in_parallel=False,
                group_id=None,
                **{"extra": "forbidden"},
            )
