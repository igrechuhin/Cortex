"""Tests for the task-level no-progress loop detector.

Covers: AttemptRecord model validation, detect_no_progress true positive
(N identical outcomes on same target trips), true negative (different
target resets the count), true negative (outcome changes between attempts
on same target does not trip), and the JSON parsing helpers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.core.no_progress_monitor import (
    DEFAULT_NO_PROGRESS_THRESHOLD,
    AttemptRecord,
    NoProgressResult,
    attempt_records_from_json,
    build_report_message,
    detect_no_progress,
    extract_attempt_history,
)


def _record(target: str, outcome: str, attempt: int) -> AttemptRecord:
    return AttemptRecord(
        target=target, outcome_signature=outcome, attempt_number=attempt
    )


class TestAttemptRecordModel:
    def test_valid_record_constructs(self) -> None:
        # Arrange / Act
        record = _record("tests/test_foo.py::test_bar", "AssertionError: shape", 1)

        # Assert
        assert record.target == "tests/test_foo.py::test_bar"
        assert record.outcome_signature == "AssertionError: shape"
        assert record.attempt_number == 1

    def test_empty_target_rejected(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            _ = AttemptRecord(target="", outcome_signature="err", attempt_number=1)

    def test_empty_outcome_signature_rejected(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            _ = AttemptRecord(target="t", outcome_signature="", attempt_number=1)

    def test_zero_attempt_number_rejected(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValidationError):
            _ = AttemptRecord(target="t", outcome_signature="err", attempt_number=0)

    def test_extra_field_rejected(self) -> None:
        # Arrange
        payload = {
            "target": "t",
            "outcome_signature": "err",
            "attempt_number": 1,
            "unexpected": "field",
        }

        # Act / Assert
        with pytest.raises(ValidationError):
            _ = AttemptRecord.model_validate(payload)

    def test_record_is_frozen(self) -> None:
        # Arrange
        record = _record("t", "err", 1)

        # Act / Assert
        with pytest.raises(ValidationError):
            record.target = "other"  # type: ignore[misc]


class TestDetectNoProgressTruePositive:
    def test_n_identical_outcomes_on_same_target_trips(self) -> None:
        # Arrange
        records = [
            _record("tests/test_foo.py::test_bar", "AssertionError: X != Y", 1),
            _record("tests/test_foo.py::test_bar", "AssertionError: X != Y", 2),
            _record("tests/test_foo.py::test_bar", "AssertionError: X != Y", 3),
        ]

        # Act
        result = detect_no_progress(records, threshold=3)

        # Assert
        assert result.tripped is True
        assert result.target == "tests/test_foo.py::test_bar"
        assert result.outcome_signature == "AssertionError: X != Y"
        assert result.consecutive_count == 3

    def test_default_threshold_matches_mcp_circuit_breaker_convention(self) -> None:
        # Arrange
        assert DEFAULT_NO_PROGRESS_THRESHOLD == 3
        records = [_record("t", "err", i) for i in range(1, 4)]

        # Act
        result = detect_no_progress(records)

        # Assert
        assert result.tripped is True

    def test_more_than_threshold_still_trips_on_tail(self) -> None:
        # Arrange: 4 identical attempts, threshold 3 — only the tail matters.
        records = [_record("t", "err", i) for i in range(1, 5)]

        # Act
        result = detect_no_progress(records, threshold=3)

        # Assert
        assert result.tripped is True
        assert result.consecutive_count == 3


class TestDetectNoProgressTrueNegatives:
    def test_fewer_than_threshold_attempts_does_not_trip(self) -> None:
        # Arrange
        records = [
            _record("t", "err", 1),
            _record("t", "err", 2),
        ]

        # Act
        result = detect_no_progress(records, threshold=3)

        # Assert
        assert result.tripped is False
        assert result.consecutive_count == 0

    def test_different_target_resets_the_count(self) -> None:
        # Arrange: two attempts on target A, then a switch to target B.
        records = [
            _record("A", "err", 1),
            _record("A", "err", 2),
            _record("B", "different-err", 1),
        ]

        # Act
        result = detect_no_progress(records, threshold=3)

        # Assert
        assert result.tripped is False

    def test_outcome_change_on_same_target_does_not_trip(self) -> None:
        # Arrange: same target throughout, but the outcome shape changes.
        records = [
            _record("A", "AssertionError: X != Y", 1),
            _record("A", "TypeError: unexpected kwarg", 2),
            _record("A", "AssertionError: X != Y", 3),
        ]

        # Act
        result = detect_no_progress(records, threshold=3)

        # Assert
        assert result.tripped is False

    def test_empty_records_does_not_trip(self) -> None:
        # Arrange / Act
        result = detect_no_progress([], threshold=3)

        # Assert
        assert result.tripped is False

    def test_invalid_threshold_raises(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValueError, match="threshold must be >= 1"):
            _ = detect_no_progress([_record("t", "err", 1)], threshold=0)


class TestAttemptRecordsFromJson:
    def test_parses_valid_list(self) -> None:
        # Arrange
        raw = [
            {"target": "t", "outcome_signature": "err", "attempt_number": 1},
            {"target": "t", "outcome_signature": "err", "attempt_number": 2},
        ]

        # Act
        records = attempt_records_from_json(raw)

        # Assert
        assert records == [_record("t", "err", 1), _record("t", "err", 2)]

    def test_non_list_input_returns_empty(self) -> None:
        # Arrange / Act / Assert
        assert attempt_records_from_json({"not": "a list"}) == []
        assert attempt_records_from_json(None) == []
        assert attempt_records_from_json("string") == []

    def test_skips_malformed_entries(self) -> None:
        # Arrange
        raw = [
            {"target": "t", "outcome_signature": "err", "attempt_number": 1},
            {"target": "", "outcome_signature": "err", "attempt_number": 2},
            "not-a-dict",
            {"missing": "fields"},
        ]

        # Act
        records = attempt_records_from_json(raw)

        # Assert
        assert records == [_record("t", "err", 1)]


class TestExtractAttemptHistory:
    def test_extracts_from_phase_payload(self) -> None:
        # Arrange
        payload: dict[str, object] = {
            "status": "running",
            "attempt_history": [
                {"target": "t", "outcome_signature": "err", "attempt_number": 1},
            ],
        }

        # Act
        records = extract_attempt_history(payload)

        # Assert
        assert records == [_record("t", "err", 1)]

    def test_missing_attempt_history_returns_empty(self) -> None:
        # Arrange
        payload: dict[str, object] = {"status": "running"}

        # Act / Assert
        assert extract_attempt_history(payload) == []


class TestBuildReportMessage:
    def test_includes_target_threshold_and_outcome(self) -> None:
        # Arrange
        result = NoProgressResult(
            tripped=True,
            target="tests/test_foo.py::test_bar",
            outcome_signature="AssertionError: X != Y",
            consecutive_count=3,
        )

        # Act
        message = build_report_message(result, threshold=3)

        # Assert
        assert "3 consecutive attempts" in message
        assert "tests/test_foo.py::test_bar" in message
        assert "AssertionError: X != Y" in message
        assert "No-progress monitor" in message
