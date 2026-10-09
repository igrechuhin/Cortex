"""Resume operation for pipeline_handoff: continuation from the store frontier."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.experience.resume import ResumePlan, build_resume_plan, not_resumable

from .pipeline_handoff_session import (
    bind_session_id,
    get_session_id,
    live_sibling_owner_ids,
)


def _plan_for(project_root: Path, session_id: str, pipeline: str) -> ResumePlan:
    return build_resume_plan(
        project_root,
        session_id,
        pipeline,
        excluded_owners=live_sibling_owner_ids(project_root),
    )


def op_resume(project_root: Path, pipeline: str) -> str:
    """Return the resume plan for an interrupted pipeline run.

    Queries the experience store for this process's run of the pipeline
    (current session preferred), reconciles it against the handoff
    projection, and reports the phases that must be skipped on
    continuation. Runs still owned by a live sibling connection are
    excluded, so resume can never attach another process's run window.

    # AI: when the plan's owner differs from the resolved id we bind to it
    # and rebuild; on a refused bind the answer is exactly NON-RESUMABLE —
    # reaching the bind attempt proves the effective id has no incomplete
    # run of its own (the own-run preference would have matched it above),
    # and only this process writes under its latched id. Re-querying the
    # store here would be a TOCTOU: a run created between the reads could
    # be reported while the latch stays put.
    """
    session_id = get_session_id(project_root, pipeline=pipeline)
    plan = _plan_for(project_root, session_id, pipeline)
    target = plan.session_id if plan.resumable else None
    if target is not None and target != session_id:
        session_id = bind_session_id(project_root, target)
        if session_id == target:
            plan = _plan_for(project_root, session_id, pipeline)
            # AI: post-validate the success-path rebuild — the
            # deterministic counterpart of the refused-bind guard above
            # (snapshot-exclusion here would be TOCTOU-prone). If the just
            # claimed run's window closed between claim and rebuild, the
            # plan must never fall back to another run: the latch holds
            # the claimed id, so the exact answer is non-resumable.
            if plan.resumable and plan.session_id != session_id:
                plan = not_resumable(pipeline, "resumed run no longer available")
        else:
            plan = not_resumable(pipeline, "run owned by another connection")
    return json.dumps(
        {"status": "ok", **plan.model_dump(mode="json")},
        indent=2,
    )
