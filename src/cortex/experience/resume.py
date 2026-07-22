"""Resume planning for interrupted pipeline runs (frontier-query recovery).

Recovery is a query, not a checkpoint: the experience store holds every
phase transition, so a crashed pipeline resumes from its last committed
node. The handoff files under ``.cortex/.session`` are treated as a
projection; on mismatch the store wins.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.experience.models import ExperienceNodeStatus
from cortex.experience.query_models import IncompleteRun
from cortex.experience.recorder import (
    experience_db_path,
    experience_session_id,
)
from cortex.experience.store_core import ExperienceStoreCore

logger = logging.getLogger(__name__)

RESUME_TTL_ENV = "CORTEX_RESUME_TTL_SECONDS"
# AI: matches PIPELINE_TTL_SECONDS in pipeline_handoff_io so store and
# handoff-file staleness policies agree by default.
DEFAULT_RESUME_TTL_SECONDS = 4 * 3600.0


class ResumePlan(BaseModel):
    """Continuation instructions derived from the experience-store frontier."""

    resumable: bool
    reason: str = Field(min_length=1)
    pipeline: str = Field(min_length=1)
    session_id: str | None = None
    handoff_dir: str | None = None
    completed_phases: list[str] = Field(default_factory=list)
    frontier_phase: str | None = None
    frontier_status: ExperienceNodeStatus | None = None
    handoff_mismatch: list[str] = Field(default_factory=list)


def resume_ttl_seconds() -> float:
    """Configured resume TTL; runs older than this are abandoned."""
    raw = os.environ.get(RESUME_TTL_ENV, "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_RESUME_TTL_SECONDS
    return value if value > 0 else DEFAULT_RESUME_TTL_SECONDS


def scan_incomplete_runs(
    project_root: Path,
    ttl_seconds: float | None = None,
    now: datetime | None = None,
) -> list[IncompleteRun]:
    """Mark stale runs abandoned, then list fresh incomplete runs.

    Best-effort: returns [] when the store is absent or unreadable so
    session orientation never fails on a broken experience database.
    """
    if not experience_db_path(project_root).exists():
        return []
    ttl = ttl_seconds if ttl_seconds is not None else resume_ttl_seconds()
    try:
        core = ExperienceStoreCore(experience_db_path(project_root))
        _ = core.mark_abandoned_runs(ttl, now)
        return core.incomplete_runs(ttl, now)
    except Exception as exc:  # noqa: BLE001
        logger.warning("incomplete-run scan failed (best-effort): %s", exc)
        return []


def _find_run(
    core: ExperienceStoreCore,
    session_id: str,
    pipeline: str,
    ttl: float,
    now: datetime | None,
) -> IncompleteRun | None:
    """Prefer the current session's run; fall back to the freshest match."""
    runs = core.incomplete_runs(ttl, now)
    own_id = experience_session_id(session_id, pipeline)
    for run in runs:
        if run.session_id == own_id:
            return run
    for run in runs:
        if run.pipeline == pipeline:
            return run
    return None


def _handoff_completed_phases(handoff_dir: Path) -> list[str]:
    """Completed phase names claimed by the pipeline.json projection."""
    state_file = handoff_dir / "pipeline.json"
    if not state_file.exists():
        return []
    try:
        parsed: object = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, dict):
        return []
    phases = cast(dict[str, object], parsed).get("phases")
    if not isinstance(phases, dict):
        return []
    completed: list[str] = []
    for name, record in cast(dict[str, object], phases).items():
        if not isinstance(record, dict):
            continue
        # BELIEF: phase records written by op_write_result carry phase_status.
        if cast(dict[str, object], record).get("phase_status") == "completed":
            completed.append(str(name))
    return sorted(completed)


def _not_resumable(pipeline: str, reason: str) -> ResumePlan:
    return ResumePlan(resumable=False, reason=reason, pipeline=pipeline)


def _plan_reason(resumable: bool, completed: list[str]) -> str:
    if resumable:
        return f"resume after completed phases: {', '.join(completed) or 'none'}"
    # AI: a failed frontier is never resumed; the fix path must run first.
    return "frontier failed; run the fix path instead of resuming"


def _plan_from_run(
    core: ExperienceStoreCore,
    project_root: Path,
    run: IncompleteRun,
    pipeline: str,
) -> ResumePlan:
    view = core.frontier(run.session_id)
    if view is None:
        return _not_resumable(pipeline, "run window is empty; start fresh")
    owner = run.owner or ""
    session_root = get_cortex_path(project_root, CortexResourceType.SESSION)
    handoff_dir = session_root / owner / pipeline
    completed = view.completed_phases
    mismatch = sorted(set(_handoff_completed_phases(handoff_dir)) ^ set(completed))
    resumable = run.frontier_status is not ExperienceNodeStatus.FAILED
    reason = _plan_reason(resumable, completed)
    return ResumePlan(
        resumable=resumable,
        reason=reason,
        pipeline=pipeline,
        session_id=owner or None,
        handoff_dir=str(handoff_dir) if owner else None,
        completed_phases=completed,
        frontier_phase=view.frontier_phase,
        frontier_status=run.frontier_status,
        handoff_mismatch=mismatch,
    )


def build_resume_plan(
    project_root: Path,
    session_id: str,
    pipeline: str,
    ttl_seconds: float | None = None,
    now: datetime | None = None,
) -> ResumePlan:
    """Resume plan for a pipeline: completed phases to skip and the frontier.

    Stale runs are closed as abandoned before matching, so expired runs are
    never offered. Phases listed in ``completed_phases`` must not run again;
    execution resumes at the next phase after them.
    """
    if not experience_db_path(project_root).exists():
        return _not_resumable(pipeline, "no experience store; start fresh")
    ttl = ttl_seconds if ttl_seconds is not None else resume_ttl_seconds()
    try:
        core = ExperienceStoreCore(experience_db_path(project_root))
        _ = core.mark_abandoned_runs(ttl, now)
        run = _find_run(core, session_id, pipeline, ttl, now)
    except Exception as exc:  # noqa: BLE001
        logger.warning("resume plan failed (best-effort): %s", exc)
        return _not_resumable(pipeline, f"experience store unreadable: {exc}")
    if run is None:
        return _not_resumable(
            pipeline, f"no incomplete run recorded for pipeline '{pipeline}'"
        )
    return _plan_from_run(core, project_root, run, pipeline)
