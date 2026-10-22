"""Every existing publication boundary fails closed without repairing evidence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.tools.phase_result_test_support import (
    call,
    evidence_snapshot,
    publication_dir,
    read_object,
)

pytestmark = pytest.mark.asyncio
pytest_plugins = ("tests.tools.phase_result_test_support",)
DATA = {"status": "passed", "value": 1, "force_fresh": True, "test_timeout": 600}


@pytest.mark.parametrize(
    ("boundary", "expected"),
    [
        ("_append_event_log", "missing"),
        ("_write_result_payload_file", "uncertain"),
        ("_update_pipeline_state_file", "uncertain"),
        ("_record_phase_event_best_effort", "exact"),
    ],
)
async def test_publication_interruption_at_each_existing_boundary(
    publication_root: Path,
    boundary: str,
    expected: str,
) -> None:
    with patch(
        f"cortex.tools.session.pipeline_handoff_io.{boundary}",
        side_effect=OSError("injected publication interruption"),
    ):
        written = await call("write", DATA)
    assert written["status"] in {"error", "uncertain"}
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == expected
    assert evidence_snapshot(publication_root) == before
    replayed = await call("replay_result", DATA)
    if expected == "missing":
        assert replayed["status"] == "ok"
        assert (await call("verify_result", DATA))["status"] == "exact"
    else:
        assert replayed["status"] == expected
        assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize(
    "filename", ["code-result.json", "pipeline.json", "pipeline.log"]
)
async def test_missing_one_persisted_component_is_uncertain(
    publication_root: Path,
    filename: str,
) -> None:
    _ = await call("write", DATA)
    (publication_dir(publication_root) / filename).unlink()
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("code-result.json", "{"),
        ("code-result.json", "[]"),
        ("code-result.json", "{}"),
        ("pipeline.json", "{"),
        ("pipeline.json", '{"phases": []}'),
        ("pipeline.log", "{"),
        ("pipeline.log", '{"phase":"code"}\n'),
    ],
)
async def test_malformed_evidence_never_qualifies_exact_or_replayable(
    publication_root: Path,
    filename: str,
    content: str,
) -> None:
    _ = await call("write", DATA)
    _ = (publication_dir(publication_root) / filename).write_text(
        content, encoding="utf-8"
    )
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize(
    ("filename", "old", "new", "expected"),
    [
        ("code-result.json", '"value": 1', '"value": 2', "conflicting"),
        ("pipeline.json", '"value": 1', '"value": 2', "uncertain"),
        (
            "pipeline.json",
            '"session_id": "publication-test"',
            '"session_id": "other"',
            "conflicting",
        ),
        (
            "pipeline.json",
            '"pipeline": "implement"',
            '"pipeline": "fix"',
            "conflicting",
        ),
        ("pipeline.json", '"force_fresh": true', '"force_fresh": false', "conflicting"),
        ("pipeline.json", '"config": {', '"discarded_config": {', "conflicting"),
        (
            "pipeline.log",
            '"operation":"write"',
            '"operation":"mark_running"',
            "uncertain",
        ),
        ("pipeline.log", '"status":"completed"', '"status":"failed"', "uncertain"),
        ("pipeline.log", '"data_keys":[', '"discarded_keys":[', "uncertain"),
    ],
)
async def test_conflicting_component_is_refused_without_changes(
    publication_root: Path,
    filename: str,
    old: str,
    new: str,
    expected: str,
) -> None:
    _ = await call("write", DATA)
    path = publication_dir(publication_root) / filename
    text = path.read_text(encoding="utf-8")
    assert old in text
    _ = path.write_text(text.replace(old, new, 1), encoding="utf-8")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == expected
    assert (await call("replay_result", DATA))["status"] == expected
    assert evidence_snapshot(publication_root) == before


async def test_legacy_payload_and_history_are_not_exact_proof(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    directory = publication_dir(publication_root)
    result = read_object(directory / "code-result.json")
    del result["_publication"]
    _ = (directory / "code-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


async def test_torn_history_suffix_is_not_silently_skipped(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    path = publication_dir(publication_root) / "pipeline.log"
    with path.open("a", encoding="utf-8") as stream:
        _ = stream.write('{"phase":')
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


async def test_scoped_clear_retains_history_and_refuses_republication(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    _ = await call("clear")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


async def test_malformed_separated_configuration_is_uncertain(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    path = publication_dir(publication_root) / "pipeline.json"
    state = read_object(path)
    state["config"] = []
    _ = path.write_text(json.dumps(state), encoding="utf-8")
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", DATA))["status"] == "uncertain"
    assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before


async def test_unreadable_evidence_is_uncertain(
    publication_root: Path,
) -> None:
    _ = await call("write", DATA)
    before = evidence_snapshot(publication_root)
    with patch.object(Path, "read_text", side_effect=OSError("injected read failure")):
        assert (await call("verify_result", DATA))["status"] == "uncertain"
        assert (await call("replay_result", DATA))["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before
