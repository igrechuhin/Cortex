from __future__ import annotations

import sqlite3
from pathlib import Path

from cortex.memory.temporal_store import TemporalFact, TemporalMemoryStore, fact_id


def _build_fact(valid_from: str = "2026-04-01") -> TemporalFact:
    return TemporalFact(
        category="status",
        subject="improve-temporal-memory",
        predicate="state",
        object="PENDING",
        valid_from=valid_from,
        source_file=".cortex/roadmap.md",
        source_line=10,
    )


def test_temporal_store_initialization_creates_db_and_table(tmp_path: Path) -> None:
    db_path = tmp_path / "temporal.db"
    _ = TemporalMemoryStore(db_path=db_path)

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
            ("table", "memory_facts"),
        ).fetchone()
    assert row == ("memory_facts",)


def test_query_as_of_honors_validity_boundaries(tmp_path: Path) -> None:
    store = TemporalMemoryStore(db_path=tmp_path / "temporal.db")
    store.add_fact(_build_fact(valid_from="2026-04-10"))

    assert store.query_as_of("2026-04-09") == []
    assert len(store.query_as_of("2026-04-10")) == 1
    assert len(store.query_as_of("2026-04-15")) == 1


def test_invalidate_closes_open_fact_window(tmp_path: Path) -> None:
    store = TemporalMemoryStore(db_path=tmp_path / "temporal.db")
    fact = _build_fact(valid_from="2026-04-01")
    store.add_fact(fact)

    changed = store.invalidate(
        subject=fact.subject,
        predicate=fact.predicate,
        object=fact.object,
        ended="2026-04-20",
    )

    assert changed is True
    assert len(store.query_as_of("2026-04-19")) == 1
    assert store.query_as_of("2026-04-20") == []


def test_add_fact_is_idempotent_for_same_deterministic_id(tmp_path: Path) -> None:
    store = TemporalMemoryStore(db_path=tmp_path / "temporal.db")
    expected_id = fact_id(
        category="status",
        subject="improve-temporal-memory",
        predicate="state",
        object_value="PENDING",
    )
    first = _build_fact(valid_from="2026-04-01")
    second = _build_fact(valid_from="2026-04-01")

    store.add_fact(first)
    store.add_fact(second)

    rows = store.query_as_of("2026-04-15")
    assert len(rows) == 1
    assert rows[0].id == expected_id
