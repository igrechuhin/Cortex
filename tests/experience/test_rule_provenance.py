"""Unit tests for pure rule-provenance aggregation and staleness computations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cortex.experience.analytics_models import PreferencePair
from cortex.experience.models import ExperienceNode, ExperienceNodeStatus
from cortex.experience.rule_provenance import (
    failure_classes_from_pairs,
    group_provenance,
    pruning_candidates,
)
from cortex.experience.rule_provenance_models import RuleProvenanceRecord


def _record(
    rule_id: str,
    pair_id: str,
    failure_class: str = "checks",
    created_at: str = "2026-01-01T00:00:00+00:00",
    last_matched_at: str = "2026-01-01T00:00:00+00:00",
) -> RuleProvenanceRecord:
    return RuleProvenanceRecord(
        rule_id=rule_id,
        pair_id=pair_id,
        session_id="sess-1",
        parent_id="parent-1",
        failed_node_id=f"failed-{pair_id}",
        passed_node_id=f"passed-{pair_id}",
        failure_class=failure_class,
        created_at=created_at,
        last_matched_at=last_matched_at,
    )


def _pair(failed_id: str, label: str | None = "checks") -> PreferencePair:
    return PreferencePair(
        parent_id="parent-1",
        session_id="sess-1",
        passed_node=ExperienceNode(
            id=f"passed-{failed_id}",
            parent_id="parent-1",
            session_id="sess-1",
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            label=label,
        ),
        failed_node=ExperienceNode(
            id=failed_id,
            parent_id="parent-1",
            session_id="sess-1",
            status=ExperienceNodeStatus.FAILED,
            label=label,
        ),
    )


class TestGroupProvenance:
    def test_group_provenance_aggregates_multiple_rows_per_rule(self) -> None:
        # Arrange
        records = [
            _record(
                "rule-1",
                "pair-a",
                created_at="2026-01-01T00:00:00+00:00",
                last_matched_at="2026-01-05T00:00:00+00:00",
            ),
            _record(
                "rule-1",
                "pair-b",
                created_at="2026-01-02T00:00:00+00:00",
                last_matched_at="2026-01-06T00:00:00+00:00",
            ),
        ]

        # Act
        aggregates = group_provenance(records)

        # Assert
        assert len(aggregates) == 1
        assert aggregates[0].rule_id == "rule-1"
        assert set(aggregates[0].pair_ids) == {"pair-a", "pair-b"}
        assert aggregates[0].created == "2026-01-01T00:00:00+00:00"
        assert aggregates[0].last_matched == "2026-01-06T00:00:00+00:00"

    def test_group_provenance_separates_distinct_rules(self) -> None:
        # Arrange
        records = [_record("rule-1", "pair-a"), _record("rule-2", "pair-b")]

        # Act
        aggregates = group_provenance(records)

        # Assert
        assert {a.rule_id for a in aggregates} == {"rule-1", "rule-2"}

    def test_group_provenance_empty_input_returns_empty_list(self) -> None:
        # Arrange / Act
        aggregates = group_provenance([])

        # Assert
        assert aggregates == []


class TestPruningCandidates:
    def test_pruning_candidates_flags_rule_past_window(self) -> None:
        # Arrange
        now = datetime(2026, 4, 1, tzinfo=UTC)
        stale_at = (now - timedelta(days=100)).isoformat(timespec="seconds")
        aggregates = group_provenance(
            [_record("rule-1", "pair-a", last_matched_at=stale_at)]
        )

        # Act
        candidates = pruning_candidates(aggregates, window_days=90.0, now=now)

        # Assert
        assert len(candidates) == 1
        assert candidates[0].rule_id == "rule-1"
        assert candidates[0].days_since_match > 90.0

    def test_pruning_candidates_excludes_rule_with_recent_match(self) -> None:
        # Arrange
        now = datetime(2026, 4, 1, tzinfo=UTC)
        recent_at = (now - timedelta(days=5)).isoformat(timespec="seconds")
        aggregates = group_provenance(
            [_record("rule-1", "pair-a", last_matched_at=recent_at)]
        )

        # Act
        candidates = pruning_candidates(aggregates, window_days=90.0, now=now)

        # Assert
        assert candidates == []

    def test_pruning_candidates_boundary_exactly_at_window_is_not_stale(self) -> None:
        # Arrange: last_matched exactly window_days ago (not > window_days).
        now = datetime(2026, 4, 1, tzinfo=UTC)
        boundary_at = (now - timedelta(days=90)).isoformat(timespec="seconds")
        aggregates = group_provenance(
            [_record("rule-1", "pair-a", last_matched_at=boundary_at)]
        )

        # Act
        candidates = pruning_candidates(aggregates, window_days=90.0, now=now)

        # Assert
        assert candidates == []

    def test_pruning_candidates_sorted_most_stale_first(self) -> None:
        # Arrange
        now = datetime(2026, 4, 1, tzinfo=UTC)
        older = (now - timedelta(days=200)).isoformat(timespec="seconds")
        newer = (now - timedelta(days=100)).isoformat(timespec="seconds")
        aggregates = group_provenance(
            [
                _record("rule-newer", "pair-a", last_matched_at=newer),
                _record("rule-older", "pair-b", last_matched_at=older),
            ]
        )

        # Act
        candidates = pruning_candidates(aggregates, window_days=90.0, now=now)

        # Assert
        assert [c.rule_id for c in candidates] == ["rule-older", "rule-newer"]

    def test_pruning_candidates_empty_provenance_returns_empty_list(self) -> None:
        # Arrange / Act
        candidates = pruning_candidates([], window_days=90.0)

        # Assert
        assert candidates == []


class TestFailureClassesFromPairs:
    def test_failure_classes_from_pairs_collects_distinct_labels(self) -> None:
        # Arrange
        pairs = [_pair("f1", label="checks"), _pair("f2", label="lint")]

        # Act
        classes = failure_classes_from_pairs(pairs)

        # Assert
        assert classes == {"checks", "lint"}

    def test_failure_classes_from_pairs_skips_unlabeled_nodes(self) -> None:
        # Arrange
        pairs = [_pair("f1", label=None)]

        # Act
        classes = failure_classes_from_pairs(pairs)

        # Assert
        assert classes == set()

    def test_failure_classes_from_pairs_empty_input_returns_empty_set(self) -> None:
        # Arrange / Act
        classes = failure_classes_from_pairs([])

        # Assert
        assert classes == set()
