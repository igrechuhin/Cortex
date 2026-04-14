"""Typed memory classification primitives."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import Field

from cortex.tools.models_base import StrictBaseModel


class MemoryType(str, Enum):
    DECISION = "decision"
    PREFERENCE = "preference"
    MILESTONE = "milestone"
    PROBLEM = "problem"
    STATUS = "status"


MEMORY_TYPE_PATTERNS: dict[MemoryType, list[str]] = {
    MemoryType.DECISION: ["decided", "chose", "switched to", "will use", "agreed"],
    MemoryType.PREFERENCE: ["always", "never", "prefer", "avoid", "policy"],
    MemoryType.MILESTONE: [
        "completed",
        "merged",
        "done",
        "shipped",
        "achieved",
        "fixed",
    ],
    MemoryType.PROBLEM: ["failed", "broke", "bug", "error", "blocked", "issue"],
    MemoryType.STATUS: [],
}


def _compile_patterns() -> dict[MemoryType, tuple[re.Pattern[str], ...]]:
    compiled: dict[MemoryType, tuple[re.Pattern[str], ...]] = {}
    for memory_type, patterns in MEMORY_TYPE_PATTERNS.items():
        compiled[memory_type] = tuple(
            re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
            for pattern in patterns
        )
    return compiled


_COMPILED_PATTERNS = _compile_patterns()
_PRIORITY_ORDER = (
    MemoryType.DECISION,
    MemoryType.PREFERENCE,
    MemoryType.MILESTONE,
    MemoryType.PROBLEM,
)


def classify_text(text: str) -> MemoryType:
    for memory_type in _PRIORITY_ORDER:
        if any(pattern.search(text) for pattern in _COMPILED_PATTERNS[memory_type]):
            return memory_type
    return MemoryType.STATUS


class MemoryEntry(StrictBaseModel):
    content: str
    memory_type: MemoryType
    tags: list[str] = Field(default_factory=list)
    created: str = ""
