"""Unit tests for frontier/incomplete-run queries on the experience store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cortex.experience.lifecycle import RUN_ABANDONED_LABEL, RUN_CLEARED_LABEL
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.store import ExperienceStore
from cortex.experience.store_core import ExperienceStoreCore

_TTL = 4 * 3600.0


def _seed_session(
    core: ExperienceStoreCore, owner: str = "sess", pipeline: str = "commit"
) -> ExperienceSession:
    task = core.create_task(ExperienceTask(spec=f"pipeline:{pipeline}"))
    return core.create_session(
        ExperienceSession(task_id=task.id, algorithm=pipeline, owner=owner)
    )


def _append(
    core: ExperienceStoreCore,
    session_id: str,
    label: str,
    status: ExperienceNodeStatus,
    step: int,
    created_at: str | None = None,
) -> ExperienceNode:
    node = ExperienceNode(
        session_id=session_id, label=label, status=status, step_number=step
    )
    if created_at is not None:
        node = node.model_copy(update={"created_at": created_at})
    return core.append_node(node)


def test_frontier_returns_window_projection(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    _ = _append(core, session.id, "checks:completed", ExperienceNodeStatus.COMPLETED, 1)
    _ = _append(core, session.id, "docs:running", ExperienceNodeStatus.RUNNING, 2)

    # Act
    view = core.frontier(session.id)

    # Assert
    assert view is not None
    assert view.completed_phases == ["checks"]
    assert view.frontier_phase == "docs"
    assert view.latest.status is ExperienceNodeStatus.RUNNING


def test_frontier_empty_after_cleared_marker(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    _ = _append(core, session.id, "checks:completed", ExperienceNodeStatus.COMPLETED, 1)
    _ = _append(core, session.id, RUN_CLEARED_LABEL, ExperienceNodeStatus.COMPLETED, 2)

    # Act / Assert
    assert core.frontier(session.id) is None
    assert core.frontier("missing") is None


def test_incomplete_runs_lists_fresh_open_windows(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    open_session = _seed_session(core, owner="open", pipeline="commit")
    ended_session = _seed_session(core, owner="ended", pipeline="implement")
    _ = _append(
        core, open_session.id, "checks:completed", ExperienceNodeStatus.COMPLETED, 1
    )
    _ = _append(
        core, ended_session.id, "code:completed", ExperienceNodeStatus.COMPLETED, 1
    )
    _ = _append(
        core, ended_session.id, RUN_CLEARED_LABEL, ExperienceNodeStatus.COMPLETED, 2
    )

    # Act
    runs = core.incomplete_runs(_TTL)

    # Assert
    assert [run.owner for run in runs] == ["open"]
    assert runs[0].pipeline == "commit"
    assert runs[0].frontier_phase == "checks"
    assert runs[0].frontier_status is ExperienceNodeStatus.COMPLETED


def test_incomplete_runs_excludes_stale_windows(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    stale_stamp = (datetime.now(UTC) - timedelta(hours=9)).isoformat(timespec="seconds")
    _ = _append(
        core,
        session.id,
        "checks:running",
        ExperienceNodeStatus.RUNNING,
        1,
        created_at=stale_stamp,
    )

    # Act / Assert
    assert core.incomplete_runs(_TTL) == []


def test_mark_abandoned_runs_closes_stale_windows(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    stale_stamp = (datetime.now(UTC) - timedelta(hours=9)).isoformat(timespec="seconds")
    _ = _append(
        core,
        session.id,
        "checks:running",
        ExperienceNodeStatus.RUNNING,
        1,
        created_at=stale_stamp,
    )

    # Act
    abandoned = core.mark_abandoned_runs(_TTL)

    # Assert
    assert abandoned == [session.id]
    latest = core.latest_node(session.id)
    assert latest is not None
    assert latest.label == RUN_ABANDONED_LABEL
    assert latest.status is ExperienceNodeStatus.FAILED
    assert core.frontier(session.id) is None
    # AI: second sweep must be a no-op — abandoned windows stay closed.
    assert core.mark_abandoned_runs(_TTL) == []


def test_mark_abandoned_runs_keeps_fresh_windows(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    _ = _append(core, session.id, "checks:running", ExperienceNodeStatus.RUNNING, 1)

    # Act / Assert
    assert core.mark_abandoned_runs(_TTL) == []
    assert len(core.incomplete_runs(_TTL)) == 1


def test_update_node_status_enforces_transitions(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    node = core.append_node(
        ExperienceNode(session_id=session.id, status=ExperienceNodeStatus.PENDING)
    )

    # Act / Assert: pending -> running -> completed is legal.
    assert core.update_node_status(node.id, ExperienceNodeStatus.RUNNING) is True
    assert core.update_node_status(node.id, ExperienceNodeStatus.COMPLETED) is True
    # Terminal states are immutable.
    assert core.update_node_status(node.id, ExperienceNodeStatus.RUNNING) is False
    assert core.update_node_status(node.id, ExperienceNodeStatus.FAILED) is False
    fetched = core.get_node(node.id)
    assert fetched is not None
    assert fetched.status is ExperienceNodeStatus.COMPLETED


def test_update_node_status_rejects_missing_and_invalid(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    node = core.append_node(
        ExperienceNode(session_id=session.id, status=ExperienceNodeStatus.PENDING)
    )

    # Act / Assert
    assert core.update_node_status("missing", ExperienceNodeStatus.RUNNING) is False
    assert core.update_node_status(node.id, ExperienceNodeStatus.COMPLETED) is False


def test_list_sessions_returns_all_rows(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    _ = _seed_session(core, owner="a", pipeline="commit")
    _ = _seed_session(core, owner="b", pipeline="implement")

    # Act
    sessions = core.list_sessions()

    # Assert
    assert {session.owner for session in sessions} == {"a", "b"}


@pytest.mark.asyncio
async def test_async_facade_exposes_queries(tmp_path: Path) -> None:
    # Arrange
    store = ExperienceStore.from_db_path(tmp_path / "experience.db")
    session = _seed_session(store.core)
    node = store.core.append_node(
        ExperienceNode(
            session_id=session.id,
            label="checks:running",
            status=ExperienceNodeStatus.RUNNING,
        )
    )

    # Act
    view = await store.frontier(session.id)
    runs = await store.incomplete_runs(_TTL)
    sessions = await store.list_sessions()
    updated = await store.update_node_status(node.id, ExperienceNodeStatus.COMPLETED)
    abandoned = await store.mark_abandoned_runs(_TTL)

    # Assert
    assert view is not None
    assert view.frontier_phase == "checks"
    assert [run.session_id for run in runs] == [session.id]
    assert len(sessions) == 1
    assert updated is True
    assert abandoned == []
