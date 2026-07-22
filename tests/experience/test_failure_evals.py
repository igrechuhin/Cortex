"""Unit tests for graph-preference-pair -> failure_based_evals.json mapping."""

from __future__ import annotations

import json
from pathlib import Path

from cortex.experience.analytics_models import PreferencePair
from cortex.experience.failure_evals import (
    preference_pairs_to_eval_tasks,
    upsert_eval_tasks,
)
from cortex.experience.models import ExperienceNode, ExperienceNodeStatus


def _pair(
    failed_id: str = "failed-1",
    passed_id: str = "passed-1",
    parent_id: str = "parent-1",
    session_id: str = "sess-1",
    artifact_ref: str | None = "artifacts/failed-1.json",
) -> PreferencePair:
    failed = ExperienceNode(
        id=failed_id,
        parent_id=parent_id,
        session_id=session_id,
        status=ExperienceNodeStatus.FAILED,
        label="type_check",
        artifact_ref=artifact_ref,
    )
    passed = ExperienceNode(
        id=passed_id,
        parent_id=parent_id,
        session_id=session_id,
        status=ExperienceNodeStatus.COMPLETED,
        fitness=1.0,
        label="type_check",
        artifact_ref="artifacts/passed-1.json",
    )
    return PreferencePair(
        parent_id=parent_id,
        session_id=session_id,
        passed_node=passed,
        failed_node=failed,
    )


def test_preference_pairs_to_eval_tasks_maps_evidence() -> None:
    # Arrange
    pair = _pair()

    # Act
    tasks = preference_pairs_to_eval_tasks([pair])

    # Assert
    assert len(tasks) == 1
    task = tasks[0]
    assert task.id == "graph-failed-1"
    assert "type_check" in task.name
    assert "passed-1" in task.expected_outcome
    assert len(task.evidence) == 2
    assert task.evidence[0].node_id == "failed-1"
    assert task.evidence[0].artifact_ref == "artifacts/failed-1.json"
    assert task.evidence[0].confidence_source == "graph"
    assert task.evidence[1].node_id == "passed-1"


def test_preference_pairs_to_eval_tasks_handles_missing_label() -> None:
    # Arrange
    failed = ExperienceNode(
        id="failed-nolabel",
        parent_id="p",
        session_id="s",
        status=ExperienceNodeStatus.FAILED,
    )
    passed = ExperienceNode(
        id="passed-nolabel",
        parent_id="p",
        session_id="s",
        status=ExperienceNodeStatus.COMPLETED,
        fitness=1.0,
    )
    pair = PreferencePair(
        parent_id="p", session_id="s", passed_node=passed, failed_node=failed
    )

    # Act
    tasks = preference_pairs_to_eval_tasks([pair])

    # Assert: falls back to node id when label is None
    assert "failed-nolabel" in tasks[0].name
    assert tasks[0].evidence[0].artifact_ref is None


def test_upsert_eval_tasks_appends_to_new_file(tmp_path: Path) -> None:
    # Arrange
    tasks_path = tmp_path / "failure_based_evals.json"
    tasks = preference_pairs_to_eval_tasks([_pair()])

    # Act
    written_ids = upsert_eval_tasks(tasks_path, tasks)

    # Assert
    assert written_ids == ["graph-failed-1"]
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "graph-failed-1"
    assert data[0]["evidence"][0]["node_id"] == "failed-1"
    assert "token_budget_baseline" not in data[0]


def test_upsert_eval_tasks_preserves_unrelated_existing_entries(
    tmp_path: Path,
) -> None:
    # Arrange: pre-existing hand-written entry with no evidence field.
    tasks_path = tmp_path / "failure_based_evals.json"
    existing = [
        {
            "id": "failure-hand-written",
            "name": "Hand-written entry",
            "description": "desc",
            "category": "pre_commit",
            "expected_tools": ["some_tool"],
            "expected_outcome": "outcome",
            "common_failure_modes": ["mode"],
            "usage_query": "some_tool",
        }
    ]
    _ = tasks_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    tasks = preference_pairs_to_eval_tasks([_pair()])

    # Act
    _ = upsert_eval_tasks(tasks_path, tasks)

    # Assert
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    hand_written = next(e for e in data if e["id"] == "failure-hand-written")
    assert hand_written == existing[0]
    assert any(e["id"] == "graph-failed-1" for e in data)


def test_upsert_eval_tasks_idempotent_on_repeated_calls(tmp_path: Path) -> None:
    # Arrange
    tasks_path = tmp_path / "failure_based_evals.json"
    tasks = preference_pairs_to_eval_tasks([_pair()])

    # Act: call twice with the same pair.
    _ = upsert_eval_tasks(tasks_path, tasks)
    written_ids_second = upsert_eval_tasks(tasks_path, tasks)

    # Assert: no duplicate entry, same id written both times.
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert written_ids_second == ["graph-failed-1"]


def test_upsert_eval_tasks_writes_empty_array_for_no_tasks(tmp_path: Path) -> None:
    # Arrange: no pre-existing file, no new tasks.
    tasks_path = tmp_path / "failure_based_evals.json"

    # Act
    written_ids = upsert_eval_tasks(tasks_path, [])

    # Assert
    assert written_ids == []
    assert json.loads(tasks_path.read_text(encoding="utf-8")) == []


def test_upsert_eval_tasks_treats_blank_existing_file_as_empty(
    tmp_path: Path,
) -> None:
    # Arrange: pre-existing file is present but blank (no content to parse).
    tasks_path = tmp_path / "failure_based_evals.json"
    _ = tasks_path.write_text("", encoding="utf-8")
    tasks = preference_pairs_to_eval_tasks([_pair()])

    # Act
    written_ids = upsert_eval_tasks(tasks_path, tasks)

    # Assert
    assert written_ids == ["graph-failed-1"]
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_upsert_eval_tasks_treats_non_list_existing_json_as_empty(
    tmp_path: Path,
) -> None:
    # Arrange: pre-existing file holds a JSON object, not the expected array.
    tasks_path = tmp_path / "failure_based_evals.json"
    _ = tasks_path.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")
    tasks = preference_pairs_to_eval_tasks([_pair()])

    # Act
    written_ids = upsert_eval_tasks(tasks_path, tasks)

    # Assert: malformed existing content is discarded, not merged.
    assert written_ids == ["graph-failed-1"]
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "graph-failed-1"
