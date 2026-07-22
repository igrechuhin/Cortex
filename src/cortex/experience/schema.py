"""SQLite schema and idempotent migrations for the experience store."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 2

_CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
)
"""

_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    spec TEXT NOT NULL,
    success_metric TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    algorithm TEXT NOT NULL,
    owner TEXT,
    progress TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_NODES = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES nodes(id),
    session_id TEXT NOT NULL REFERENCES sessions(id),
    artifact_ref TEXT,
    fitness REAL,
    status TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_NODE_SESSION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_nodes_session_step
ON nodes (session_id, step_number)
"""

# AI: rule_provenance links a Synapse rule id to the experience-store node
# pairs (failure -> fix) that justify it; PRIMARY KEY (rule_id, pair_id)
# makes re-citing the same pair idempotent (ON CONFLICT DO UPDATE bumps
# last_matched_at instead of duplicating rows). See plan
# synapse-rule-provenance.md.
_CREATE_RULE_PROVENANCE = """
CREATE TABLE IF NOT EXISTS rule_provenance (
    rule_id TEXT NOT NULL,
    pair_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    failed_node_id TEXT NOT NULL,
    passed_node_id TEXT NOT NULL,
    failure_class TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_matched_at TEXT NOT NULL,
    PRIMARY KEY (rule_id, pair_id)
)
"""

_CREATE_RULE_PROVENANCE_FAILURE_CLASS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_rule_provenance_failure_class
ON rule_provenance (failure_class)
"""


def migrate(connection: sqlite3.Connection) -> None:
    """Apply the experience schema; safe to call repeatedly (idempotent).

    Enables WAL journal mode to reduce lock contention between concurrent
    pipeline sessions writing best-effort experience records.
    """
    _ = connection.execute("PRAGMA journal_mode=WAL")
    for statement in (
        _CREATE_SCHEMA_VERSION,
        _CREATE_TASKS,
        _CREATE_SESSIONS,
        _CREATE_NODES,
        _CREATE_NODE_SESSION_INDEX,
        _CREATE_RULE_PROVENANCE,
        _CREATE_RULE_PROVENANCE_FAILURE_CLASS_INDEX,
    ):
        _ = connection.execute(statement)
    _ = connection.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    connection.commit()


def current_schema_version(connection: sqlite3.Connection) -> int:
    """Return the highest applied schema version (0 when unmigrated)."""
    try:
        row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    version = row[0] if row is not None else None
    return int(version) if isinstance(version, int) else 0
