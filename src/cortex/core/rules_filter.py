"""Filter markdown rules content to task-relevant sections."""

from __future__ import annotations

import re

from cortex.core.models import TaskType

_TASK_TYPES_COMMENT = re.compile(r"<!--\s*task_types\s*:\s*([^>]+)-->", re.IGNORECASE)
_HEADER_RE = re.compile(r"^##\s+")


def _parse_task_types(comment_line: str) -> set[str]:
    match = _TASK_TYPES_COMMENT.search(comment_line)
    if match is None:
        return set()
    return {
        token.strip().upper() for token in match.group(1).split(",") if token.strip()
    }


def filter_rules(rules_content: str, task_types: list[TaskType]) -> str:
    """Keep only sections whose task_types tag intersects requested task types."""
    requested = {task_type.value for task_type in task_types}
    include_all = TaskType.ALL.value in requested
    lines = rules_content.splitlines()
    kept: list[str] = []
    section_start = 0
    section_allowed = True

    def flush(end_index: int) -> None:
        if section_allowed:
            kept.extend(lines[section_start:end_index])

    for index, line in enumerate(lines):
        if _HEADER_RE.match(line):
            flush(index)
            section_start = index
            section_allowed = True
            continue
        if "<!--" in line and "task_types" in line:
            tags = _parse_task_types(line)
            if TaskType.ALL.value in tags:
                section_allowed = True
            elif include_all:
                section_allowed = True
            else:
                section_allowed = bool(tags & requested)

    if lines:
        flush(len(lines))
    if not kept:
        return rules_content
    return "\n".join(kept).strip() + "\n"
