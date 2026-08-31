"""Best-effort experience recording hooks for pipeline instrumentation.

Called from ``pipeline_handoff`` phase transitions and the quality-gate
result path. Recording is a side effect of normal pipeline execution and
MUST never break the pipeline: every public function swallows storage
errors and logs them at WARNING with the session id as trace id.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from cortex.experience.artifacts import store_artifact
from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.embedding_models import TaskEmbeddingRecord
from cortex.experience.encoder import EncoderProtocol, HashingEncoder
from cortex.experience.frontier import run_window
from cortex.experience.lifecycle import (
    RUN_ABANDONED_LABEL,
    RUN_CLEARED_LABEL,
    can_record_event,
    phase_from_label,
)
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.store_core import ExperienceStoreCore

logger = logging.getLogger(__name__)

RECORDING_ENV_FLAG = "CORTEX_EXPERIENCE_RECORDING"
EXPERIENCE_DB_RELATIVE_POSIX = ".cortex/experience/experience.db"

_DISABLED_VALUES = frozenset({"0", "false", "off", "no"})

# AI: module-level counter surfaces silent recording failures to health checks.
_failure_count = 0

# AI: one process-wide default encoder instance; HashingEncoder is stateless
# aside from (dim, version) so sharing it across recording calls avoids
# reconstructing it per task while staying trivially DI-swappable via the
# private `_task_encoder` module attribute (tests monkeypatch this symbol).
_task_encoder: EncoderProtocol = HashingEncoder()


def recording_enabled(override: bool | None = None) -> bool:
    """Return True when experience recording is on (default enabled)."""
    if override is not None:
        return override
    raw = os.environ.get(RECORDING_ENV_FLAG, "1")
    return raw.strip().lower() not in _DISABLED_VALUES


def recording_failure_count() -> int:
    """Return the number of recording failures since process start."""
    return _failure_count


def experience_db_path(project_root: Path) -> Path:
    return project_root / EXPERIENCE_DB_RELATIVE_POSIX


def _deterministic_id(kind: str, *parts: str) -> str:
    key = "\x1f".join([kind, *parts])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def experience_session_id(session_id: str, pipeline: str) -> str:
    """Deterministic experience-session id for a (session, pipeline) pair."""
    return _deterministic_id("session", session_id, pipeline)


def _node_status(status: str) -> ExperienceNodeStatus:
    lowered = status.strip().lower()
    if lowered == ExperienceNodeStatus.PENDING.value:
        return ExperienceNodeStatus.PENDING
    if lowered == ExperienceNodeStatus.RUNNING.value:
        return ExperienceNodeStatus.RUNNING
    if lowered == ExperienceNodeStatus.FAILED.value:
        return ExperienceNodeStatus.FAILED
    return ExperienceNodeStatus.COMPLETED


def _last_phase_event_status(
    core: ExperienceStoreCore, experience_session_id: str, phase: str
) -> ExperienceNodeStatus | None:
    """Status of the phase's most recent event in the current run window."""
    window = run_window(core.list_nodes(experience_session_id))
    for node in reversed(window):
        if phase_from_label(node.label) == phase:
            return node.status
    return None


def _index_task_embedding_best_effort(
    core: ExperienceStoreCore, task: ExperienceTask
) -> None:
    """Embed and upsert the task's spec text; never raises past the caller.

    Idempotent (upsert on task_id), so re-invoking on every ``ensure_lineage``
    call for an already-indexed task is cheap and safe.
    """
    try:
        index = EmbeddingIndexCore(core.db_path)
        vector = _task_encoder.encode(task.spec)
        _ = index.upsert(
            TaskEmbeddingRecord(
                task_id=task.id,
                vector=vector,
                dim=_task_encoder.dim,
                encoder_version=_task_encoder.version,
            )
        )
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(task.id, "index_task_embedding", exc)


# AI: public so predictions.py can reuse the same task/session rows rather
# than opening a second, divergent lineage for the same pipeline run.
def ensure_lineage(
    core: ExperienceStoreCore, session_id: str, pipeline: str
) -> ExperienceSession:
    """Create-or-reuse the task and session rows for a pipeline run."""
    task = ExperienceTask(
        id=_deterministic_id("task", pipeline),
        spec=f"pipeline:{pipeline}",
        success_metric="quality gate preflight_passed",
    )
    _ = core.create_task(task)
    _index_task_embedding_best_effort(core, task)
    session = ExperienceSession(
        id=_deterministic_id("session", session_id, pipeline),
        task_id=task.id,
        algorithm=pipeline,
        owner=session_id,
    )
    return core.create_session(session)


# AI: public for predictions.py — every recorder appends through one place so
# step_number and parent links stay consistent across recording kinds.
def append_child_node(
    core: ExperienceStoreCore,
    experience_session_id: str,
    status: ExperienceNodeStatus,
    label: str,
    fitness: float | None = None,
    artifact_ref: str | None = None,
) -> ExperienceNode:
    parent = core.latest_node(experience_session_id)
    node = ExperienceNode(
        parent_id=parent.id if parent else None,
        session_id=experience_session_id,
        status=status,
        step_number=(parent.step_number + 1) if parent else 1,
        label=label,
        fitness=fitness,
        artifact_ref=artifact_ref,
    )
    return core.append_node(node)


