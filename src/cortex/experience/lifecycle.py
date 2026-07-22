"""Node status lifecycle rules for the experience store.

Encodes the ``pending -> running -> committed(completed) | failed`` lifecycle
from the pipeline-resume design plus label conventions used to interpret a
session's append-only node stream as pipeline-phase events.
"""

from __future__ import annotations

from cortex.experience.models import ExperienceNodeStatus

# AI: run-end markers close a "run window" inside a deterministic experience
# session so a restarted run in the same session starts a fresh frontier.
RUN_PSEUDO_PHASE = "pipeline"
RUN_CLEARED_LABEL = "pipeline:cleared"
RUN_ABANDONED_LABEL = "pipeline:abandoned"
RUN_END_LABELS: frozenset[str] = frozenset({RUN_CLEARED_LABEL, RUN_ABANDONED_LABEL})

# AI: quality-gate nodes score a phase; they are not phases themselves.
NON_PHASE_LABELS: frozenset[str] = frozenset({"quality-gate"})

_NODE_TRANSITIONS: dict[ExperienceNodeStatus, frozenset[ExperienceNodeStatus]] = {
    ExperienceNodeStatus.PENDING: frozenset(
        {ExperienceNodeStatus.RUNNING, ExperienceNodeStatus.FAILED}
    ),
    ExperienceNodeStatus.RUNNING: frozenset(
        {ExperienceNodeStatus.COMPLETED, ExperienceNodeStatus.FAILED}
    ),
    ExperienceNodeStatus.COMPLETED: frozenset(),
    ExperienceNodeStatus.FAILED: frozenset(),
}


def is_terminal(status: ExperienceNodeStatus) -> bool:
    """Return True when the status ends a node's lifecycle."""
    return not _NODE_TRANSITIONS[status]


def can_transition(current: ExperienceNodeStatus, new: ExperienceNodeStatus) -> bool:
    """Strict per-node lifecycle: pending -> running -> completed | failed."""
    return new in _NODE_TRANSITIONS[current]


def can_record_event(
    previous: ExperienceNodeStatus | None, new: ExperienceNodeStatus
) -> bool:
    """Event-stream rule: PENDING may only open a phase's event stream.

    Later events may legally re-run a phase (``running`` after a terminal
    status when a phase is retried) or re-report terminals (result rewrite),
    so only a late ``pending`` event is rejected.
    """
    if previous is None:
        return True
    return new is not ExperienceNodeStatus.PENDING


def is_run_end(label: str | None) -> bool:
    """Return True when the node label marks the end of a run window."""
    return label in RUN_END_LABELS


def phase_from_label(label: str | None) -> str | None:
    """Extract the phase token from a ``{phase}:{status}`` node label.

    Returns None for gate nodes and labels without a phase component.
    """
    if not label or label in NON_PHASE_LABELS:
        return None
    phase = label.rsplit(":", 1)[0]
    return phase or None
