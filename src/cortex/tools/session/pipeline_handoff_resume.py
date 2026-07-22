"""Resume operation for pipeline_handoff: continuation from the store frontier."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.experience.resume import build_resume_plan

from .pipeline_handoff_io import get_session_id


def op_resume(project_root: Path, pipeline: str) -> str:
    """Return the resume plan for an interrupted pipeline run.

    Queries the experience store for the freshest incomplete run of this
    pipeline (current session preferred), reconciles it against the handoff
    projection, and reports the phases that must be skipped on continuation.
    """
    plan = build_resume_plan(project_root, get_session_id(project_root), pipeline)
    return json.dumps(
        {"status": "ok", **plan.model_dump(mode="json")},
        indent=2,
    )
