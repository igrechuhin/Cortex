"""Invariant: PARTIAL progress entries require a non-empty roadmap backlog."""

from __future__ import annotations

import re

_PARTIAL_LINE = re.compile(
    r"^\s*-\s+\*\*.+\*\*\s+-\s+PARTIAL(?:[\s.]|$)",
    re.MULTILINE,
)
_PENDING_LINE = re.compile(
    r"^\s*-\s+\*\*.+\*\*\s+-\s+PENDING(?:[\s.-]|$)",
    re.MULTILINE,
)


def check_roadmap_progress_consistency(
    progress_content: str, roadmap_content: str
) -> list[str]:
    """Return violations when progress has PARTIAL items but roadmap has no PENDING line."""
    if _PARTIAL_LINE.search(progress_content) is None:
        return []
    if _PENDING_LINE.search(roadmap_content) is not None:
        return []
    msg = (
        "progress.md contains PARTIAL entries but roadmap.md has no PENDING items; "
        "add or restore at least one roadmap backlog entry for incomplete work."
    )
    return [msg]
