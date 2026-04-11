"""Parse plan bodies, compute implementation-step deltas, render change history."""

from __future__ import annotations

import re
from datetime import timezone

from cortex.core.models import PlanDelta

IMPLEMENTATION_STEPS_HEADING = "## Implementation Steps"
CHANGE_HISTORY_HEADING = "## Change History"
# Timestamp line uses ASCII hyphen or em dash between ISO time and author.
_CHANGE_ENTRY_HEADING_RE = re.compile(
    r"^###\s+(\S+?)\s+[\u2014-]\s+(.+)$", re.MULTILINE
)


def extract_markdown_section(content: str, heading: str) -> str | None:
    """Return body under ``heading`` (exact line match) until the next ``## ``."""
    lines = content.splitlines()
    in_section = False
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == heading:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            body.append(line)
    text = "\n".join(body).strip()
    return text or None


def parse_implementation_blocks(section: str | None) -> dict[str, str]:
    """Map ``###`` step headers to trimmed body text."""
    if not section:
        return {}
    blocks: dict[str, str] = {}
    current_key: str | None = None
    current_body: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            if current_key is not None:
                blocks[current_key] = "\n".join(current_body).strip()
            current_key = stripped
            current_body = []
        elif current_key is not None:
            current_body.append(line)
    if current_key is not None:
        blocks[current_key] = "\n".join(current_body).strip()
    return blocks


def _find_renames(
    old_only: set[str],
    new_only: set[str],
    old_blocks: dict[str, str],
    new_blocks: dict[str, str],
) -> tuple[list[tuple[str, str]], set[str], set[str]]:
    pairs: list[tuple[str, str]] = []
    used_old: set[str] = set()
    used_new: set[str] = set()
    for ok in sorted(old_only):
        if ok in used_old:
            continue
        for nk in sorted(new_only):
            if nk in used_new:
                continue
            if ok != nk and old_blocks[ok] == new_blocks[nk]:
                pairs.append((ok, nk))
                used_old.add(ok)
                used_new.add(nk)
                break
    remaining_old = set(old_only) - used_old
    remaining_new = set(new_only) - used_new
    return pairs, remaining_old, remaining_new


def _delta_lists_from_step_maps(
    old_blocks: dict[str, str], new_blocks: dict[str, str]
) -> tuple[list[str], list[str], list[str], list[str]]:
    old_keys = set(old_blocks)
    new_keys = set(new_blocks)
    renamed_pairs, old_only, new_only = _find_renames(
        old_keys - new_keys, new_keys - old_keys, old_blocks, new_blocks
    )
    renamed = [f"{a} → {b}" for a, b in renamed_pairs]
    removed = sorted(old_only)
    added = sorted(new_only)
    modified: list[str] = []
    for key in sorted(old_keys & new_keys):
        if old_blocks[key] != new_blocks[key]:
            modified.append(
                _summarize_modified_step(key, old_blocks[key], new_blocks[key])
            )
    return renamed, removed, modified, added


def compute_plan_delta(
    old_content: str,
    new_content: str,
    *,
    author: str,
    reason: str,
) -> PlanDelta | None:
    """Compare implementation steps; return a delta model or None if unchanged."""
    old_blocks = parse_implementation_blocks(
        extract_markdown_section(old_content, IMPLEMENTATION_STEPS_HEADING)
    )
    new_blocks = parse_implementation_blocks(
        extract_markdown_section(new_content, IMPLEMENTATION_STEPS_HEADING)
    )
    renamed, removed, modified, added = _delta_lists_from_step_maps(
        old_blocks, new_blocks
    )
    if not (renamed or removed or modified or added):
        return None
    return PlanDelta(
        timestamp=PlanDelta.utc_now(),
        author=author,
        renamed=renamed,
        removed=removed,
        modified=modified,
        added=added,
        reason=reason,
    )


def _summarize_modified_step(header: str, before: str, after: str) -> str:
    if before == after:
        return header
    b_preview = before.replace("\n", " ").strip()[:120]
    a_preview = after.replace("\n", " ").strip()[:120]
    return f"{header} (was: {b_preview!r}; now: {a_preview!r})"


