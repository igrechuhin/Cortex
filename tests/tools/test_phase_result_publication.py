"""Exact identity, lost responses and publication-only replay through the real API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.session.phase_result_receipt import PhaseResultReceipt
from tests.tools.phase_result_test_support import (
    call,
    evidence_snapshot,
    publication_dir,
    read_object,
)

pytestmark = pytest.mark.asyncio
pytest_plugins = ("tests.tools.phase_result_test_support",)


async def test_lost_response_verification_and_replay_preserve_all_evidence(
    publication_root: Path,
) -> None:
    data = {
        "status": "passed",
        "nested": {"b": [False, None, 3], "a": "é"},
        "force_fresh": True,
        "test_timeout": 600,
    }
    written = await call("write", data)
    receipt = PhaseResultReceipt.model_validate(written["receipt"])
    before = evidence_snapshot(publication_root)

    verified = await call("verify_result", json.dumps(data, sort_keys=True))
    replayed = await call("replay_result", data)

    assert verified["status"] == replayed["status"] == "exact"
    assert PhaseResultReceipt.model_validate(verified["receipt"]) == receipt
    assert receipt.run_id == "publication-test"
    assert receipt.pipeline == "implement" and receipt.phase == "code"
    assert evidence_snapshot(publication_root) == before
    result = read_object(publication_dir(publication_root) / "code-result.json")
    assert "force_fresh" not in result and "test_timeout" not in result
    assert result["_publication"] == written["receipt"]


@pytest.mark.parametrize(
    "different",
    [
        {"status": "passed", "value": 2},
        {"status": "passed", "value": True},
        {"status": "passed", "value": 1.0},
        {"status": "passed", "value": [1]},
    ],
)
async def test_same_keys_different_payload_cannot_replay_over_newer_result(
    publication_root: Path,
    different: dict[str, object],
) -> None:
    original = {"status": "passed", "value": 1}
    _ = await call("write", original)
    _ = await call("write_result", different)
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", original))["status"] == "conflicting"
    assert (await call("replay_result", original))["status"] == "conflicting"
    assert (await call("verify_result", different))["status"] == "exact"
    assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize(
    "config",
    [
        {"force_fresh": False, "test_timeout": 600},
        {"force_fresh": True, "test_timeout": 300},
        {"force_fresh": 1, "test_timeout": 600},
        {"force_fresh": True},
    ],
)
async def test_config_is_part_of_exact_request_identity(
    publication_root: Path,
    config: dict[str, object],
) -> None:
    original = {"status": "passed", "force_fresh": True, "test_timeout": 600}
    _ = await call("write", original)
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", {"status": "passed", **config}))[
        "status"
    ] == "conflicting"
    assert (await call("replay_result", {"status": "passed", **config}))[
        "status"
    ] == "conflicting"
    assert evidence_snapshot(publication_root) == before


async def test_other_phase_config_change_invalidates_exact_without_rewriting(
    publication_root: Path,
) -> None:
    data = {"status": "passed", "force_fresh": True, "test_timeout": 600}
    _ = await call("write", data)
    _ = await call("write", {"status": "passed", "test_timeout": 300}, phase="review")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", data))["status"] == "conflicting"
    assert (await call("replay_result", data))["status"] == "conflicting"
    assert evidence_snapshot(publication_root) == before


async def test_missing_replay_publishes_once_without_executing_work(
    publication_root: Path,
) -> None:
    _ = await call("init")
    data = {"status": "passed", "value": "already computed"}
    before = evidence_snapshot(publication_root)
    assert (await call("verify_result", data))["status"] == "missing"
    assert evidence_snapshot(publication_root) == before

    assert (await call("replay_result", data))["status"] == "ok"
    after = evidence_snapshot(publication_root)
    assert (await call("replay_result", data))["status"] == "exact"
    assert evidence_snapshot(publication_root) == after
    history = (
        (publication_dir(publication_root) / "pipeline.log").read_text().splitlines()
    )
    assert len(history) == 1


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        [1, "x"],
        "not json",
        42,
        False,
        {"completed_at": "caller timestamp", "phase_status": "failed"},
    ],
)
async def test_canonicalization_preserves_supported_normal_payloads(
    publication_root: Path,
    data: object,
) -> None:
    assert (await call("write", data))["status"] == "ok"
    assert (await call("verify_result", data))["status"] == "exact"
    before = evidence_snapshot(publication_root)
    assert (await call("replay_result", data))["status"] == "exact"
    assert evidence_snapshot(publication_root) == before


async def test_embedded_routing_and_legacy_write_share_request_identity(
    publication_root: Path,
) -> None:
    _ = await call(
        "write_result",
        {
            "operation": "write",
            "pipeline": "implement",
            "phase": "code",
            "value": "same",
        },
    )
    assert (await call("verify_result", {"value": "same"}))["status"] == "exact"
    assert (await call("read"))["status"] == "not_found"
    assert "phases" in await call("read_state")


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
async def test_phase_required_for_publication_operations(
    publication_root: Path,
    operation: str,
) -> None:
    from cortex.tools.session.pipeline_handoff import pipeline_handoff

    result = json.loads(
        await pipeline_handoff(operation=operation, pipeline="implement")
    )
    assert result["status"] == "error"
    assert "phase is required" in result["error"]


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize("newer", [False, True])
@pytest.mark.parametrize("embedded_operation", ["write", "clear", "mark_running"])
async def test_original_envelope_cannot_override_publication_operation(
    publication_root: Path,
    operation: str,
    newer: bool,
    embedded_operation: str,
) -> None:
    envelope = {
        "operation": "write",
        "pipeline": "implement",
        "phase": "code",
        "value": "same",
    }
    _ = await call("write_result", envelope)
    if newer:
        _ = await call("write", {"value": "newer"})
    before = evidence_snapshot(publication_root)
    envelope["operation"] = embedded_operation

    result = await call(operation, envelope)

    assert result["status"] == ("conflicting" if newer else "exact")
    assert evidence_snapshot(publication_root) == before
    history = (publication_dir(publication_root) / "pipeline.log").read_text()
    assert len(history.splitlines()) == (2 if newer else 1)


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize(("key", "value"), [("pipeline", "fix"), ("phase", "review")])
async def test_original_envelope_cannot_redirect_explicit_publication_target(
    publication_root: Path,
    operation: str,
    key: str,
    value: str,
) -> None:
    envelope = {
        "operation": "write",
        "pipeline": "implement",
        "phase": "code",
        "value": "same",
    }
    _ = await call("write_result", envelope)
    envelope[key] = value
    before = evidence_snapshot(publication_root)

    assert (await call(operation, envelope))["status"] == "conflicting"
    assert evidence_snapshot(publication_root) == before
    assert (await call("verify_result", {"value": "same"}))["status"] == "exact"
