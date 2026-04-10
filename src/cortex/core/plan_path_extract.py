"""Extract probable file path globs from plan markdown for session goal scope."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Backticked paths like `src/foo.py` or `.cortex/plans/x.md`
_BACKTICK_PATH = re.compile(
    r"`((?:[\w./-]|\.cortex/)+?\.(?:py|md|json|ya?ml|toml|txt))`"
)
# Loose path-like tokens (segments with slash)
_SLASH_PATH = re.compile(r"\b((?:\.cortex/)?(?:src|tests)/[\w./-]+\.(?:py|md))\b")


def extract_file_patterns_from_plan(text: str) -> list[str]:
    """Return deduplicated path-like strings from plan markdown."""
    found: list[str] = []
    for pattern in _BACKTICK_PATH, _SLASH_PATH:
        for m in pattern.finditer(text):
            raw = m.group(1).strip()
            if raw and raw not in found:
                found.append(raw)
    return _dedupe_preserve_order(found)


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
