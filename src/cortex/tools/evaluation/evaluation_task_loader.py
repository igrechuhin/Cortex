"""Phase 57: Load raw eval task dicts from JSON (no EvalTask dependency)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


def load_eval_task_dicts(tasks_dir: Path) -> list[dict[str, object]]:
    """Load raw task dicts from all JSON files under tasks_dir."""
    records: list[dict[str, object]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not raw_text.strip():
            continue
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        items: list[dict[str, object]] = []
        if isinstance(data, list):
            sequence = cast(list[object], data)
            for item_obj in sequence:
                if isinstance(item_obj, dict):
                    item = cast(dict[str, object], item_obj)
                    items.append(item)
        elif isinstance(data, dict):
            item_single = cast(dict[str, object], data)
            items.append(item_single)
        records.extend(items)
    return records


def build_eval_tasks[T](
    records: list[dict[str, object]],
    selected_ids: set[str],
    validate: Callable[[dict[str, object]], T | None],
    id_attr: str = "id",
) -> list[T]:
    """Validate raw task dicts and apply ID filter; returns list of validated models."""
    tasks: list[T] = []
    for rec in records:
        try:
            task = validate(rec)
        except Exception as e:
            logger.debug("build_eval_tasks: skip invalid record: %s", e)
            continue
        if task is None:
            continue
        tid = getattr(task, id_attr, None)
        if selected_ids and tid not in selected_ids:
            continue
        tasks.append(task)
    return tasks