def record_phase_event(
    project_root: Path,
    session_id: str,
    pipeline: str,
    phase: str,
    status: str,
    enabled: bool | None = None,
) -> str | None:
    """Record one node per phase event; drops lifecycle violations. Best-effort."""
    if not recording_enabled(enabled):
        return None
    try:
        core = ExperienceStoreCore(experience_db_path(project_root))
        session = ensure_lineage(core, session_id, pipeline)
        new_status = _node_status(status)
        allowed = _event_transition_allowed(
            core, session_id, session.id, phase, new_status
        )
        if not allowed:
            return None
        node = append_child_node(
            core,
            experience_session_id=session.id,
            status=new_status,
            label=f"{phase}:{status}",
        )
        return node.id
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "record_phase_event", exc)
        return None


def _event_transition_allowed(
    core: ExperienceStoreCore,
    trace_id: str,
    experience_session_id: str,
    phase: str,
    new_status: ExperienceNodeStatus,
) -> bool:
    """Validate the phase event against its stream; warn on rejection."""
    previous = _last_phase_event_status(core, experience_session_id, phase)
    if can_record_event(previous, new_status):
        return True
    logger.warning(
        "experience recording rejected transition: trace_id=%s phase=%s %s -> %s",
        trace_id,
        phase,
        previous.value if previous else None,
        new_status.value,
    )
    return False


def record_run_end(
    project_root: Path,
    session_id: str,
    pipeline: str,
    reason: str,
    enabled: bool | None = None,
) -> str | None:
    """Close the current run window (reason: "cleared" or "abandoned").

    Cleared runs ended normally (pipeline_handoff clear); abandoned runs
    expired past the resume TTL. Best-effort; skips when nothing was
    recorded for the project yet.
    """
    if not recording_enabled(enabled):
        return None
    if not experience_db_path(project_root).exists():
        return None
    try:
        core = ExperienceStoreCore(experience_db_path(project_root))
        session = ensure_lineage(core, session_id, pipeline)
        node = _append_run_end_node(core, session.id, reason)
        return node.id if node is not None else None
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "record_run_end", exc)
        return None


def _append_run_end_node(
    core: ExperienceStoreCore, experience_session_id: str, reason: str
) -> ExperienceNode | None:
    """Append the run-end marker when a run window is open."""
    if not run_window(core.list_nodes(experience_session_id)):
        return None
    cleared = reason.strip().lower() == "cleared"
    return append_child_node(
        core,
        experience_session_id=experience_session_id,
        status=(
            ExperienceNodeStatus.COMPLETED if cleared else ExperienceNodeStatus.FAILED
        ),
        label=RUN_CLEARED_LABEL if cleared else RUN_ABANDONED_LABEL,
    )


def record_gate_fitness(
    project_root: Path,
    session_id: str,
    pipeline: str,
    passed: bool,
    summary: str,
    enabled: bool | None = None,
) -> str | None:
    """Attach a quality-gate outcome as fitness on the producing node.

    The gate result belongs to the most recent node of the current pipeline
    session; when that node already carries a fitness (gate re-run) a child
    node is appended instead so every gate invocation maps to exactly one
    node. Best-effort.
    """
    if not recording_enabled(enabled):
        return None
    try:
        core = ExperienceStoreCore(experience_db_path(project_root))
        session = ensure_lineage(core, session_id, pipeline)
        fitness = 1.0 if passed else 0.0
        artifact_ref = store_artifact(project_root, "quality-gate", summary)
        return _attach_fitness(core, session.id, passed, fitness, artifact_ref)
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "record_gate_fitness", exc)
        return None


def _attach_fitness(
    core: ExperienceStoreCore,
    experience_session_id: str,
    passed: bool,
    fitness: float,
    artifact_ref: str,
) -> str:
    status = ExperienceNodeStatus.COMPLETED if passed else ExperienceNodeStatus.FAILED
    latest = core.latest_node(experience_session_id)
    if latest is not None and latest.fitness is None:
        _ = core.set_fitness(latest.id, fitness)
        _ = core.link_artifact(latest.id, artifact_ref)
        return latest.id
    node = append_child_node(
        core,
        experience_session_id=experience_session_id,
        status=status,
        label="quality-gate",
        fitness=fitness,
        artifact_ref=artifact_ref,
    )
    return node.id


# AI: public so every best-effort recorder increments the same failure counter
# that health checks read; a silent swallow elsewhere would hide breakage.
def warn_recording_failure(session_id: str, operation: str, exc: Exception) -> None:
    global _failure_count
    _failure_count += 1
    logger.warning(
        "experience recording failed (best-effort): op=%s trace_id=%s error=%s",
        operation,
        session_id,
        exc,
    )
