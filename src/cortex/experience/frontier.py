"""Pure frontier computations over a session's ordered node stream."""

from __future__ import annotations

from datetime import UTC, datetime

from cortex.experience.lifecycle import (
    RUN_PSEUDO_PHASE,
    is_run_end,
    phase_from_label,
)
from cortex.experience.models import ExperienceNode, ExperienceNodeStatus
from cortex.experience.query_models import FrontierView


def run_window(nodes: list[ExperienceNode]) -> list[ExperienceNode]:
    """Return nodes after the last run-end marker (the current run's events)."""
    for index in range(len(nodes) - 1, -1, -1):
        if is_run_end(nodes[index].label):
            return nodes[index + 1 :]
    return nodes


def _event_phase(node: ExperienceNode) -> str | None:
    phase = phase_from_label(node.label)
    if phase is None or phase == RUN_PSEUDO_PHASE:
        return None
    return phase


def completed_phases(nodes: list[ExperienceNode]) -> list[str]:
    """Phases whose final event in the window is COMPLETED, in first-seen order."""
    order: list[str] = []
    last_status: dict[str, ExperienceNodeStatus] = {}
    for node in nodes:
        phase = _event_phase(node)
        if phase is None:
            continue
        if phase not in last_status:
            order.append(phase)
        last_status[phase] = node.status
    return [
        phase for phase in order if last_status[phase] is ExperienceNodeStatus.COMPLETED
    ]


def last_committed(nodes: list[ExperienceNode]) -> ExperienceNode | None:
    """Deepest COMPLETED node in the window (the resumable frontier)."""
    for node in reversed(nodes):
        if node.status is ExperienceNodeStatus.COMPLETED:
            return node
    return None


def frontier_phase(nodes: list[ExperienceNode]) -> str | None:
    """Phase of the deepest phase-bearing node in the window."""
    for node in reversed(nodes):
        phase = _event_phase(node)
        if phase is not None:
            return phase
    return None


def frontier_view(session_id: str, nodes: list[ExperienceNode]) -> FrontierView | None:
    """Build the frontier view for one session's current run window."""
    window = run_window(nodes)
    if not window:
        return None
    return FrontierView(
        session_id=session_id,
        latest=window[-1],
        last_committed=last_committed(window),
        completed_phases=completed_phases(window),
        frontier_phase=frontier_phase(window),
    )


def age_seconds(created_at: str, now: datetime | None = None) -> float:
    """Age of an ISO timestamp in seconds (naive stamps assumed UTC)."""
    moment = datetime.fromisoformat(created_at)
    if moment.tzinfo is None:
        # BELIEF: store timestamps come from datetime.now(UTC); naive values
        # in legacy rows are treated as UTC rather than local time.
        moment = moment.replace(tzinfo=UTC)
    reference = now if now is not None else datetime.now(UTC)
    return max(0.0, (reference - moment).total_seconds())
