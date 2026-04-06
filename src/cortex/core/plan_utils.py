"""Utilities for parsing Cortex plan markdown documents."""

from __future__ import annotations

import re
from collections.abc import Iterator

from cortex.core.models import ClarificationMarker

# AI: Single compiled pattern keeps scans fast and documents the exact marker grammar.
_MARKER_PATTERN = re.compile(
    r"\[NEEDS CLARIFICATION(?P<blocking>\(blocking\))?\s*:\s*(?P<reason>[^\]]*)\]",
    re.IGNORECASE,
)


def _fenced_code_spans(text: str) -> list[tuple[int, int]]:
    """Return half-open character spans that lie inside fenced ``` blocks."""
    lines = text.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    offset = 0
    in_fence = False
    span_start = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                span_start = offset
            else:
                in_fence = False
                spans.append((span_start, offset + len(line)))
        offset += len(line)
    return spans


def _in_fenced_block(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _line_number_at(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _iter_marker_matches(text: str) -> Iterator[re.Match[str]]:
    spans = _fenced_code_spans(text)
    for match in _MARKER_PATTERN.finditer(text):
        if _in_fenced_block(match.start(), spans):
            continue
        reason = (match.group("reason") or "").strip()
        if not reason:
            continue
        yield match


def find_clarification_markers(content: str) -> list[ClarificationMarker]:
    """Scan *content* for ``[NEEDS CLARIFICATION ...]`` markers.

    Ignores matches inside fenced code blocks. Markers with an empty reason text
    are skipped. Each returned marker has ``resolved=False``.
    """
    out: list[ClarificationMarker] = []
    for match in _iter_marker_matches(content):
        line_no = _line_number_at(content, match.start())
        blocking = match.group("blocking") is not None
        reason = match.group("reason").strip()
        out.append(
            ClarificationMarker(
                reason=reason,
                blocking=blocking,
                location=f"line {line_no}",
                resolved=False,
            )
        )
    return out


_CLARIFICATIONS_HEADING = re.compile(r"^##\s+Clarifications Needed\s*$")


def strip_clarifications_needed_section(content: str) -> str:
    """Remove a ``## Clarifications Needed`` block through the next ``##`` heading."""
    # AI: Drop prior auto-summary so create/enrich can regenerate without duplicate headings.
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _CLARIFICATIONS_HEADING.match(line.rstrip("\r\n")):
            i += 1
            while i < len(lines) and not re.match(r"^##\s+", lines[i]):
                i += 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _format_clarifications_needed_section(markers: list[ClarificationMarker]) -> str:
    lines = [
        "## Clarifications Needed",
        "",
        "Summary of inline `[NEEDS CLARIFICATION]` markers (auto-generated on create):",
        "",
    ]
    for m in markers:
        # AI: Prefix distinguishes blocking markers without relying on bold in logs.
        prefix = "(blocking) " if m.blocking else ""
        lines.append(f"- {prefix}{m.reason} — {m.location}")
    lines.append("")
    return "\n".join(lines)


def _insert_point_clarifications_section(text: str) -> int:
    """Return the index where the Clarifications Needed section should start."""
    ctx = re.search(r"(?m)^##\s+context\s*$", text)
    if ctx:
        return ctx.start()
    goal = re.search(r"(?m)^##\s+goal\s*$", text)
    if goal:
        start = goal.end()
        rest = text[start:]
        nxt = re.search(r"(?m)^##\s+", rest)
        if nxt:
            return start + nxt.start()
        return len(text)
    # AI: Prefer inserting after YAML front matter when standard headings are absent.
    fm = re.match(r"^---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", text, re.DOTALL)
    if fm:
        return fm.end()
    return 0


def apply_clarifications_summary_to_plan(content: str) -> tuple[str, int]:
    """Strip any prior summary, then insert ``## Clarifications Needed`` when markers exist.

    Returns ``(updated_markdown, marker_count)``. When there are no markers, the
    body is returned with any stale summary section removed.
    """
    stripped = strip_clarifications_needed_section(content)
    markers = find_clarification_markers(stripped)
    if not markers:
        return stripped, 0
    section = _format_clarifications_needed_section(markers)
    pos = _insert_point_clarifications_section(stripped)
    before = stripped[:pos]
    after = stripped[pos:]
    if before and not before.endswith(("\n", "\r")):
        before += "\n"
    return before + section + after, len(markers)
