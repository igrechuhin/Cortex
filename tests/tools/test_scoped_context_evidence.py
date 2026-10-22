"""Conflict, missingness, incoherence, and budget behavior of scoped evidence."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from cortex.core.session_goal_builder import build_session_goal
from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import write_session_goal
from cortex.tools.context.scoped_context import build_scoped_context_packet
from cortex.tools.context.scoped_readiness import ScopedReadiness
from cortex.tools.context.scoped_snapshot import ScopedSnapshot
from cortex.tools.context.scoped_source_state import ScopedSourceState
from cortex.tools.optimization import handlers
from tests.tools.scoped_revision_test_support import (
    ScopedResourceHarness,
    manifest,
    scoped_packet,
    task_state,
    write_plan,
    write_source,
)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScopedResourceHarness:
    return ScopedResourceHarness(tmp_path, monkeypatch)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metadata", "issue"),
    [
        ("depends_on: []", "missing_or_invalid_status"),
        ("status: custom\ndepends_on: []", "missing_or_invalid_status"),
        ("status: DONE\nstatus: PENDING\ndepends_on: []", "conflicting_status"),
        ("status: PENDING", "missing_dependencies"),
        ("status: PENDING\ndepends_on: not-a-list", "invalid_dependencies"),
        (
            "status: PENDING\ndepends_on: []\ndepends_on: [other]",
            "conflicting_dependencies",
        ),
    ],
)
async def test_metadata_uncertainty_is_not_implicit_readiness(
    harness: ScopedResourceHarness, metadata: str, issue: str
) -> None:
    # Arrange
    _ = write_source(
        harness.root,
        ".cortex/plans/selected.md",
        f"---\n{metadata}\n---\n## Goal\nSelected goal.\n",
    )
    # Act
    payload = await harness.read()
    # Assert
    assert payload["status"] == "success"
    assert task_state(payload).readiness is ScopedReadiness.UNKNOWN
    assert any(item.code == issue for item in task_state(payload).issues)
    assert scoped_packet(payload)["freshness"] == "warnings"


@pytest.mark.asyncio
async def test_dependency_cycles_are_explicit(harness: ScopedResourceHarness) -> None:
    # Arrange
    _ = write_plan(harness.root, dependencies=["dependency"])
    _ = write_plan(harness.root, "dependency", "DONE", ["selected"])
    # Act
    payload = await harness.read()
    # Assert
    assert any(item.code == "dependency_cycle" for item in task_state(payload).issues)
    assert task_state(payload).readiness is ScopedReadiness.UNKNOWN


@pytest.mark.asyncio
async def test_missing_current_plan_and_ambiguous_current_plan_are_evidenced(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    path = harness.root / ".cortex/plans/selected.md"
    path.unlink()
    missing = await harness.read()
    # Act
    path = write_plan(harness.root)
    created = await harness.read()
    _ = write_source(
        harness.root,
        ".cortex/plans/archive/Other/selected.md",
        path.read_text(encoding="utf-8"),
    )
    ambiguous = await harness.read()
    # Assert
    assert harness.calls == 3
    assert manifest(missing)["plan:selected"].state is ScopedSourceState.MISSING
    assert task_state(created).readiness is ScopedReadiness.READY
    assert manifest(ambiguous)["plan:selected"].state is ScopedSourceState.AMBIGUOUS
    assert "error" in scoped_packet(ambiguous)
    assert task_state(ambiguous).readiness is ScopedReadiness.UNKNOWN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw", ["not json", "[]", '{"goal": ""}', '{"goal": "text", "unknown": 1}']
)
async def test_invalid_goal_remains_explicit_without_breaking_context(
    harness: ScopedResourceHarness, raw: str
) -> None:
    # Arrange
    _ = write_source(harness.root, ".cortex/.session/session-goal.md", raw)
    # Act
    payload = await harness.read()
    # Assert
    assert payload["status"] == "success"
    assert "session_goal" not in payload
    assert manifest(payload)["session-goal"].state is ScopedSourceState.INVALID
    assert any(item.code == "invalid_goal" for item in task_state(payload).issues)
    assert task_state(payload).goal.value == "Implement selected feature."


@pytest.mark.asyncio
async def test_legacy_goal_anchor_loads_with_missing_derivation_evidence(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    goal = SessionGoal(
        goal="Operator goal", plan_slug="selected", blocked_files=["no/**"]
    )
    legacy = goal.model_dump_json(exclude={"source_plan_path", "source_plan_revision"})
    _ = write_source(harness.root, ".cortex/.session/session-goal.md", legacy)
    # Act
    payload = await harness.read()
    # Assert
    assert task_state(payload).goal.value == "Operator goal"
    assert task_state(payload).prohibitions == ["no/**"]
    assert any(
        item.code == "missing_goal_provenance" for item in task_state(payload).issues
    )
    assert (
        cast(dict[str, object], payload["session_goal"])["source_plan_revision"] is None
    )


@pytest.mark.asyncio
async def test_goal_plan_identity_conflict_does_not_override_authority(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = write_plan(harness.root, "other", goal="Other plan goal.")
    goal = build_session_goal(
        "Explicit operator goal", "other", harness.root, ["blocked/**"]
    )
    write_session_goal(harness.root, goal)
    # Act
    payload = await harness.read()
    # Assert
    codes = {item.code for item in task_state(payload).issues}
    assert {
        "goal_plan_conflict",
        "goal_plan_source_conflict",
        "goal_text_difference",
    } <= codes
    assert task_state(payload).goal.value == "Explicit operator goal"
    assert task_state(payload).plan_goal.value == "Implement selected feature."
    assert task_state(payload).prohibitions == ["blocked/**"]


@pytest.mark.asyncio
async def test_created_deleted_goal_and_rule_inputs_invalidate(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    missing = await harness.read()
    goal = build_session_goal("New anchor", "selected", harness.root)
    write_session_goal(harness.root, goal)
    created = await harness.read()
    # Act
    (harness.root / ".cortex/.session/session-goal.md").unlink()
    harness.rule.unlink()
    deleted = await harness.read()
    # Assert
    assert harness.calls == 3
    assert manifest(missing)["session-goal"].state is ScopedSourceState.MISSING
    assert task_state(created).goal.value == "New anchor"
    assert task_state(deleted).goal.value == "Implement selected feature."
    assert "rule:local:general:selected.mdc" not in manifest(deleted)


@pytest.mark.asyncio
async def test_missing_rules_provenance_is_visible(
    harness: ScopedResourceHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    async def plain_rules() -> str:
        return "## Universal\nSelected plain rules.\n"

    monkeypatch.setattr(handlers, "get_relevant_rules", plain_rules)
    # Act
    payload = await harness.read()
    # Assert
    assert any(
        item.code == "missing_rule_provenance" for item in task_state(payload).issues
    )
    assert "Selected plain rules." in str(scoped_packet(payload)["filtered_rules"])


@pytest.mark.asyncio
async def test_selected_mutation_during_assembly_refuses_mixed_snapshot_and_does_not_cache(
    harness: ScopedResourceHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    async def mutate_during_base(task_description: str, token_budget: int) -> str:
        result = await harness.load_base(task_description, token_budget)
        _ = write_plan(harness.root, goal="Changed during assembly.")
        return result

    monkeypatch.setattr(handlers, "load_context_impl", mutate_during_base)
    # Act
    refused = await harness.read()
    monkeypatch.setattr(handlers, "load_context_impl", harness.load_base)
    fresh = await harness.read()
    # Assert
    assert refused["error"] == "incoherent_scoped_snapshot"
    assert harness.calls == 2
    assert task_state(fresh).plan_goal.value == "Changed during assembly."


@pytest.mark.asyncio
async def test_selected_mutation_during_capture_refuses_before_optimizer(
    harness: ScopedResourceHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    async def mutate_while_loading_rules() -> str:
        _ = write_plan(harness.root, goal="Changed while selecting evidence.")
        return await harness.read_rules()

    monkeypatch.setattr(handlers, "get_relevant_rules", mutate_while_loading_rules)
    # Act
    refused = await harness.read()
    # Assert
    assert refused["error"] == "incoherent_scoped_snapshot"
    assert harness.calls == 0


@pytest.mark.asyncio
async def test_selected_membership_mutation_during_assembly_is_rejected(
    harness: ScopedResourceHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    async def duplicate_during_base(task_description: str, token_budget: int) -> str:
        result = await harness.load_base(task_description, token_budget)
        _ = write_source(
            harness.root,
            ".cortex/plans/archive/Other/selected.md",
            (harness.root / ".cortex/plans/selected.md").read_text(encoding="utf-8"),
        )
        return result

    monkeypatch.setattr(handlers, "load_context_impl", duplicate_during_base)
    # Act
    refused = await harness.read()
    # Assert
    assert refused["error"] == "incoherent_scoped_snapshot"


@pytest.mark.asyncio
async def test_required_manifest_survives_optional_budget_omission(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    first = await harness.read()
    harness.config["token_budget"] = cast(int, first["total_tokens"]) + 1000
    _ = write_source(
        harness.root, ".cortex/memory-bank/log.md", "optional history " * 8000
    )
    # Act
    payload = await harness.read()
    # Assert
    assert payload["status"] == "success"
    assert "recent_operations" in cast(list[str], payload["omitted_components"])
    assert manifest(payload)["plan:selected"].revision is not None
    assert task_state(payload).plan_prohibitions.value == "- No deployment."
    assert cast(int, payload["total_tokens"]) <= harness.config["token_budget"]


@pytest.mark.asyncio
async def test_insufficient_budget_does_not_truncate_scoped_governance(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    harness.config["token_budget"] = 20
    # Act
    payload = await harness.read()
    # Assert
    assert payload["error"] == "insufficient_token_budget"
    assert "scoped_context" in cast(list[str], payload["required_components"])


def test_direct_packet_preserves_snapshot_bytes_and_warns_on_mutation(
    tmp_path: Path,
) -> None:
    # Arrange
    path = write_plan(tmp_path)
    from cortex.tools.context.scoped_plan_evidence import capture_plan_evidence

    snapshot = ScopedSnapshot(root=tmp_path, scope="plan:selected")
    capture_plan_evidence(snapshot)
    _ = write_plan(tmp_path, goal="New bytes.")
    # Act
    packet = build_scoped_context_packet(
        project_root=tmp_path,
        scope="plan:selected",
        rules_payload="",
        snapshot=snapshot,
    )
    # Assert
    assert packet is not None
    assert packet["freshness"] == "incoherent"
    assert (
        "Implement selected feature."
        in cast(dict[str, str], packet["current_plan"])["content"]
    )
    assert "New bytes." in path.read_text(encoding="utf-8")


def test_snapshot_reports_unreadable_and_invalid_utf8_sources(tmp_path: Path) -> None:
    # Arrange
    snapshot = ScopedSnapshot(root=tmp_path, scope="plan:selected")
    invalid = tmp_path / "invalid.md"
    _ = invalid.write_bytes(b"\xff")
    directory = tmp_path / "directory"
    directory.mkdir()
    # Act
    with pytest.raises(UnicodeError):
        _ = snapshot.read(invalid)
    with pytest.raises(OSError):
        _ = snapshot.read(directory)
    # Assert
    assert snapshot.sources["file:invalid.md"].state is ScopedSourceState.INVALID
    assert snapshot.sources["file:directory"].state is ScopedSourceState.UNREADABLE
    assert snapshot.files_unchanged()
