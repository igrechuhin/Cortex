"""SQLite schema and idempotent migration for the task-embedding index.

Lives in the same ``experience.db`` file as the task/session/node tables
(see ``cortex.experience.schema``); additive-only, run independently so the
embedding index has no hard import-time dependency on the store schema.
"""

from __future__ import annotations

import sqlite3

_CREATE_TASK_EMBEDDINGS = """
CREATE TABLE IF NOT EXISTS task_embeddings (
    task_id TEXT PRIMARY KEY REFERENCES tasks(id),
    vector BLOB NOT NULL,
    dim INTEGER NOT NULL,
    encoder_version TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def migrate_embeddings(connection: sqlite3.Connection) -> None:
    """Create the ``task_embeddings`` table when missing; safe to call repeatedly."""
    _ = connection.execute("PRAGMA journal_mode=WAL")
    _ = connection.execute(_CREATE_TASK_EMBEDDINGS)
    connection.commit()
