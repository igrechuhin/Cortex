"""Workflow schema resolution for session brief (keeps ``brief.py`` smaller)."""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.core.models import WorkflowSchema
from cortex.core.project_session_config import load_project_session_config
from cortex.core.schema_loader import (
    SchemaNotFoundError,
    evaluate_workflow_condition,
    load_schema,
)

logger = logging.getLogger(__name__)


def _visible_workflow_phases(
    schema: WorkflowSchema,
    session_state: dict[str, object],
) -> list[str]:
    return [
        f"{p.name}: {p.tool}" + (" (required)" if p.required else " (optional)")
        for p in schema.phases
        if evaluate_workflow_condition(p.condition, session_state)
    ]


def load_workflow_brief_fields(
    project_root: Path,
) -> tuple[str, str, list[str], str | None]:
    """Resolve active workflow schema for the session brief."""
    cfg = load_project_session_config(project_root)
    requested = cfg.workflow_schema
    warning: str | None = None
    try:
        schema = load_schema(requested, project_root)
    except (SchemaNotFoundError, ValueError, OSError) as e:
        logger.warning("workflow_schema %r failed: %s", requested, e)
        try:
            schema = load_schema("default", project_root)
        except (SchemaNotFoundError, ValueError, OSError):
            return (
                requested,
                "",
                [],
                (
                    f"workflow_schema {requested!r} invalid and default schema unavailable: {e}"
                ),
            )
        warning = (
            f"workflow_schema {requested!r} could not be loaded ({e}); "
            "using built-in default."
        )
    session_state = cfg.model_dump(mode="python")
    phases = _visible_workflow_phases(schema, session_state)
    return schema.name, schema.description, phases, warning