def render_plan_delta_markdown(delta: PlanDelta) -> str:
    """Render one history entry (``###`` heading + category blocks)."""
    ts = delta.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    em = "\u2014"
    lines = [f"### {ts} {em} {delta.author}", ""]
    order: tuple[tuple[str, list[str]], ...] = (
        ("RENAMED", delta.renamed),
        ("REMOVED", delta.removed),
        ("MODIFIED", delta.modified),
        ("ADDED", delta.added),
    )
    for label, items in order:
        if not items:
            continue
        lines.append(f"**{label}**")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("**Reason**")
    lines.append("")
    lines.append(delta.reason)
    lines.append("")
    return "\n".join(lines)


def ensure_change_history_section(content: str) -> str:
    """Append an empty ``## Change History`` section when missing."""
    if CHANGE_HISTORY_HEADING in content:
        return content
    suffix = (
        f"\n\n{CHANGE_HISTORY_HEADING}\n\n"
        "_No revisions recorded yet — enrich or edit implementation steps to append "
        "history._\n"
    )
    return content.rstrip() + suffix


def append_change_history_entry(content: str, entry_markdown: str) -> str:
    """Append a rendered delta at the end of ``## Change History``."""
    entry = entry_markdown.strip()
    if not entry:
        return content
    if _last_history_entry_matches(content, entry):
        return content
    if CHANGE_HISTORY_HEADING not in content:
        content = ensure_change_history_section(content)
    prior = extract_markdown_section(content, CHANGE_HISTORY_HEADING) or ""
    new_body = f"{prior.strip()}\n\n{entry}\n".strip() + "\n"
    return _replace_change_history_body(content, new_body)


def _replace_change_history_body(content: str, new_body: str) -> str:
    start = content.find(CHANGE_HISTORY_HEADING)
    if start < 0:
        return content
    after_heading = start + len(CHANGE_HISTORY_HEADING)
    rest = content[after_heading:]
    m = re.search(r"\n## [^#]", rest)
    end_abs = after_heading + (m.start() if m else len(rest))
    return (
        content[:after_heading] + "\n\n" + new_body.rstrip() + "\n" + content[end_abs:]
    )


def _last_history_entry_matches(content: str, new_entry: str) -> bool:
    section = extract_markdown_section(content, CHANGE_HISTORY_HEADING)
    if not section:
        return False
    parts = re.split(r"(?=^### )", section, flags=re.MULTILINE)
    blocks = [p.strip() for p in parts if p.strip().startswith("###")]
    if not blocks:
        return False
    last = blocks[-1]
    return _normalize_history_body(last) == _normalize_history_body(new_entry)


def _normalize_history_body(text: str) -> str:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def change_history_stats(content: str) -> tuple[int, str | None]:
    """Return (number of ``###`` history entries, one-line latest summary)."""
    section = extract_markdown_section(content, CHANGE_HISTORY_HEADING)
    if not section:
        return (0, None)
    matches = list(_CHANGE_ENTRY_HEADING_RE.finditer(section))
    count = len(matches)
    if count == 0:
        return (0, None)
    last = matches[-1]
    ts = last.group(1)
    author = last.group(2).strip()
    tail = section[last.end() :].strip()
    reason_line = _first_reason_line_after_heading(tail)
    summary = f"{ts} — {author}"
    if reason_line:
        summary = f"{summary}: {reason_line}"
    return count, summary


def _first_reason_line_after_heading(tail: str) -> str:
    after_reason_heading = False
    for line in tail.splitlines():
        stripped = line.strip()
        if stripped == "**Reason**":
            after_reason_heading = True
            continue
        if not after_reason_heading:
            continue
        if not stripped:
            continue
        return stripped[:200]
    return ""


def last_change_context_line(content: str) -> str | None:
    """Single-line hint for agents: ``[LAST CHANGE: …]``."""
    section = extract_markdown_section(content, CHANGE_HISTORY_HEADING)
    if not section:
        return None
    matches = list(_CHANGE_ENTRY_HEADING_RE.finditer(section))
    if not matches:
        return None
    last = matches[-1]
    ts = last.group(1)
    _, summary = change_history_stats(content)
    if not summary:
        return f"[LAST CHANGE: {ts}]"
    return f"[LAST CHANGE: {ts}] {summary}"
