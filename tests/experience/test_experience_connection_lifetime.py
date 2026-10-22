"""Real SQLite regressions for experience-store connection ownership."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.recorder import experience_db_path
from cortex.experience.resume import scan_incomplete_runs
from cortex.experience.store_core import ExperienceStoreCore


class _TransactionalStore(ExperienceStoreCore):
    def transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        return self._connect()


class _RejectingRowFactoryConnection(sqlite3.Connection):
    def __setattr__(self, name: str, value: object) -> None:
        if name == "row_factory":
            raise RuntimeError("row factory configuration failed")
        super().__setattr__(name, value)


@contextmanager
def _retained_connections(
    monkeypatch: pytest.MonkeyPatch,
    factory: type[sqlite3.Connection] = sqlite3.Connection,
) -> Iterator[list[sqlite3.Connection]]:
    original_connect = sqlite3.connect
    connections: list[sqlite3.Connection] = []

    def connect(database: Path, timeout: float) -> sqlite3.Connection:
        connection = original_connect(database, timeout=timeout, factory=factory)
        connections.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        try:
            yield connections
        finally:
            for connection in connections:
                connection.close()


def _assert_closed(connections: list[sqlite3.Connection]) -> None:
    assert connections
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            _ = connection.execute("SELECT 1")


def _seed_scan_history(core: ExperienceStoreCore, now: datetime) -> set[str]:
    task = core.create_task(ExperienceTask(spec="pipeline:commit"))
    owners = {f"sess-{index}" for index in range(20)}
    for owner in sorted(owners):
        session = core.create_session(
            ExperienceSession(task_id=task.id, algorithm="commit", owner=owner)
        )
        _ = core.append_node(
            ExperienceNode(
                session_id=session.id,
                label="checks:running",
                status=ExperienceNodeStatus.RUNNING,
                created_at=now.isoformat(),
            )
        )
    return owners


def test_connection_commits_and_closes_before_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    task = ExperienceTask(spec="persisted transaction")
    with _retained_connections(monkeypatch) as connections:
        core = _TransactionalStore(tmp_path / "experience.db")

        # Act: no explicit commit, so the transaction context must commit.
        with core.transaction() as connection:
            _ = connection.execute(
                """
                INSERT INTO tasks (id, spec, success_metric, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task.id, task.spec, task.success_metric, task.created_at),
            )

        # Assert: the writer is closed before a separate connection reads it.
        _assert_closed(connections)
        assert core.get_task(task.id) == task
        _assert_closed(connections)


def test_connection_rolls_back_original_exception_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    error = RuntimeError("transaction body failed")
    with _retained_connections(monkeypatch) as connections:
        core = _TransactionalStore(tmp_path / "experience.db")
        task = core.create_task(ExperienceTask(spec="original spec"))

        # Act
        with pytest.raises(RuntimeError) as raised:
            with core.transaction() as connection:
                _ = connection.execute(
                    "UPDATE tasks SET spec = ? WHERE id = ?", ("changed", task.id)
                )
                raise error

        # Assert
        assert raised.value is error
        _assert_closed(connections)
        assert core.get_task(task.id) == task
        _assert_closed(connections)


def test_initialization_failure_closes_acquired_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: real migration SQL must fail against an invalid database.
    db_path = tmp_path / "experience.db"
    _ = db_path.write_bytes(b"not a SQLite database" * 10)
    with _retained_connections(monkeypatch) as connections:
        # Act
        with pytest.raises(sqlite3.DatabaseError):
            _ = ExperienceStoreCore(db_path)

        # Assert
        assert len(connections) == 1
        _assert_closed(connections)


def test_configuration_failure_closes_acquired_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: a real SQLite subclass rejects the row-factory assignment.
    with _retained_connections(
        monkeypatch, _RejectingRowFactoryConnection
    ) as connections:
        # Act
        with pytest.raises(RuntimeError, match="row factory configuration failed"):
            _ = ExperienceStoreCore(tmp_path / "experience.db")

        # Assert
        assert len(connections) == 1
        _assert_closed(connections)


def test_repeated_scan_closes_every_retained_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: retain every real handle so garbage collection cannot hide leaks.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with _retained_connections(monkeypatch) as connections:
        core = ExperienceStoreCore(experience_db_path(tmp_path))
        owners = _seed_scan_history(core, now)
        _assert_closed(connections)

        # Act / Assert: each bounded scan traverses all synthetic sessions.
        for _ in range(5):
            before = len(connections)
            runs = scan_incomplete_runs(tmp_path, ttl_seconds=3600.0, now=now)
            assert {run.owner for run in runs} == owners
            assert all(run.frontier_phase == "checks" for run in runs)
            assert len(connections) > before
            _assert_closed(connections[before:])
