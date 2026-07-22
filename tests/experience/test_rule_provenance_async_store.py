"""Async facade tests for ExperienceStore rule-provenance delegation."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.store import ExperienceStore


async def _seed_pair_via_async_store(
    tmp_path: Path,
) -> tuple[ExperienceStore, str, str, str]:
    """Seed one session with a passed/failed sibling pair; return (store, session_id, failed_id, passed_id)."""
    store = ExperienceStore.from_db_path(tmp_path / "experience.db")
    task = await store.create_task(ExperienceTask(spec="pipeline:commit"))
    session = await store.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit")
    )
    parent = await store.append_node(ExperienceNode(session_id=session.id))
    passed = await store.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            step_number=2,
            label="checks",
        )
    )
    failed = await store.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.FAILED,
            step_number=2,
            label="checks",
        )
    )
    return store, session.id, failed.id, passed.id


@pytest.mark.asyncio
async def test_async_store_record_rule_provenance_delegates_to_core(
    tmp_path: Path,
) -> None:
    # Arrange
    store, session_id, _, _ = await _seed_pair_via_async_store(tmp_path)
    pairs = await store.preference_pairs(session_id)

    # Act
    provenance = await store.record_rule_provenance("rule-1", pairs, "checks")

    # Assert
    assert provenance is not None
    assert provenance.rule_id == "rule-1"


@pytest.mark.asyncio
async def test_async_store_rule_evidence_delegates_to_core(tmp_path: Path) -> None:
    # Arrange
    store, session_id, failed_id, passed_id = await _seed_pair_via_async_store(tmp_path)
    pairs = await store.preference_pairs(session_id)
    _ = await store.record_rule_provenance("rule-1", pairs, "checks")

    # Act
    evidence = await store.rule_evidence("rule-1")

    # Assert
    assert len(evidence) == 1
    assert evidence[0].failed_node_id == failed_id
    assert evidence[0].passed_node_id == passed_id


@pytest.mark.asyncio
async def test_async_store_refresh_and_list_and_prune_delegate_to_core(
    tmp_path: Path,
) -> None:
    # Arrange
    store, session_id, _, _ = await _seed_pair_via_async_store(tmp_path)
    pairs = await store.preference_pairs(session_id)
    _ = await store.record_rule_provenance("rule-1", pairs, "checks")

    # Act
    refreshed = await store.refresh_rule_matches(pairs)
    all_provenance = await store.list_rule_provenance()
    candidates = await store.pruning_candidates(90.0)

    # Assert
    assert refreshed == ["rule-1"]
    assert len(all_provenance) == 1
    assert candidates == []
