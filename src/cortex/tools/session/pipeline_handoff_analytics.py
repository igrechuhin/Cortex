"""Coverage-checked graph-analytics operations for ``pipeline_handoff``.

Mirrors ``experience_recall_brief.py``'s sync pattern: open
``ExperienceStoreCore`` directly and check store/session coverage before
querying, so the analyze-session step can fall back to transcript scraping
when there is no graph coverage for a session (see plan
``analyze-experience-graph-queries.md``, Review Follow-Up Gap 1).
"""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.experience.recorder import experience_db_path
from cortex.experience.store_core import ExperienceStoreCore

# AI: cortex.experience.failure_evals imports cortex.tools.evaluation._models,
# which forces a full cortex.tools package init (parent-package-first import
# rule) — importing it here at module scope would re-enter this module mid
# import whenever cortex.experience.failure_evals is imported first (e.g. from
# a test). Deferred inside op_write_failure_evals to break the cycle.


def _open_core(project_root: Path) -> ExperienceStoreCore | None:
    db_path = experience_db_path(project_root)
    if not db_path.exists():
        return None
    return ExperienceStoreCore(db_path)


def _no_coverage_response() -> str:
    return json.dumps({"status": "no_coverage", "coverage": False}, indent=2)


def _failure_evals_path(project_root: Path) -> Path:
    evals_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / "evals"
    return evals_dir / "tasks" / "failure_based_evals.json"


def op_preference_pairs(project_root: Path, session_id: str) -> str:
    """Coverage-checked preference-pair query for the analyze-session step."""
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response()
    if not core.list_nodes(session_id):
        return json.dumps({"status": "ok", "coverage": False, "pairs": []}, indent=2)
    pairs = core.preference_pairs(session_id)
    return json.dumps(
        {
            "status": "ok",
            "coverage": True,
            "pairs": [pair.model_dump(mode="json") for pair in pairs],
        },
        indent=2,
    )


def op_repeated_failures(project_root: Path, session_id: str) -> str:
    """Coverage-checked repeated-failure-cluster query for the analyze-session step."""
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response()
    if not core.list_nodes(session_id):
        return json.dumps({"status": "ok", "coverage": False, "clusters": []}, indent=2)
    clusters = core.repeated_failures(session_id)
    return json.dumps(
        {
            "status": "ok",
            "coverage": True,
            "clusters": [cluster.model_dump(mode="json") for cluster in clusters],
        },
        indent=2,
    )


def op_fitness_by_task_type(project_root: Path) -> str:
    """Coverage-checked store-wide fitness-by-task-type query."""
    core = _open_core(project_root)
    if core is None:
        return _no_coverage_response()
    if not core.list_sessions():
        return json.dumps({"status": "ok", "coverage": False, "results": []}, indent=2)
    results = core.fitness_by_task_type()
    return json.dumps(
        {
            "status": "ok",
            "coverage": True,
            "results": [result.model_dump(mode="json") for result in results],
        },
        indent=2,
    )


def op_write_failure_evals(project_root: Path, session_id: str) -> str:
    """Write evidence-linked ``failure_based_evals.json`` entries from graph pairs."""
    from cortex.experience.failure_evals import (
        preference_pairs_to_eval_tasks,
        upsert_eval_tasks,
    )

    core = _open_core(project_root)
    if core is None:
        return json.dumps(
            {"status": "no_coverage", "written": 0, "task_ids": []}, indent=2
        )
    pairs = core.preference_pairs(session_id)
    if not pairs:
        return json.dumps({"status": "ok", "written": 0, "task_ids": []}, indent=2)
    tasks = preference_pairs_to_eval_tasks(pairs)
    written_ids = upsert_eval_tasks(_failure_evals_path(project_root), tasks)
    return json.dumps(
        {"status": "ok", "written": len(written_ids), "task_ids": written_ids},
        indent=2,
    )
