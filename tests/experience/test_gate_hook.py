"""Tests for quality-gate -> experience fitness attachment hook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.core.models import ModelDict
from cortex.experience.gate_hook import gate_summary, record_gate_result
from cortex.experience.recorder import experience_db_path, experience_session_id
from cortex.experience.store_core import ExperienceStoreCore


def test_gate_summary_keeps_only_score_keys() -> None:
    # Arrange
    result: ModelDict = {
        "preflight_passed": True,
        "summary": "all good",
        "total_errors": 0,
        "checks_performed": ["tests"],
    }

    # Act
    summary = json.loads(gate_summary(result))

    # Assert
    assert summary == {
        "preflight_passed": True,
        "summary": "all good",
        "total_errors": 0,
    }


@pytest.mark.asyncio
async def test_record_gate_result_attaches_fitness_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("CORTEX_SESSION_ID", "gatesess")

    # Act
    node_id = await record_gate_result(
        tmp_path, {"preflight_passed": False, "summary": "2 type errors"}
    )

    # Assert
    assert node_id is not None
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    nodes = core.list_nodes(experience_session_id("gatesess", "commit"))
    assert len(nodes) == 1
    assert nodes[0].fitness == 0.0
    assert nodes[0].artifact_ref is not None


@pytest.mark.asyncio
async def test_record_gate_result_disabled_via_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("CORTEX_SESSION_ID", "gatesess")
    monkeypatch.setenv("CORTEX_EXPERIENCE_RECORDING", "0")

    # Act
    node_id = await record_gate_result(tmp_path, {"preflight_passed": True})

    # Assert
    assert node_id is None
    assert not experience_db_path(tmp_path).exists()
