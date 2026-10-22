"""Run ownership, fail-closed locking and execution-frontier isolation."""

from __future__ import annotations

import asyncio
import json
import os
import platform
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.experience.recorder import experience_db_path, experience_session_id
from cortex.experience.resume import build_resume_plan
from cortex.experience.store_core import ExperienceStoreCore
from cortex.tools.session.pipeline_handoff_lock import PipelineClaimLockTimeout
from tests.tools.phase_result_test_support import (
    call,
    evidence_snapshot,
    publication_dir,
    read_object,
)

pytestmark = pytest.mark.asyncio
pytest_plugins = ("tests.tools.phase_result_test_support",)
DATA = {"status": "passed", "value": "computed"}


async def test_verification_and_replay_never_mint_or_adopt_an_unbound_run(
    publication_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = await call("write", DATA)
    monkeypatch.delenv("CORTEX_PIPELINE_SESSION_ID")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


async def test_different_current_run_cannot_verify_or_overwrite_sibling_evidence(
    publication_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = await call("write", DATA)
    original = evidence_snapshot(publication_root)
    original_publication = evidence_snapshot(publication_dir(publication_root))
    monkeypatch.setenv("CORTEX_PIPELINE_SESSION_ID", "other-run")

    assert (await call("verify_result", DATA))["status"] == "missing"
    assert evidence_snapshot(publication_root) == original
    assert (await call("replay_result", DATA))["status"] == "ok"
    assert evidence_snapshot(publication_dir(publication_root)) == original_publication


@pytest.mark.parametrize(
    "operation", ["write", "verify_result", "replay_result", "mark_running", "clear"]
)
async def test_lock_refusal_never_allows_unlocked_publication(
    publication_root: Path,
    operation: str,
) -> None:
    _ = await call("write", DATA)
    before = evidence_snapshot(publication_dir(publication_root))
    module = (
        "pipeline_handoff_publication"
        if operation == "verify_result"
        else "pipeline_handoff_io"
    )
    with patch(
        f"cortex.tools.session.{module}.pipeline_claim_lock",
        side_effect=PipelineClaimLockTimeout("injected contention"),
    ):
        result = await call(operation, DATA)

    assert result["status"] in {"uncertain", "error"}
    assert evidence_snapshot(publication_dir(publication_root)) == before


async def test_concurrent_missing_replays_publish_exactly_one_result_record(
    publication_root: Path,
) -> None:
    _ = await call("init")
    results = await asyncio.gather(*(call("replay_result", DATA) for _ in range(5)))

    assert sorted(str(result["status"]) for result in results) == ["exact"] * 4 + ["ok"]
    assert (
        len(
            (publication_dir(publication_root) / "pipeline.log")
            .read_text()
            .splitlines()
        )
        == 1
    )
    assert (await call("verify_result", DATA))["status"] == "exact"


async def test_new_running_marker_is_not_overwritten_by_replay(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    _ = await call("mark_running")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize("status", ["passed", "failed"])
async def test_replay_preserves_experience_and_failed_frontier_rules(
    publication_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    monkeypatch.setenv("CORTEX_EXPERIENCE_RECORDING", "1")
    data = {"status": status}
    _ = await call("mark_running")
    _ = await call("write", data)
    core = ExperienceStoreCore(experience_db_path(publication_root))
    session = experience_session_id("publication-test", "implement")
    nodes = core.list_nodes(session)
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", data))["status"] == "exact"
    assert (await call("replay_result", data))["status"] == "exact"
    assert core.list_nodes(session) == nodes
    assert evidence_snapshot(publication_root) == before
    plan = build_resume_plan(publication_root, "publication-test", "implement")
    assert plan.resumable is (status == "passed")
    assert plan.completed_phases == (["code"] if status == "passed" else [])
    assert plan.frontier_phase == "code"
    if status == "failed":
        assert "fix path" in plan.reason


@pytest.mark.parametrize("operation", ["write", "verify_result", "replay_result"])
@pytest.mark.parametrize("data", [{"_publication": {}}, '{"value": NaN}'])
async def test_invalid_identity_input_is_refused_without_mutating_evidence(
    publication_root: Path,
    operation: str,
    data: object,
) -> None:
    _ = await call("init")
    before = evidence_snapshot(publication_root)

    assert (await call(operation, data))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


def _set_foreign_registry_owner(root: Path, *, include_current: bool) -> None:
    registry_path = root / ".cortex/.session/.pipeline-runs.json"
    registry = read_object(registry_path)
    record = cast(dict[str, object], registry["publication-test"])
    existing = cast(list[object], record["owners"])
    foreign = {"pid": os.getppid(), "host": platform.node()}
    record["owners"] = [*existing, foreign] if include_current else [foreign]
    _ = registry_path.write_text(json.dumps(registry), encoding="utf-8")


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize("phase", ["code", "review"])
async def test_inherited_live_foreign_only_run_is_never_read_or_written(
    publication_root: Path,
    operation: str,
    phase: str,
) -> None:
    _ = await call("write", DATA)
    _set_foreign_registry_owner(publication_root, include_current=False)
    before = evidence_snapshot(publication_root)

    result = await call(operation, DATA, phase=phase)

    assert result["status"] == "uncertain"
    assert result.get("receipt") is None
    assert evidence_snapshot(publication_root) == before


async def test_registered_participant_may_verify_shared_inherited_run(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    _set_foreign_registry_owner(publication_root, include_current=True)
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "exact"
    assert (await call("replay_result", DATA))["status"] == "exact"
    assert evidence_snapshot(publication_root) == before


async def test_established_unregistered_current_run_remains_compatible(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    (publication_root / ".cortex/.session/.pipeline-runs.json").unlink()
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "exact"
    assert (await call("replay_result", DATA))["status"] == "exact"
    assert evidence_snapshot(publication_root) == before
