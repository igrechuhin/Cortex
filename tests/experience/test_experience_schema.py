"""Unit tests for experience-store schema migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from cortex.experience.schema import (
    SCHEMA_VERSION,
    current_schema_version,
    migrate,
)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_migrate_creates_tasks_sessions_nodes_tables(tmp_path: Path) -> None:
    # Arrange
    connection = sqlite3.connect(tmp_path / "experience.db")

    # Act
    migrate(connection)

    # Assert
    tables = _table_names(connection)
    assert {"tasks", "sessions", "nodes", "schema_version"} <= tables
    connection.close()


def test_migrate_creates_rule_provenance_table(tmp_path: Path) -> None:
    # Arrange
    connection = sqlite3.connect(tmp_path / "experience.db")

    # Act
    migrate(connection)

    # Assert
    tables = _table_names(connection)
    assert "rule_provenance" in tables
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(rule_provenance)").fetchall()
    }
    assert columns == {
        "rule_id",
        "pair_id",
        "session_id",
        "parent_id",
        "failed_node_id",
        "passed_node_id",
        "failure_class",
        "created_at",
        "last_matched_at",
    }
    connection.close()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    # Arrange
    connection = sqlite3.connect(tmp_path / "experience.db")

    # Act
    migrate(connection)
    migrate(connection)

    # Assert
    assert current_schema_version(connection) == SCHEMA_VERSION
    connection.close()


def test_migrate_enables_wal_journal_mode(tmp_path: Path) -> None:
    # Arrange
    connection = sqlite3.connect(tmp_path / "experience.db")

    # Act
    migrate(connection)

    # Assert
    row = connection.execute("PRAGMA journal_mode").fetchone()
    assert row == ("wal",)
    connection.close()


def test_current_schema_version_zero_before_migration(tmp_path: Path) -> None:
    # Arrange
    connection = sqlite3.connect(tmp_path / "experience.db")

    # Act / Assert
    assert current_schema_version(connection) == 0
    connection.close()
