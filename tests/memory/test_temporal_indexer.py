from __future__ import annotations

from datetime import date
from pathlib import Path

from cortex.memory.temporal_indexer import TemporalIndexer
from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)


def test_indexer_extracts_roadmap_status_facts(tmp_path: Path) -> None:
    root = tmp_path
    memory_bank = root / ".cortex" / "memory-bank"
    memory_bank.mkdir(parents=True)
    roadmap = memory_bank / "roadmap.md"
    _ = roadmap.write_text(
        "\n".join(
            [
                "## Pending plans (from .cortex/plans)",
                "- **Task A** - PENDING - first. Plan: .cortex/plans/task-a.md",
                "- **Task B** - PENDING - second. Plan: .cortex/plans/task-b.md",
                "- **Task C** - PENDING - third. Plan: .cortex/plans/task-c.md",
            ]
        ),
        encoding="utf-8",
    )
    store = TemporalMemoryStore(root / ".cortex" / "temporal.db")
    indexer = TemporalIndexer(store, root)

    added = indexer.index_file(roadmap)

    assert added == 3
    facts = store.query_as_of(
        date.today().isoformat(), category=TemporalFactCategory.STATUS
    )
    assert len(facts) == 3
    assert {fact.subject for fact in facts} == {"task-a", "task-b", "task-c"}


def test_check_contradiction_returns_open_conflicts(tmp_path: Path) -> None:
    store = TemporalMemoryStore(tmp_path / "temporal.db")
    indexer = TemporalIndexer(store, tmp_path)
    existing = TemporalFact(
        category=TemporalFactCategory.STATUS,
        subject="plan-alpha",
        predicate="status",
        object="PENDING",
        valid_from="2026-04-10",
        source_file="roadmap.md",
        source_line=1,
    )
    store.add_fact(existing)
    new_fact = TemporalFact(
        category=TemporalFactCategory.STATUS,
        subject="plan-alpha",
        predicate="status",
        object="DONE",
        valid_from="2026-04-11",
        source_file="roadmap.md",
        source_line=2,
    )

    conflicts = indexer.check_contradiction(new_fact)

    assert len(conflicts) == 1
    assert conflicts[0].object == "PENDING"


def test_indexer_skips_unknown_markdown_formats(tmp_path: Path) -> None:
    root = tmp_path
    memory_bank = root / ".cortex" / "memory-bank"
    memory_bank.mkdir(parents=True)
    file_path = memory_bank / "notes.md"
    _ = file_path.write_text("no recognized structured facts here", encoding="utf-8")
    store = TemporalMemoryStore(root / ".cortex" / "temporal.db")

    added = TemporalIndexer(store, root).index_file(file_path)

    assert added == 0
