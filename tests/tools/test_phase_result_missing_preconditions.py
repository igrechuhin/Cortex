"""Missing-target replay must honor existing manifest publication preconditions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.tools.phase_result_test_support import (
    call,
    evidence_snapshot,
    publication_dir,
    read_object,
)

pytestmark = pytest.mark.asyncio
pytest_plugins = ("tests.tools.phase_result_test_support",)


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize(
    ("key", "current", "incoming"),
    [("test_timeout", 300, 600), ("force_fresh", False, True)],
)
async def test_missing_target_refuses_conflicting_config_without_mutation(
    publication_root: Path,
    operation: str,
    key: str,
    current: object,
    incoming: object,
) -> None:
    assert (await call("write", {"status": "passed", key: current}, phase="review"))[
        "status"
    ] == "ok"
    assert not (publication_dir(publication_root) / "code-result.json").exists()
    before = evidence_snapshot(publication_root)

    result = await call(operation, {"status": "passed", key: incoming})

    assert (result["status"], evidence_snapshot(publication_root)) == (
        "conflicting",
        before,
    )


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize(
    ("key", "value"), [("session_id", "foreign-run"), ("pipeline", "commit")]
)
async def test_missing_target_refuses_wrong_manifest_identity_without_mutation(
    publication_root: Path,
    operation: str,
    key: str,
    value: str,
) -> None:
    assert (await call("write", {"status": "passed"}, phase="review"))["status"] == "ok"
    manifest = publication_dir(publication_root) / "pipeline.json"
    state = read_object(manifest)
    state[key] = value
    _ = manifest.write_text(json.dumps(state), encoding="utf-8")
    assert not (publication_dir(publication_root) / "code-result.json").exists()
    before = evidence_snapshot(publication_root)

    result = await call(operation, {"status": "passed"})

    assert (result["status"], evidence_snapshot(publication_root)) == (
        "conflicting",
        before,
    )


@pytest.mark.parametrize(
    ("setup", "current", "incoming"),
    [
        ("absent", {}, {"test_timeout": 600, "force_fresh": True}),
        ("initialized", {}, {"test_timeout": 600}),
        ("review", {"test_timeout": 600}, {"test_timeout": 600}),
        ("review", {"test_timeout": 600}, {"test_timeout": 600, "force_fresh": True}),
        ("review", {"test_timeout": 600}, {}),
        (
            "review",
            {"test_timeout": {"a": [1, False], "b": None}},
            {"test_timeout": {"b": None, "a": [1, False]}},
        ),
    ],
)
async def test_valid_missing_publication_replays_once_and_preserves_exact_evidence(
    publication_root: Path,
    setup: str,
    current: dict[str, object],
    incoming: dict[str, object],
) -> None:
    if setup == "initialized":
        assert (await call("init"))["status"] == "ok"
    elif setup == "review":
        assert (await call("write", current, phase="review"))["status"] == "ok"
    data = {"status": "passed", "value": "already computed", **incoming}
    before = evidence_snapshot(publication_root)

    assert (await call("verify_result", data))["status"] == "missing"
    assert evidence_snapshot(publication_root) == before
    assert (await call("replay_result", data))["status"] == "ok"
    published = evidence_snapshot(publication_root)
    assert (await call("verify_result", data))["status"] == "exact"
    assert (await call("replay_result", data))["status"] == "exact"
    assert evidence_snapshot(publication_root) == published
    directory = publication_dir(publication_root)
    assert len((directory / "pipeline.log").read_text().splitlines()) == (
        2 if setup == "review" else 1
    )
    assert read_object(directory / "pipeline.json")["config"] == {**current, **incoming}


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize(
    ("key", "current", "incoming"),
    [
        ("force_fresh", True, 1),
        ("force_fresh", False, 0),
        ("test_timeout", 600, 600.0),
        ("test_timeout", {"a": [1, False]}, {"a": [1, 0]}),
        ("test_timeout", [1, 2], [2, 1]),
    ],
)
async def test_missing_config_comparison_is_canonical_and_type_sensitive(
    publication_root: Path,
    operation: str,
    key: str,
    current: object,
    incoming: object,
) -> None:
    assert (await call("write", {key: current}, phase="review"))["status"] == "ok"
    before = evidence_snapshot(publication_root)

    result = await call(operation, {key: incoming})

    assert result["status"] == "conflicting"
    assert evidence_snapshot(publication_root) == before


@pytest.mark.parametrize("operation", ["verify_result", "replay_result"])
@pytest.mark.parametrize("malformed", [None, [], True, "invalid", 7])
async def test_missing_target_refuses_malformed_config_without_mutation(
    publication_root: Path,
    operation: str,
    malformed: object,
) -> None:
    assert (await call("write", {}, phase="review"))["status"] == "ok"
    manifest = publication_dir(publication_root) / "pipeline.json"
    state = read_object(manifest)
    state["config"] = malformed
    _ = manifest.write_text(json.dumps(state), encoding="utf-8")
    before = evidence_snapshot(publication_root)

    result = await call(operation, {})

    assert result["status"] == "uncertain"
    assert evidence_snapshot(publication_root) == before
