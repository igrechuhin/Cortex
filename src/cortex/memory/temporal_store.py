"""SQLite-backed temporal fact store."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

_FACT_KEY_SEPARATOR = "\x1f"


def fact_id(category: str, subject: str, predicate: str, object_value: str) -> str:
    """Return deterministic fact id for logical identity fields."""
    key = _FACT_KEY_SEPARATOR.join([category, subject, predicate, object_value])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


class TemporalFact(BaseModel):
    """Temporal memory fact row."""

    id: str | None = None
    category: str
    subject: str
    predicate: str
    object: str
    valid_from: str
    valid_to: str | None = None
    source_file: str
    source_line: int
    created_at: str = Field(default_factory=_utc_now_iso)

    @model_validator(mode="after")
    def _ensure_id(self) -> TemporalFact:
        if self.id:
            return self
        self.id = fact_id(
            category=self.category,
            subject=self.subject,
            predicate=self.predicate,
            object_value=self.object,
        )
        return self


class TemporalMemoryStore:
    """SQLite temporal store with validity-window queries."""

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS memory_facts (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        subject TEXT NOT NULL,
        predicate TEXT NOT NULL,
        object TEXT NOT NULL,
        valid_from TEXT NOT NULL,
        valid_to TEXT,
        source_file TEXT NOT NULL,
        source_line INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as connection:
            _ = connection.execute(self._CREATE_SQL)
            connection.commit()

    def add_fact(self, fact: TemporalFact) -> None:
        query = """
        INSERT OR IGNORE INTO memory_facts (
            id, category, subject, predicate, object,
            valid_from, valid_to, source_file, source_line, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with sqlite3.connect(self._db_path) as connection:
            _ = connection.execute(
                query,
                (
                    fact.id,
                    fact.category,
                    fact.subject,
                    fact.predicate,
                    fact.object,
                    fact.valid_from,
                    fact.valid_to,
                    fact.source_file,
                    fact.source_line,
                    fact.created_at,
                ),
            )
            connection.commit()

    def invalidate(self, subject: str, predicate: str, object: str, ended: str) -> bool:
        query = """
        UPDATE memory_facts
        SET valid_to = ?
        WHERE subject = ? AND predicate = ? AND object = ? AND valid_to IS NULL
        """
        with sqlite3.connect(self._db_path) as connection:
            cursor = connection.execute(query, (ended, subject, predicate, object))
            connection.commit()
        return cursor.rowcount > 0

    def query_as_of(
        self, date: str, subject: str | None = None, category: str | None = None
    ) -> list[TemporalFact]:
        filters = ["valid_from <= ?", "(valid_to IS NULL OR valid_to > ?)"]
        params: list[str] = [date, date]
        if subject is not None:
            filters.append("subject = ?")
            params.append(subject)
        if category is not None:
            filters.append("category = ?")
            params.append(category)
        query = f"SELECT * FROM memory_facts WHERE {' AND '.join(filters)}"
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()
        return [TemporalFact.model_validate(dict(row)) for row in rows]

    def current_facts(self, subject: str | None = None) -> list[TemporalFact]:
        today = date.today().isoformat()
        return self.query_as_of(date=today, subject=subject)

    def all_facts(
        self, subject: str | None = None, category: str | None = None
    ) -> list[TemporalFact]:
        filters: list[str] = []
        params: list[str] = []
        if subject is not None:
            filters.append("subject = ?")
            params.append(subject)
        if category is not None:
            filters.append("category = ?")
            params.append(category)
        where = f" WHERE {' AND '.join(filters)}" if filters else ""
        query = "SELECT * FROM memory_facts" + where
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()
        return [TemporalFact.model_validate(dict(row)) for row in rows]
