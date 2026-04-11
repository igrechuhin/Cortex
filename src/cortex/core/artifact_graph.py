"""Plan dependency helpers for scoped context assembly."""

from __future__ import annotations

import re
from pathlib import Path

_DEPENDS_RE = re.compile(
    r"^depends_on\s*:\s*\[(.*?)\]\s*$", re.IGNORECASE | re.MULTILINE
)
_STATUS_RE = re.compile(r"^status\s*:\s*([A-Z_]+)\s*$", re.IGNORECASE | re.MULTILINE)


def _parse_depends_on(plan_content: str) -> list[str]:
    match = _DEPENDS_RE.search(plan_content)
    if match is None:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    deps: list[str] = []
    for item in raw.split(","):
        token = item.strip().strip("\"'")
        if token:
            deps.append(token)
    return deps


def _is_done_plan(plan_content: str) -> bool:
    match = _STATUS_RE.search(plan_content)
    if match is None:
        return False
    return match.group(1).strip().upper() == "DONE"


def resolve_upstream_plans(plan_slug: str, plans_dir: Path) -> list[str]:
    """Resolve transitive DONE dependencies in topological order."""
    resolved: list[str] = []
    visited: set[str] = set()

    def visit(slug: str) -> None:
        if slug in visited:
            return
        visited.add(slug)
        plan_path = plans_dir / f"{slug}.md"
        if not plan_path.is_file():
            return
        content = plan_path.read_text(encoding="utf-8")
        for dep in _parse_depends_on(content):
            visit(dep)
        if slug != plan_slug and _is_done_plan(content):
            resolved.append(slug)

    visit(plan_slug)
    return resolved
