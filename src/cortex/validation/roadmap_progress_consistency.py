"""Invariant: only unresolved PARTIAL progress entries require roadmap backlog."""

from __future__ import annotations

import re

_STATUS_LINE = re.compile(
    r"^\s*-\s+\*\*(?P<title>.+?)\*\*\s+-\s+(?P<status>PARTIAL|COMPLETE)(?:[\s.]|$)",
    re.MULTILINE,
)
# Roadmap bullets often use em/en dashes (—/–) before PENDING; progress lines use ASCII "-".
_PENDING_LINE = re.compile(
    r"^\s*-\s+\*\*(?P<title>.+?)\*\*\s+[-\u2013\u2014]\s+PENDING\b",
    re.MULTILINE,
)


def _title_has_pending_match(title: str, pending_titles: set[str]) -> bool:
    """Return True when *title* overlaps (case-insensitive) with any pending title."""
    title_lower = title.lower()
    for pending in pending_titles:
        pending_lower = pending.lower()
        if title_lower in pending_lower or pending_lower in title_lower:
            return True
    return False


def _orphan_partial_messages(
    unresolved_partial_titles: set[str], pending_titles: set[str]
) -> list[str]:
    messages: list[str] = []
    for title in sorted(unresolved_partial_titles):
        if _title_has_pending_match(title, pending_titles):
            continue
        msg = (
            f'progress.md has unresolved PARTIAL "{title}" with no matching PENDING '
            "entry in roadmap.md; mark it COMPLETE if done, or add a PENDING roadmap "
            "entry if work remains (warning-only, do not fabricate placeholder backlog)."
        )
        messages.append(msg)
    return messages


def check_roadmap_progress_consistency(
    progress_content: str, roadmap_content: str
) -> list[str]:
    """Require a matching PENDING entry for each unresolved PARTIAL workstream.

    An unresolved PARTIAL is a ``- **Title** - PARTIAL`` line whose title has no
    corresponding ``- **Title** - COMPLETE`` line elsewhere in *progress_content*.
    Each such title must match (case-insensitive substring) at least one
    ``- **...** - PENDING`` entry in *roadmap_content*; orphans produce a warning.
    """
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
    pending_titles = {
        match.group("title").strip()
        for match in _PENDING_LINE.finditer(roadmap_content)
    }
    return _orphan_partial_messages(unresolved_partial_titles, pending_titles)
