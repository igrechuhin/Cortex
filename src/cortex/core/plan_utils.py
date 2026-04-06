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
