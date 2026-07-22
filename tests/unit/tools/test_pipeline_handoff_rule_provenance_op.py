"""Dispatcher-level tests for pipeline_handoff rule-provenance operations.

Covers plan synapse-rule-provenance.md: record_rule_provenance,
refresh_rule_matches, rule_evidence, pruning_candidates — coverage-true/false
paths and negative cases (unknown rule id, missing required fields).
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
from cortex.tools.session.pipeline_handoff_rule_provenance import dispatch
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)


def _seed_pair(tmp_path: Path, session_id: str = "sess-1") -> None:
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    task = core.create_task(ExperienceTask(spec="test task"))
    session = core.create_session(
        ExperienceSession(id=session_id, task_id=task.id, algorithm="commit")
    )
    _ = core.append_node(
        ExperienceNode(
            id="passed-1",
            parent_id="root",
            session_id=session.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            label="checks",
        )
    )
    _ = core.append_node(
        ExperienceNode(
            id="failed-1",
            parent_id="root",
            session_id=session.id,
            status=ExperienceNodeStatus.FAILED,
            label="checks",
        )
    )


@pytest.mark.asyncio
async def test_record_rule_provenance_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data={
                "session_id": "sess-1",
                "rule_id": "rule-1",
                "failure_class": "checks",
            },
        )
    )

    # Assert
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_record_rule_provenance_missing_rule_id_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data={"session_id": "sess-1", "failure_class": "checks"},
        )
    )

    # Assert
    assert result["status"] == "error"
    assert "rule_id" in result["error"]


@pytest.mark.asyncio
async def test_record_rule_provenance_missing_failure_class_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data={"session_id": "sess-1", "rule_id": "rule-1"},
        )
    )

    # Assert
    assert result["status"] == "error"
    assert "failure_class" in result["error"]


@pytest.mark.asyncio
async def test_record_rule_provenance_writes_citation_from_session_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data={
                "session_id": "sess-1",
                "rule_id": "rule-1",
                "failure_class": "checks",
            },
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["recorded"] == 1
    assert result["provenance"]["rule_id"] == "rule-1"
    assert result["provenance"]["pair_ids"] == ["failed-1"]


@pytest.mark.asyncio
async def test_record_rule_provenance_filters_by_pair_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act: pair_ids filter that matches no pair in the session.
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data={
                "session_id": "sess-1",
                "rule_id": "rule-1",
                "failure_class": "checks",
                "pair_ids": ["nonexistent"],
            },
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["recorded"] == 0
    assert result["provenance"] is None


@pytest.mark.asyncio
async def test_refresh_rule_matches_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="refresh_rule_matches",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_refresh_rule_matches_returns_refreshed_rule_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)
    _ = await pipeline_handoff(
        operation="record_rule_provenance",
        pipeline="analyze",
        data={"session_id": "sess-1", "rule_id": "rule-1", "failure_class": "checks"},
    )

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="refresh_rule_matches",
            pipeline="analyze",
            data={"session_id": "sess-1"},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["refreshed"] == ["rule-1"]


@pytest.mark.asyncio
async def test_rule_evidence_missing_rule_id_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="rule_evidence", pipeline="analyze", data={})
    )

    # Assert
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_rule_evidence_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="rule_evidence", pipeline="analyze", data={"rule_id": "rule-1"}
        )
    )

    # Assert
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_rule_evidence_unknown_rule_returns_empty_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="rule_evidence", pipeline="analyze", data={"rule_id": "unknown"}
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is False
    assert result["evidence"] == []


@pytest.mark.asyncio
async def test_rule_evidence_returns_cited_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)
    _ = await pipeline_handoff(
        operation="record_rule_provenance",
        pipeline="analyze",
        data={"session_id": "sess-1", "rule_id": "rule-1", "failure_class": "checks"},
    )

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="rule_evidence", pipeline="analyze", data={"rule_id": "rule-1"}
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["coverage"] is True
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["failed_node_id"] == "failed-1"


@pytest.mark.asyncio
async def test_pruning_candidates_no_coverage_when_store_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="pruning_candidates", pipeline="analyze")
    )

    # Assert
    assert result["status"] == "no_coverage"


@pytest.mark.asyncio
async def test_pruning_candidates_uses_default_window_when_unspecified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(operation="pruning_candidates", pipeline="analyze")
    )

    # Assert
    assert result["status"] == "ok"
    assert result["window_days"] == 90.0
    assert result["candidates"] == []


@pytest.mark.asyncio
async def test_pruning_candidates_respects_custom_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="pruning_candidates",
            pipeline="analyze",
            data={"window_days": 30},
        )
    )

    # Assert
    assert result["status"] == "ok"
    assert result["window_days"] == 30.0


def test_dispatch_returns_none_for_unrelated_operation(tmp_path: Path) -> None:
    # Arrange / Act
    result = dispatch(tmp_path, "preference_pairs", "sess-1", None)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_record_rule_provenance_invalid_json_treated_as_missing_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: data is not valid JSON at all (falls back to {} in _parse_payload).
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    _seed_pair(tmp_path)

    # Act
    result = json.loads(
        await pipeline_handoff(
            operation="record_rule_provenance",
            pipeline="analyze",
            data="not-json-at-all",
        )
    )

    # Assert
    assert result["status"] == "error"
    assert "rule_id" in result["error"]
