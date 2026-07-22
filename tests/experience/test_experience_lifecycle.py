"""Unit tests for node-status lifecycle rules and label helpers."""

from __future__ import annotations

import pytest

from cortex.experience.lifecycle import (
    RUN_ABANDONED_LABEL,
    RUN_CLEARED_LABEL,
    can_record_event,
    can_transition,
    is_run_end,
    is_terminal,
    phase_from_label,
)
from cortex.experience.models import ExperienceNodeStatus


@pytest.mark.parametrize(
    ("current", "new", "expected"),
    [
        (ExperienceNodeStatus.PENDING, ExperienceNodeStatus.RUNNING, True),
        (ExperienceNodeStatus.PENDING, ExperienceNodeStatus.FAILED, True),
        (ExperienceNodeStatus.PENDING, ExperienceNodeStatus.COMPLETED, False),
        (ExperienceNodeStatus.RUNNING, ExperienceNodeStatus.COMPLETED, True),
        (ExperienceNodeStatus.RUNNING, ExperienceNodeStatus.FAILED, True),
        (ExperienceNodeStatus.RUNNING, ExperienceNodeStatus.PENDING, False),
        (ExperienceNodeStatus.COMPLETED, ExperienceNodeStatus.RUNNING, False),
        (ExperienceNodeStatus.FAILED, ExperienceNodeStatus.RUNNING, False),
    ],
)
def test_can_transition_enforces_lifecycle(
    current: ExperienceNodeStatus, new: ExperienceNodeStatus, expected: bool
) -> None:
    # Arrange / Act / Assert
    assert can_transition(current, new) is expected


def test_terminal_states_are_completed_and_failed() -> None:
    # Arrange / Act / Assert
    assert is_terminal(ExperienceNodeStatus.COMPLETED) is True
    assert is_terminal(ExperienceNodeStatus.FAILED) is True
    assert is_terminal(ExperienceNodeStatus.PENDING) is False
    assert is_terminal(ExperienceNodeStatus.RUNNING) is False


def test_can_record_event_rejects_late_pending_only() -> None:
    # Arrange / Act / Assert
    assert can_record_event(None, ExperienceNodeStatus.PENDING) is True
    assert can_record_event(None, ExperienceNodeStatus.FAILED) is True
    assert (
        can_record_event(ExperienceNodeStatus.RUNNING, ExperienceNodeStatus.PENDING)
        is False
    )
    assert (
        can_record_event(ExperienceNodeStatus.COMPLETED, ExperienceNodeStatus.RUNNING)
        is True
    )


def test_is_run_end_matches_marker_labels() -> None:
    # Arrange / Act / Assert
    assert is_run_end(RUN_CLEARED_LABEL) is True
    assert is_run_end(RUN_ABANDONED_LABEL) is True
    assert is_run_end("checks:completed") is False
    assert is_run_end(None) is False


def test_phase_from_label_extracts_phase_token() -> None:
    # Arrange / Act / Assert
    assert phase_from_label("checks:completed") == "checks"
    assert phase_from_label("final-gate:running") == "final-gate"
    assert phase_from_label("quality-gate") is None
    assert phase_from_label(None) is None
    assert phase_from_label(":running") is None
