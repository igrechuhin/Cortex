"""Temporal memory timeline query helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)


class MemoryTimelineInput(BaseModel):
    subject: str | None = None
    category: TemporalFactCategory | None = None
    as_of: str | None = None
    show_invalidated: bool = False


class MemoryTimelineResult(BaseModel):
    facts: list[TemporalFact]
    queried_as_of: str
    total: int


def _resolve_as_of(value: str | None) -> str:
    return value if value is not None else date.today().isoformat()


def memory_timeline_handle(
    input_data: MemoryTimelineInput, project_root: Path
) -> MemoryTimelineResult:
    store = TemporalMemoryStore(project_root / ".cortex" / "temporal.db")
    as_of = _resolve_as_of(input_data.as_of)
    if input_data.show_invalidated:
        facts = store.all_facts(
            subject=input_data.subject, category=input_data.category
        )
    else:
        facts = store.query_as_of(
            date=as_of, subject=input_data.subject, category=input_data.category
        )
    return MemoryTimelineResult(facts=facts, queried_as_of=as_of, total=len(facts))
