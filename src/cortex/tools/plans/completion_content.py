"""Content parsing and manipulation helpers for plan completion.

Handles roadmap bullet lookup, Completed Work section parsing,
and progress entry appending logic.
"""

import re


def today_iso() -> str:
    """Return today's date in YYYY-MM-DD."""
    from datetime import date

    return date.today().strftime("%Y-%m-%d")


def find_roadmap_bullet_line(content: str, plan_title: str) -> int | None:
    """Return 1-based line number of first bullet line containing plan_title, or None."""
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("- ") and plan_title.strip() in line:
            return i
    return None


def remove_line_at(content: str, one_based_line: int) -> str:
    """Remove the line at the given 1-based index; return new content."""
    lines = content.split("\n")
    idx = one_based_line - 1
    if idx < 0 or idx >= len(lines):
        return content
    new_lines = lines[:idx] + lines[idx + 1 :]
    return "\n".join(new_lines)


def find_completed_work_section(content: str, date_str: str) -> tuple[int, int] | None:
    """Return (start_line_1based, end_line_1based) of '## Completed Work (date_str)' or None."""
    lines = content.split("\n")
    pattern = re.compile(
        r"^##\s+Completed Work\s+\(\s*" + re.escape(date_str) + r"\s*\)"
    )
    start = None
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return None
    end = start
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("## ") and i + 1 != start:
            end = i
            break
        end = i + 1
    return (start, end)


def last_bullet_line_in_range(lines: list[str], start_0: int, end_0: int) -> int | None:
    """Return 0-based index of last line in [start_0, end_0) that starts with '- ', or None."""
    last = None
    for i in range(start_0, min(end_0, len(lines))):
        if lines[i].strip().startswith("- "):
            last = i
    return last


def has_completed_entry_for_date_and_title(
    content: str, date_str: str, title: str
) -> bool:
    """True if activeContext has a completed entry with same date and title (avoids duplicate bullets)."""
    section = find_completed_work_section(content, date_str.strip())
    if not section:
        return False
    start_1, end_1 = section
    lines = content.split("\n")
    want = title.strip()
    for i in range(start_1 - 1, min(end_1, len(lines))):
        line = lines[i].strip()
        if not line.startswith("- "):
            continue
        if "**" in line:
            parts = line.split("**", 2)
            if len(parts) >= 2:
                existing_title = parts[1].strip()
                if existing_title == want:
                    return True
    return False


def append_completed_entry(
    content: str, date_str: str, title: str, summary: str
) -> tuple[str, int | None]:
    """Append completed entry to activeContext. Returns (new_content, 1-based line inserted)."""
    lines = content.split("\n")
    section = find_completed_work_section(content, date_str)
    if not section:
        return (content, None)
    start_1, end_1 = section
    start_0, end_0 = start_1 - 1, end_1
    last_bullet = last_bullet_line_in_range(lines, start_0, end_0)
    insert_at = (last_bullet + 1) if last_bullet is not None else start_0 + 1
    entry = f"- ✅ **{title}** - COMPLETE ({date_str}) - {summary}"
    new_lines = lines[:insert_at] + [""] + [entry] + lines[insert_at:]
    new_content = "\n".join(new_lines)
    line_inserted = insert_at + 2
    return (new_content, line_inserted)


def create_section_and_append(
    content: str, date_str: str, title: str, summary: str
) -> tuple[str, int | None]:
    """If no section for date exists, add it after first '## Completed Work'; then append entry."""
    section = find_completed_work_section(content, date_str)
    if section:
        return append_completed_entry(content, date_str, title, summary)
    lines = content.split("\n")
    new_section_header = f"## Completed Work ({date_str})"
    entry = f"- ✅ **{title}** - COMPLETE ({date_str}) - {summary}"
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Completed Work\s+\(", line.strip()):
            insert_at = i
            new_lines = (
                lines[:insert_at]
                + [new_section_header]
                + [""]
                + [entry]
                + [""]
                + lines[insert_at:]
            )
            new_content = "\n".join(new_lines)
            return (new_content, insert_at + 3)
    return (content, None)


def find_progress_date_section(content: str, date_str: str) -> tuple[int, int] | None:
    """Return (start_0, end_0) 0-based line range for ## date_str in progress.md, or None."""
    lines = content.split("\n")
    target = f"## {date_str.strip()}"
    start = None
    for i, line in enumerate(lines):
        if line.strip() == target:
            start = i
            break
    if start is None:
        return None
    end = start + 1
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            end = i
            break
        end = i + 1
    return (start, end)


def append_progress_entry_content(
    content: str, date_str: str, entry_text: str
) -> tuple[str, int | None]:
    """Append one bullet to progress.md under ## date_str. Returns (new_content, 1-based line)."""
    section = find_progress_date_section(content, date_str)
    lines = content.split("\n")
    bullet = f"- {entry_text.strip()}"
    if section:
        start_0, end_0 = section
        last_bullet = last_bullet_line_in_range(lines, start_0 + 1, end_0)
        insert_at = (last_bullet + 1) if last_bullet is not None else start_0 + 2
        new_lines = lines[:insert_at] + [bullet] + lines[insert_at:]
        return ("\n".join(new_lines), insert_at + 1)
    header = f"## {date_str.strip()}"
    for i, line in enumerate(lines):
        if line.strip().startswith("# ") and "Progress" in line:
            insert_at = i + 2
            new_lines = lines[:insert_at] + [header, "", bullet, ""] + lines[insert_at:]
            return ("\n".join(new_lines), insert_at + 3)
    new_lines = [header, "", bullet, ""] + lines
    return ("\n".join(new_lines), 3)
