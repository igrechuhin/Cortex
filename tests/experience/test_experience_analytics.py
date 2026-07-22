"""Unit tests for pure graph-pattern analytics over experience nodes."""

from __future__ import annotations

from cortex.experience.analytics import (
    fitness_by_task_type,
    preference_pairs,
    repeated_failures,
)
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
)


def _node(
    node_id: str,
    parent_id: str | None,
    status: ExperienceNodeStatus,
    session_id: str = "sess",
    fitness: float | None = None,
    label: str | None = None,
    artifact_ref: str | None = None,
) -> ExperienceNode:
    return ExperienceNode(
        id=node_id,
        parent_id=parent_id,
        session_id=session_id,
        status=status,
        fitness=fitness,
        label=label,
        artifact_ref=artifact_ref,
    )


def test_preference_pairs_single_sibling_pair() -> None:
    # Arrange
    passed = _node("passed", "parent", ExperienceNodeStatus.COMPLETED, fitness=1.0)
    failed = _node("failed", "parent", ExperienceNodeStatus.FAILED)
    nodes = [passed, failed]

    # Act
    pairs = preference_pairs(nodes)

    # Assert
    assert len(pairs) == 1
    assert pairs[0].parent_id == "parent"
    assert pairs[0].passed_node.id == "passed"
    assert pairs[0].failed_node.id == "failed"


def test_preference_pairs_multi_sibling_picks_highest_fitness_passed() -> None:
    # Arrange
    passed_low = _node(
        "passed-low", "parent", ExperienceNodeStatus.COMPLETED, fitness=0.2
    )
    passed_high = _node(
        "passed-high", "parent", ExperienceNodeStatus.COMPLETED, fitness=0.9
    )
    failed_a = _node("failed-a", "parent", ExperienceNodeStatus.FAILED)
    failed_b = _node("failed-b", "parent", ExperienceNodeStatus.FAILED)
    nodes = [passed_low, passed_high, failed_a, failed_b]

    # Act
    pairs = preference_pairs(nodes)

    # Assert: one pair per failed node, all bound to the best passed sibling
    assert len(pairs) == 2
    assert {pair.failed_node.id for pair in pairs} == {"failed-a", "failed-b"}
    assert all(pair.passed_node.id == "passed-high" for pair in pairs)


def test_preference_pairs_no_pair_when_all_same_status() -> None:
    # Arrange
    nodes = [
        _node("a", "parent", ExperienceNodeStatus.COMPLETED),
        _node("b", "parent", ExperienceNodeStatus.COMPLETED),
    ]

    # Act / Assert
    assert preference_pairs(nodes) == []


def test_preference_pairs_no_pair_when_no_passed_sibling() -> None:
    # Arrange: parent group with only FAILED siblings has no counterexample.
    nodes = [
        _node("a", "parent", ExperienceNodeStatus.FAILED),
        _node("b", "parent", ExperienceNodeStatus.FAILED),
    ]

    # Act / Assert
    assert preference_pairs(nodes) == []


def test_preference_pairs_tied_fitness_still_pairs_on_status_only() -> None:
    # Arrange: tied fitness values must not block a pair; status divergence
    # is the only pairing signal (strict pass/fail divergence rule).
    passed = _node("passed", "parent", ExperienceNodeStatus.COMPLETED, fitness=0.5)
    failed = _node("failed", "parent", ExperienceNodeStatus.FAILED, fitness=0.5)
    nodes = [passed, failed]

    # Act
    pairs = preference_pairs(nodes)

    # Assert
    assert len(pairs) == 1
    assert pairs[0].passed_node.id == "passed"
    assert pairs[0].failed_node.id == "failed"


def test_preference_pairs_excludes_orphan_nodes() -> None:
    # Arrange
    orphan_passed = _node("orphan-passed", None, ExperienceNodeStatus.COMPLETED)
    orphan_failed = _node("orphan-failed", None, ExperienceNodeStatus.FAILED)

    # Act / Assert
    assert preference_pairs([orphan_passed, orphan_failed]) == []


def test_preference_pairs_missing_artifact_ref_still_pairs() -> None:
    # Arrange
    passed = _node(
        "passed", "parent", ExperienceNodeStatus.COMPLETED, artifact_ref=None
    )
    failed = _node("failed", "parent", ExperienceNodeStatus.FAILED, artifact_ref=None)

    # Act
    pairs = preference_pairs([passed, failed])

    # Assert
    assert len(pairs) == 1
    assert pairs[0].passed_node.artifact_ref is None
    assert pairs[0].failed_node.artifact_ref is None


def test_repeated_failures_clusters_by_session_and_label() -> None:
    # Arrange
    nodes = [
        _node("f1", "p", ExperienceNodeStatus.FAILED, label="quality-gate"),
        _node("f2", "p", ExperienceNodeStatus.FAILED, label="quality-gate"),
        _node("f3", "p", ExperienceNodeStatus.FAILED, label="other"),
    ]

    # Act
    clusters = repeated_failures(nodes)

    # Assert
    assert len(clusters) == 1
    assert clusters[0].label == "quality-gate"
    assert clusters[0].count == 2
    assert set(clusters[0].node_ids) == {"f1", "f2"}


def test_repeated_failures_ignores_unlabeled_and_single_occurrences() -> None:
    # Arrange
    nodes = [
        _node("f1", "p", ExperienceNodeStatus.FAILED, label=None),
        _node("f2", "p", ExperienceNodeStatus.FAILED, label="rare"),
        _node("c1", "p", ExperienceNodeStatus.COMPLETED, label="quality-gate"),
    ]

    # Act / Assert
    assert repeated_failures(nodes) == []


def test_fitness_by_task_type_aggregates_across_sessions() -> None:
    # Arrange
    commit_session = ExperienceSession(id="s1", task_id="t1", algorithm="commit")
    implement_session = ExperienceSession(id="s2", task_id="t1", algorithm="implement")
    nodes_by_session = {
        "s1": [
            _node("n1", None, ExperienceNodeStatus.COMPLETED, fitness=0.5),
            _node("n2", None, ExperienceNodeStatus.COMPLETED, fitness=1.0),
        ],
        "s2": [_node("n3", None, ExperienceNodeStatus.COMPLETED, fitness=0.2)],
    }

    # Act
    stats = fitness_by_task_type([commit_session, implement_session], nodes_by_session)

    # Assert
    by_type = {s.task_type: s for s in stats}
    assert by_type["commit"].sample_count == 2
    assert by_type["commit"].avg_fitness == 0.75
    assert by_type["commit"].min_fitness == 0.5
    assert by_type["commit"].max_fitness == 1.0
    assert by_type["implement"].sample_count == 1


def test_fitness_by_task_type_skips_sessions_without_fitness_data() -> None:
    # Arrange
    session = ExperienceSession(id="s1", task_id="t1", algorithm="commit")
    nodes_by_session = {"s1": [_node("n1", None, ExperienceNodeStatus.RUNNING)]}

    # Act / Assert
    assert fitness_by_task_type([session], nodes_by_session) == []
