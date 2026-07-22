"""Integration tests for rule-provenance persistence via ExperienceStoreCore.

Covers plan synapse-rule-provenance.md Testing Strategy: record/refresh
round-trips, staleness windows, and negative cases (dangling ids, unknown
rule ids, empty provenance table).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.store_core import ExperienceStoreCore


def _seeded_core(tmp_path: Path, session_id: str = "sess-1") -> ExperienceStoreCore:
    core = ExperienceStoreCore(tmp_path / "experience.db")
    task = core.create_task(ExperienceTask(spec="test task"))
    _ = core.create_session(
        ExperienceSession(id=session_id, task_id=task.id, algorithm="commit")
    )
    return core


def _seed_pair(
    core: ExperienceStoreCore,
    session_id: str,
    failed_id: str,
    passed_id: str = "passed-shared",
    label: str = "checks",
) -> None:
    if core.get_node(passed_id) is None:
        _ = core.append_node(
            ExperienceNode(
                id=passed_id,
                parent_id="root",
                session_id=session_id,
                status=ExperienceNodeStatus.COMPLETED,
                fitness=1.0,
                label=label,
                artifact_ref="artifacts/passed.log",
            )
        )
    _ = core.append_node(
        ExperienceNode(
            id=failed_id,
            parent_id="root",
            session_id=session_id,
            status=ExperienceNodeStatus.FAILED,
            label=label,
            artifact_ref="artifacts/failed.log",
        )
    )


class TestRecordRuleProvenance:
    def test_record_rule_provenance_persists_evidence_citation(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")

        # Act
        provenance = core.record_rule_provenance("rule-1", pairs, "checks")

        # Assert
        assert provenance is not None
        assert provenance.rule_id == "rule-1"
        assert provenance.pair_ids == ["failed-1"]
        assert provenance.failure_class == "checks"

    def test_record_rule_provenance_empty_pairs_returns_none(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)

        # Act
        provenance = core.record_rule_provenance("rule-1", [], "checks")

        # Assert
        assert provenance is None

    def test_record_rule_provenance_idempotent_on_repeated_citation(
        self, tmp_path: Path
    ) -> None:
        # Arrange: same pair cited twice for the same rule.
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")

        # Act
        _ = core.record_rule_provenance("rule-1", pairs, "checks")
        second = core.record_rule_provenance("rule-1", pairs, "checks")

        # Assert: no duplicate rows — pair_ids has exactly one entry.
        assert second is not None
        assert second.pair_ids == ["failed-1"]


class TestRuleEvidence:
    def test_rule_evidence_returns_cited_pairs_with_artifact_refs(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")
        _ = core.record_rule_provenance("rule-1", pairs, "checks")

        # Act
        evidence = core.rule_evidence("rule-1")

        # Assert
        assert len(evidence) == 1
        assert evidence[0].failed_node_id == "failed-1"
        assert evidence[0].failed_artifact_ref == "artifacts/failed.log"
        assert evidence[0].passed_artifact_ref == "artifacts/passed.log"

    def test_rule_evidence_unknown_rule_id_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)

        # Act
        evidence = core.rule_evidence("unknown-rule")

        # Assert
        assert evidence == []

    def test_rule_evidence_empty_provenance_table_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        # Arrange: store exists, provenance table empty (auto-created, no rows).
        core = _seeded_core(tmp_path)

        # Act
        evidence = core.rule_evidence("rule-1")

        # Assert
        assert evidence == []

    def test_rule_evidence_dangling_node_ids_resolve_to_none_artifact_ref(
        self, tmp_path: Path
    ) -> None:
        # Arrange: record provenance, then simulate a pruned node by deleting
        # the underlying nodes row directly (BELIEF: nodes table has no
        # cascading delete, so dangling foreign keys are possible in
        # practice, e.g. via external maintenance).
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")
        _ = core.record_rule_provenance("rule-1", pairs, "checks")
        connection = sqlite3.connect(tmp_path / "experience.db")
        _ = connection.execute("DELETE FROM nodes WHERE id = ?", ("failed-1",))
        connection.commit()
        connection.close()

        # Act
        evidence = core.rule_evidence("rule-1")

        # Assert
        assert len(evidence) == 1
        assert evidence[0].failed_artifact_ref is None


class TestRefreshRuleMatches:
    def test_refresh_rule_matches_bumps_last_matched_for_matching_failure_class(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")
        _ = core.record_rule_provenance("rule-1", pairs, "checks")
        connection = sqlite3.connect(tmp_path / "experience.db")
        stale_at = (datetime.now(UTC) - timedelta(days=100)).isoformat(
            timespec="seconds"
        )
        _ = connection.execute(
            "UPDATE rule_provenance SET last_matched_at = ? WHERE rule_id = ?",
            (stale_at, "rule-1"),
        )
        connection.commit()
        connection.close()
        assert len(core.pruning_candidates(90.0)) == 1

        # Act: a new failed node with the same "checks" label recurs.
        _seed_pair(core, "sess-1", "failed-2")
        new_pairs = core.preference_pairs("sess-1")
        refreshed = core.refresh_rule_matches(new_pairs)

        # Assert
        assert refreshed == ["rule-1"]
        assert core.pruning_candidates(90.0) == []

    def test_refresh_rule_matches_no_matching_failure_class_refreshes_nothing(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1", label="checks")
        pairs = core.preference_pairs("sess-1")
        _ = core.record_rule_provenance("rule-1", pairs, "checks")

        # Act: new pairs carry an unrelated failure class.
        _seed_pair(core, "sess-1", "failed-lint", passed_id="passed-lint", label="lint")
        new_pairs = [
            p
            for p in core.preference_pairs("sess-1")
            if p.failed_node.id == "failed-lint"
        ]
        refreshed = core.refresh_rule_matches(new_pairs)

        # Assert
        assert refreshed == []

    def test_refresh_rule_matches_empty_pairs_refreshes_nothing(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)

        # Act
        refreshed = core.refresh_rule_matches([])

        # Assert
        assert refreshed == []


class TestPruningCandidatesStore:
    def test_pruning_candidates_empty_provenance_table_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)

        # Act
        candidates = core.pruning_candidates(90.0)

        # Assert
        assert candidates == []

    def test_pruning_candidates_distinguishes_stale_and_fresh_rules(
        self, tmp_path: Path
    ) -> None:
        # Arrange: rule-fresh cited recently, rule-stale cited long ago.
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-fresh", passed_id="passed-fresh")
        _seed_pair(core, "sess-1", "failed-stale", passed_id="passed-stale")
        pairs = core.preference_pairs("sess-1")
        fresh_pair = next(p for p in pairs if p.failed_node.id == "failed-fresh")
        stale_pair = next(p for p in pairs if p.failed_node.id == "failed-stale")
        _ = core.record_rule_provenance("rule-fresh", [fresh_pair], "checks")
        _ = core.record_rule_provenance("rule-stale", [stale_pair], "checks")
        connection = sqlite3.connect(tmp_path / "experience.db")
        stale_at = (datetime.now(UTC) - timedelta(days=200)).isoformat(
            timespec="seconds"
        )
        _ = connection.execute(
            "UPDATE rule_provenance SET last_matched_at = ? WHERE rule_id = ?",
            (stale_at, "rule-stale"),
        )
        connection.commit()
        connection.close()

        # Act
        candidates = core.pruning_candidates(90.0)

        # Assert
        assert [c.rule_id for c in candidates] == ["rule-stale"]


class TestListRuleProvenance:
    def test_list_rule_provenance_returns_all_rules_when_no_filter(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)
        _seed_pair(core, "sess-1", "failed-1")
        pairs = core.preference_pairs("sess-1")
        _ = core.record_rule_provenance("rule-1", pairs, "checks")

        # Act
        all_provenance = core.list_rule_provenance()

        # Assert
        assert [p.rule_id for p in all_provenance] == ["rule-1"]

    def test_list_rule_provenance_empty_table_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        core = _seeded_core(tmp_path)

        # Act
        all_provenance = core.list_rule_provenance()

        # Assert
        assert all_provenance == []
