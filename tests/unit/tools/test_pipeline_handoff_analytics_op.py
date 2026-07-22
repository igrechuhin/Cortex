"""Dispatcher-level tests for pipeline_handoff graph-analytics operations.

Covers Gap 1 (analyze-experience-graph-queries.md Review Follow-Up):
coverage-true path (nodes exist), coverage-false / no-db path (fallback
signal), and write_failure_evals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.recorder import experience_db_path
from cortex.experience.store_core import ExperienceStoreCore
from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


def _seed_nodes(core: ExperienceStoreCore, session_id: str) -> None:
    """Append one passed + two failed siblings under one parent to a session."""
    statuses = (
        ("passed-1", ExperienceNodeStatus.COMPLETED, 1.0),
        ("failed-1", ExperienceNodeStatus.FAILED, None),
        ("failed-2", ExperienceNodeStatus.FAILED, None),
    )
    for node_id, status, fitness in statuses:
        _ = core.append_node(
            ExperienceNode(
                id=node_id,
                parent_id="root",
                session_id=session_id,
                status=status,
                fitness=fitness,
                label="checks",
            )
        )


def _seed_pair(tmp_path: Path, session_id: str = "sess-1") -> None:
    """Seed one task/session with a passed+failed sibling pair under one parent."""
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    task = core.create_task(ExperienceTask(spec="test task"))
    session = core.create_session(
        ExperienceSession(id=session_id, task_id=task.id, algorithm="commit")
    )
    _seed_nodes(core, session.id)


@pytest.mark.asyncio
async def test_preference_pairs_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="preference_pairs",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "no_coverage"
    assert result["coverage"] is False


@pytest.mark.asyncio
async def test_preference_pairs_coverage_false_when_session_has_no_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: store exists but has no nodes for the requested session.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = ExperienceStoreCore(experience_db_path(tmp_path))

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="preference_pairs",
            pipeline="analyze",
            data={"session_id": "sess-empty"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is False
    assert result["pairs"] == []


@pytest.mark.asyncio
async def test_preference_pairs_coverage_true_returns_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="preference_pairs",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is True
    assert len(result["pairs"]) == 2
    assert {p["failed_node"]["id"] for p in result["pairs"]} == {
        "failed-1",
        "failed-2",
    }


@pytest.mark.asyncio
async def test_repeated_failures_coverage_true_returns_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: two FAILED nodes with the same label => a repeated-failure cluster.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="repeated_failures",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is True
    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["count"] == 2


@pytest.mark.asyncio
async def test_repeated_failures_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="repeated_failures",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "no_coverage"
    assert result["coverage"] is False


@pytest.mark.asyncio
async def test_repeated_failures_coverage_false_when_session_has_no_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: store exists but has no nodes for the requested session.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = ExperienceStoreCore(experience_db_path(tmp_path))

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="repeated_failures",
            pipeline="analyze",
            data={"session_id": "sess-empty"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is False
    assert result["clusters"] == []


@pytest.mark.asyncio
async def test_fitness_by_task_type_coverage_false_when_no_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: store exists but has no sessions at all.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _ = ExperienceStoreCore(experience_db_path(tmp_path))

    # Act
    result = json.loads(
        await pipeline_handoff(operation="fitness_by_task_type", pipeline="analyze")
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is False
    assert result["results"] == []


@pytest.mark.asyncio
async def test_fitness_by_task_type_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="fitness_by_task_type", pipeline="analyze")
    )

    # Assert
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_fitness_by_task_type_coverage_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="fitness_by_task_type", pipeline="analyze")
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is True
    assert result["results"][0]["task_type"] == "commit"


@pytest.mark.asyncio
async def test_write_failure_evals_writes_evidence_linked_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="write_failure_evals",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["written"] == 2
    evals_path = tmp_path / ".cortex" / "evals" / "tasks" / "failure_based_evals.json"
    written = json.loads(evals_path.read_text(encoding="utf-8"))
    assert len(written) == 2
    assert all(entry["evidence"] for entry in written)


@pytest.mark.asyncio
async def test_write_failure_evals_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="write_failure_evals",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "no_coverage"
    assert result["written"] == 0


@pytest.mark.asyncio
async def test_preference_pairs_falls_back_to_current_session_when_no_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: no explicit session_id in data — must fall back to get_session_id().
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="preference_pairs", pipeline="analyze")
    )

    # Assert: falls back cleanly (store missing => no_coverage) instead of raising.
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_preference_pairs_falls_back_when_data_is_malformed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: data is a plain string that is not valid JSON.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="preference_pairs", pipeline="analyze", data="not-json-at-all"
        )
    )

    # Assert: malformed data is ignored, falls back to get_session_id() cleanly.
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_preference_pairs_falls_back_when_data_is_json_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: data parses as JSON but is a list, not an object with session_id.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="preference_pairs", pipeline="analyze", data="[1, 2, 3]"
        )
    )

    # Assert: non-dict payload is ignored, falls back to get_session_id() cleanly.
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_write_failure_evals_no_pairs_when_no_divergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: store has coverage but no failed/passed divergence.
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    task = core.create_task(ExperienceTask(spec="test task"))
    session = core.create_session(
        ExperienceSession(id="sess-1", task_id=task.id, algorithm="commit")
    )
    _ = core.append_node(
        ExperienceNode(
            id="passed-only",
            parent_id="root",
            session_id=session.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            label="checks",
        )
    )

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="write_failure_evals",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["written"] == 0
    assert result["task_ids"] == []
