"""Evidence-linked failure_based_evals.json entries from graph-pattern queries.

Converts ``PreferencePair`` results (``cortex.experience.analytics``) into
``EvalTask`` entries carrying ``EvidenceLink`` provenance, and upserts them
into ``.cortex/evals/tasks/failure_based_evals.json`` by id, preserving
existing hand-written entries untouched (see plan
``analyze-experience-graph-queries.md``, Review Follow-Up Gap 2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.experience.analytics_models import PreferencePair
from cortex.tools.evaluation._models import EvalTask, EvalTaskCategory, EvidenceLink


def _eval_task_for_pair(pair: PreferencePair) -> EvalTask:
    failed = pair.failed_node
    passed = pair.passed_node
    label = failed.label or failed.id
    return EvalTask(
        id=f"graph-{failed.id}",
        name=f"Graph-sourced failure: {label}",
        description=(
            f"Sibling node {failed.id} (parent {pair.parent_id}, session "
            f"{pair.session_id}) failed the gate; sibling {passed.id} passed "
            "the same gate under the same parent."
        ),
        category=EvalTaskCategory.OTHER,
        expected_outcome=(
            f"Matches passed sibling {passed.id} under parent {pair.parent_id}"
        ),
        evidence=[
            EvidenceLink(
                node_id=failed.id,
                artifact_ref=failed.artifact_ref,
                confidence_source="graph",
            ),
            EvidenceLink(
                node_id=passed.id,
                artifact_ref=passed.artifact_ref,
                confidence_source="graph",
            ),
        ],
    )


def preference_pairs_to_eval_tasks(pairs: list[PreferencePair]) -> list[EvalTask]:
    """Map graph preference pairs to evidence-linked ``EvalTask`` entries."""
    return [_eval_task_for_pair(pair) for pair in pairs]


def _trim_payload(payload: dict[str, object]) -> dict[str, object]:
    """Drop None/empty-list fields so new entries match the file's hand-written style."""
    trimmed: dict[str, object] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        trimmed[key] = value
    return trimmed


def _format_eval_tasks_json(entries: list[dict[str, object]]) -> str:
    """Serialize eval-task dicts in ``failure_based_evals.json``'s compact style.

    2-space indented objects, one field per line, list/scalar field values
    rendered inline (matches the file's existing hand-written formatting).
    """
    if not entries:
        return "[]\n"
    obj_blocks = [
        "  {\n"
        + ",\n".join(
            f'    "{key}": {json.dumps(value)}' for key, value in entry.items()
        )
        + "\n  }"
        for entry in entries
    ]
    return "[\n" + ",\n".join(obj_blocks) + "\n]\n"


def _read_existing_entries(tasks_path: Path) -> list[dict[str, object]]:
    if not tasks_path.exists():
        return []
    raw = tasks_path.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    loaded: object = json.loads(raw)
    if not isinstance(loaded, list):
        return []
    items = cast(list[object], loaded)
    return [cast(dict[str, object], item) for item in items if isinstance(item, dict)]


def upsert_eval_tasks(tasks_path: Path, new_tasks: list[EvalTask]) -> list[str]:
    """Upsert ``EvalTask`` entries into ``tasks_path`` by id.

    Reads the existing JSON array (if present), replaces entries whose id
    matches a new task, appends new ids in encounter order, and writes back
    using the file's established compact-list formatting. Untouched existing
    entries are preserved verbatim. Returns the ids written (updated or
    appended); idempotent across repeated calls with the same tasks.
    """
    existing = _read_existing_entries(tasks_path)
    by_id: dict[str, dict[str, object]] = {
        str(e["id"]): e for e in existing if "id" in e
    }
    order = [str(e["id"]) for e in existing if "id" in e]

    written_ids: list[str] = []
    for task in new_tasks:
        payload = _trim_payload(task.model_dump(mode="json", exclude_none=True))
        if task.id not in by_id:
            order.append(task.id)
        by_id[task.id] = payload
        written_ids.append(task.id)

    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    _ = tasks_path.write_text(
        _format_eval_tasks_json([by_id[i] for i in order]), encoding="utf-8"
    )
    return written_ids
