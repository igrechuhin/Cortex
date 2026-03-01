"""Pure helpers for session compaction (Phase 56).

No I/O; all functions take content strings and return transformed content or
parsed structures. Used by compact_session tool and progress summarization.
"""

import re
from datetime import datetime
from enum import Enum

from cortex.tools.compaction_constants import (
    PROGRESS_DAYS_FULL,
    PROGRESS_DAYS_WEEKLY_SUMMARY,
    RECENT_CHANGES_MAX_ENTRIES,
)
from cortex.tools.files.file_section_helpers import (
    find_section_end,
    find_section_heading,
)

# Pattern for "## Completed Work (YYYY-MM-DD)"
_COMPLETED_WORK_HEADING = re.compile(
    r"^##\s+Completed Work\s+\((\d{4}-\d{2}-\d{2})\)\s*$"
)

# Pattern for "## YYYY-MM-DD" in progress.md
_PROGRESS_DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")


def _parse_date(s: str) -> datetime | None:
    """Parse YYYY-MM-DD to date. Returns None if invalid."""
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def get_completed_work_sections(content: str) -> list[tuple[str, int, int]]:
    """Find all '## Completed Work (YYYY-MM-DD)' sections.

    Returns list of (date_str, start_line, end_line_exclusive).
    """
    lines = content.split("\n")
    result: list[tuple[str, int, int]] = []
    i = 0
    while i < len(lines):
        match = _COMPLETED_WORK_HEADING.match(lines[i].strip())
        if match:
            date_str = match.group(1)
            start = i
            level = 2
            end = find_section_end(lines, start, level)
            result.append((date_str, start, end))
            i = end
        else:
            i += 1
    return result


def compact_active_context_completed_work(content: str, current_date_str: str) -> str:
    """Keep only current date's Completed Work full; summarize older to one line each.

    Older dates become a single summary line: "- **Summary (YYYY-MM-DD)** - N entries."
    """
    lines = content.split("\n")
    sections = get_completed_work_sections(content)
    if not sections:
        return content

    current_dt = _parse_date(current_date_str)
    if current_dt is None:
        return content

    # Build new lines: before first Completed Work, then compacted sections, then rest
    first_start = sections[0][1]
    before = lines[:first_start]

    new_sections_lines: list[str] = []
    for date_str, start, end in sections:
        section_lines = lines[start:end]
        dt = _parse_date(date_str)
        if dt is None:
            new_sections_lines.extend(section_lines)
            continue
        if dt.date() == current_dt.date():
            new_sections_lines.extend(section_lines)
        else:
            # Count bullet entries (lines starting with -)
            bullets = sum(1 for ln in section_lines[1:] if ln.strip().startswith("-"))
            new_sections_lines.append(section_lines[0])  # heading
            new_sections_lines.append("")  # MD022: blank line after heading
            new_sections_lines.append(
                f"- **Summary ({date_str})** - {bullets} entries archived."
            )
            new_sections_lines.append("")

    # Rest of file after last Completed Work section
    last_end = sections[-1][2]
    after = lines[last_end:]

    return "\n".join(before + new_sections_lines + after)


def trim_recent_changes(
    content: str, max_entries: int = RECENT_CHANGES_MAX_ENTRIES
) -> str:
    """Keep at most max_entries bullet entries in '## Recent Changes'."""
    idx, level = find_section_heading(content.split("\n"), "Recent Changes")
    if idx is None:
        return content
    lines = content.split("\n")
    end = find_section_end(lines, idx, level)
    section_lines = lines[idx:end]
    bullets = [ln for ln in section_lines[1:] if ln.strip().startswith("-")]
    if len(bullets) <= max_entries:
        return content
    kept = bullets[:max_entries]
    new_section = [section_lines[0]] + kept + [""]
    return "\n".join(lines[:idx] + new_section + lines[end:])


def get_progress_date_sections(content: str) -> list[tuple[str, list[str]]]:
    """Parse progress.md into (date_str, lines) for each '## YYYY-MM-DD' section."""
    lines = content.split("\n")
    result: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        match = _PROGRESS_DATE_HEADING.match(lines[i].strip())
        if match:
            date_str = match.group(1)
            start = i
            level = 2
            end = find_section_end(lines, start, level)
            result.append((date_str, lines[start:end]))
            i = end
        else:
            i += 1
    return result


def _days_between(date_str: str, today_str: str) -> int | None:
    """Return days from date_str to today_str. None if parse fails."""
    d = _parse_date(date_str)
    t = _parse_date(today_str)
    if d is None or t is None:
        return None
    return (t.date() - d.date()).days


def summarize_entries_as_line(entries: list[str], label: str) -> str:
    """Turn a list of bullet lines into one summary line."""
    count = len([e for e in entries if e.strip().startswith("-")])
    return f"- **{label}** - {count} entries summarized."


def _progress_section_to_lines(
    date_str: str,
    section_lines: list[str],
    days: int | None,
    days_full: int,
    days_weekly: int,
) -> list[str]:
    """Return lines for one progress section (full or summarized)."""
    if days is None:
        return section_lines
    if days <= days_full:
        return section_lines
    if days <= days_weekly:
        label = f"Week containing {date_str}"
    else:
        label = f"Month containing {date_str}"
    summary = summarize_entries_as_line(section_lines[1:], label)
    return [section_lines[0], "", summary, ""]


def apply_progress_tiers(
    content: str,
    today_str: str,
    days_full: int = PROGRESS_DAYS_FULL,
    days_weekly: int = PROGRESS_DAYS_WEEKLY_SUMMARY,
) -> str:
    """Apply progressive summarization: full (0-7d), weekly (7-30d), monthly (30+d).

    Returns new progress content with older sections replaced by summary lines.
    """
    sections = get_progress_date_sections(content)
    if not sections:
        return content

    lines = content.split("\n")
    first_line_of_first = next(
        (i for i, ln in enumerate(lines) if _PROGRESS_DATE_HEADING.match(ln.strip())),
        len(lines),
    )
    before = lines[:first_line_of_first]
    last_section_end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if _PROGRESS_DATE_HEADING.match(lines[i].strip()):
            last_section_end = find_section_end(lines, i, 2)
            break
    after = lines[last_section_end:]

    new_parts: list[str] = []
    for date_str, section_lines in sections:
        days = _days_between(date_str, today_str)
        new_parts.extend(
            _progress_section_to_lines(
                date_str, section_lines, days, days_full, days_weekly
            )
        )
    return "\n".join(before + new_parts + after)


class ProgressTier(str, Enum):
    """Progress summarization tier."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"


def summarize_progress(
    content: str,
    tier: ProgressTier | str,
    today_str: str,
) -> str:
    """Summarize progress.md by tier: weekly (7-30d) or monthly (30+d)."""
    tier_str = tier.value if isinstance(tier, ProgressTier) else tier
    if tier_str == "weekly":
        return apply_progress_tiers(
            content,
            today_str,
            days_full=PROGRESS_DAYS_FULL,
            days_weekly=PROGRESS_DAYS_WEEKLY_SUMMARY,
        )
    # monthly
    return apply_progress_tiers(
        content,
        today_str,
        days_full=PROGRESS_DAYS_WEEKLY_SUMMARY,
        days_weekly=PROGRESS_DAYS_WEEKLY_SUMMARY,
    )
