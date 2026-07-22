"""Unit tests for pure frontier computations over node streams."""

from __future__ import annotations

from datetime import UTC, datetime

from cortex.experience.frontier import (
    age_seconds,
    completed_phases,
    frontier_phase,
    frontier_view,
    last_committed,
    run_window,
)
from cortex.experience.lifecycle import RUN_CLEARED_LABEL
from cortex.experience.models import ExperienceNode, ExperienceNodeStatus


def _node(
    label: str | None,
    status: ExperienceNodeStatus,
    step: int,
) -> ExperienceNode:
    return ExperienceNode(
        session_id="sess", label=label, status=status, step_number=step
    )


def test_run_window_returns_nodes_after_last_run_end() -> None:
    # Arrange
    nodes = [
        _node("checks:completed", ExperienceNodeStatus.COMPLETED, 1),
        _node(RUN_CLEARED_LABEL, ExperienceNodeStatus.COMPLETED, 2),
        _node("select:completed", ExperienceNodeStatus.COMPLETED, 3),
    ]

    # Act
    window = run_window(nodes)

    # Assert
    assert [node.step_number for node in window] == [3]


def test_run_window_without_marker_returns_all_nodes() -> None:
    # Arrange
    nodes = [_node("select:running", ExperienceNodeStatus.RUNNING, 1)]

    # Act / Assert
    assert run_window(nodes) == nodes
    assert run_window([]) == []


def test_completed_phases_uses_final_event_per_phase() -> None:
    # Arrange
    nodes = [
        _node("select:running", ExperienceNodeStatus.RUNNING, 1),
        _node("select:completed", ExperienceNodeStatus.COMPLETED, 2),
        _node("code:running", ExperienceNodeStatus.RUNNING, 3),
        _node("code:failed", ExperienceNodeStatus.FAILED, 4),
        _node("quality-gate", ExperienceNodeStatus.COMPLETED, 5),
    ]

    # Act / Assert
    assert completed_phases(nodes) == ["select"]


def test_last_committed_returns_deepest_completed_node() -> None:
    # Arrange
    nodes = [
        _node("select:completed", ExperienceNodeStatus.COMPLETED, 1),
        _node("code:running", ExperienceNodeStatus.RUNNING, 2),
    ]

    # Act
    committed = last_committed(nodes)

    # Assert
    assert committed is not None
    assert committed.label == "select:completed"
    assert last_committed([]) is None


def test_frontier_phase_skips_gate_nodes() -> None:
    # Arrange
    nodes = [
        _node("code:completed", ExperienceNodeStatus.COMPLETED, 1),
        _node("quality-gate", ExperienceNodeStatus.COMPLETED, 2),
    ]

    # Act / Assert
    assert frontier_phase(nodes) == "code"
    assert frontier_phase([]) is None


def test_frontier_view_builds_full_projection() -> None:
    # Arrange
    nodes = [
        _node("select:completed", ExperienceNodeStatus.COMPLETED, 1),
        _node("code:running", ExperienceNodeStatus.RUNNING, 2),
    ]

    # Act
    view = frontier_view("sess", nodes)

    # Assert
    assert view is not None
    assert view.latest.label == "code:running"
    assert view.completed_phases == ["select"]
    assert view.frontier_phase == "code"
    assert view.last_committed is not None
    assert view.last_committed.label == "select:completed"


def test_frontier_view_is_none_after_run_end() -> None:
    # Arrange
    nodes = [
        _node("code:completed", ExperienceNodeStatus.COMPLETED, 1),
        _node(RUN_CLEARED_LABEL, ExperienceNodeStatus.COMPLETED, 2),
    ]

    # Act / Assert
    assert frontier_view("sess", nodes) is None
    assert frontier_view("sess", []) is None


def test_age_seconds_handles_tz_aware_and_naive_stamps() -> None:
    # Arrange
    now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)

    # Act / Assert
    assert age_seconds("2026-07-20T11:59:00+00:00", now) == 60.0
    assert age_seconds("2026-07-20T11:58:00", now) == 120.0
    # AI: clock skew must never produce a negative age.
    assert age_seconds("2026-07-20T12:01:00+00:00", now) == 0.0
