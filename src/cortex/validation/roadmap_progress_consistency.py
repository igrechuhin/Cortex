"""Invariant: only unresolved PARTIAL progress entries require roadmap backlog."""

from __future__ import annotations

import re

_STATUS_LINE = re.compile(
    r"^\s*-\s+\*\*(?P<title>.+?)\*\*\s+-\s+(?P<status>PARTIAL|COMPLETE)(?:[\s.]|$)",
    re.MULTILINE,
)
_PENDING_LINE = re.compile(
    r"^\s*-\s+\*\*.+\*\*\s+-\s+PENDING(?:[\s.-]|$)",
    re.MULTILINE,
)


def check_roadmap_progress_consistency(
    progress_content: str, roadmap_content: str
) -> list[str]:
    """Require roadmap backlog only for unresolved PARTIAL workstreams."""
    status_matches = list(_STATUS_LINE.finditer(progress_content))
    if not status_matches:
        return []
    complete_titles = {
        match.group("title").strip()
        for match in status_matches
        if match.group("status") == "COMPLETE"
    }
    unresolved_partial_titles = {
        match.group("title").strip()
        for match in status_matches
        if match.group("status") == "PARTIAL"
        and match.group("title").strip() not in complete_titles
    }
    if not unresolved_partial_titles:
        return []
    if _PENDING_LINE.search(roadmap_content) is not None:
        return []
    msg = (
        "progress.md contains unresolved PARTIAL entries but roadmap.md has no PENDING "
        "items; add or restore at least one roadmap backlog entry for incomplete work."
    )
    return [msg]
