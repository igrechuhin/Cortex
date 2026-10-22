"""Deterministic real-file/cache cases for selected scoped input revisions."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from cortex.core.session_goal_builder import build_session_goal
from cortex.core.session_goal_store import write_session_goal
from cortex.tools.context.scoped_evidence_state import ScopedEvidenceState
from cortex.tools.context.scoped_readiness import ScopedReadiness
from cortex.tools.context.scoped_source_state import ScopedSourceState
from cortex.tools.optimization import handlers
from cortex.wiki.layout import ensure_default_wiki_layout
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
async def test_unchanged_and_unrelated_sources_reuse_exact_cached_bytes(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    first = await harness.read()
    # Act
    _ = write_plan(harness.root, "unrelated", "DONE")
    _ = write_source(harness.root, "src/unrelated.py", "changed = True\n")
    _ = write_source(harness.root, ".cortex/rules/unselected.mdc", "Unselected rule")
    second = await harness.read()
    third = await harness.read()
    # Assert
    assert first == second == third
    assert harness.calls == 1
    assert all(
        "unrelated" not in source.reference for source in manifest(second).values()
    )


@pytest.mark.asyncio
async def test_selected_plan_read_mutate_read_refreshes_same_key(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    first = await harness.read()
    # Act
    path = write_plan(harness.root, goal="Changed selected goal.")
    second = await harness.read()
    # Assert
    assert harness.calls == 2
    assert task_state(second).plan_goal.value == "Changed selected goal."
    assert (
        manifest(second)["plan:selected"].revision
        == sha256(path.read_bytes()).hexdigest()
    )
    assert (
        manifest(first)["plan:selected"].revision
        != manifest(second)["plan:selected"].revision
    )


@pytest.mark.asyncio
async def test_mentioned_source_paths_are_not_revision_dependencies(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = write_plan(
        harness.root, goal="Edit src/mentioned.py without importing its contents."
    )
    path = write_source(harness.root, "src/mentioned.py", "first = 1\n")
    first = await harness.read()
    # Act
    _ = path.write_text("first = 2\n", encoding="utf-8")
    second = await harness.read()
    # Assert
    assert harness.calls == 1
    assert first == second
    assert all(
        source.reference != "src/mentioned.py" for source in manifest(second).values()
    )


@pytest.mark.asyncio
async def test_declared_dependency_status_and_content_refresh_readiness(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = write_plan(harness.root, dependencies=["dependency"])
    _ = write_plan(harness.root, "dependency", "PENDING", ["ancestor"])
    _ = write_plan(harness.root, "ancestor", "DONE")
    first = await harness.read()
    # Act
    dependency = write_plan(
        harness.root, "dependency", "DONE", ["ancestor"], "Updated dependency."
    )
    second = await harness.read()
    # Assert
    assert harness.calls == 2
    assert task_state(first).readiness is ScopedReadiness.BLOCKED
    assert task_state(first).dependencies[0].satisfied is False
    assert task_state(second).readiness is ScopedReadiness.READY
    assert task_state(second).dependencies[0].satisfied is True
    assert (
        manifest(second)["plan:dependency"].revision
        == sha256(dependency.read_bytes()).hexdigest()
    )
    assert [
        entry["slug"]
        for entry in cast(list[dict[str, str]], scoped_packet(first)["upstream_plans"])
    ] == ["ancestor"]


@pytest.mark.asyncio
async def test_missing_created_deleted_dependency_invalidates_same_request(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = write_plan(harness.root, dependencies=["new-dependency.md"])
    missing = await harness.read()
    # Act
    path = write_plan(harness.root, "new-dependency", "DONE")
    created = await harness.read()
    path.unlink()
    deleted = await harness.read()
    # Assert
    assert harness.calls == 3
    assert manifest(missing)["plan:new-dependency"].state is ScopedSourceState.MISSING
    assert (
        task_state(missing).readiness
        is task_state(deleted).readiness
        is ScopedReadiness.BLOCKED
    )
    assert task_state(created).readiness is ScopedReadiness.READY


@pytest.mark.asyncio
async def test_archiving_and_ambiguity_change_selected_membership(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = write_plan(harness.root, dependencies=["dependency"])
    path = write_plan(harness.root, "dependency", "DONE")
    first = await harness.read()
    # Act
    archived = path.parent / "archive" / "Other" / path.name
    archived.parent.mkdir(parents=True)
    _ = path.rename(archived)
    moved = await harness.read()
    _ = write_plan(harness.root, "dependency", "DONE")
    ambiguous = await harness.read()
    # Assert
    assert harness.calls == 3
    assert (
        manifest(first)["plan:dependency"].reference
        != manifest(moved)["plan:dependency"].reference
    )
    assert "archive/Other" in manifest(moved)["plan:dependency"].reference
    assert manifest(ambiguous)["plan:dependency"].state is ScopedSourceState.AMBIGUOUS
    assert task_state(ambiguous).readiness is ScopedReadiness.BLOCKED
    assert any(issue.code == "ambiguous" for issue in task_state(ambiguous).issues)


@pytest.mark.asyncio
async def test_goal_prohibitions_and_derivation_revision_are_preserved(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    goal = build_session_goal("Operator goal", "selected", harness.root, ["deploy/**"])
    write_session_goal(harness.root, goal)
    first = await harness.read()
    # Act
    changed = goal.model_copy(
        update={"goal": "New operator goal", "blocked_files": ["secrets/**"]}
    )
    write_session_goal(harness.root, changed)
    second = await harness.read()
    _ = write_plan(harness.root, goal="Plan changed independently.")
    stale = await harness.read()
    # Assert
    assert harness.calls == 3
    assert task_state(first).prohibitions == ["deploy/**"]
    assert task_state(second).goal.value == "New operator goal"
    assert task_state(second).prohibitions == ["secrets/**"]
    assert task_state(second).prohibition_sources == ["session-goal"]
    assert any(
        issue.code == "stale_goal_derivation" for issue in task_state(stale).issues
    )
    assert cast(dict[str, object], stale["session_goal"])["goal"] == "New operator goal"


@pytest.mark.asyncio
async def test_original_rule_bytes_and_stale_delivery_remain_visible(
    harness: ScopedResourceHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    payload = await harness.read_rules()
    first = await harness.read()

    async def stale_rules() -> str:
        return payload

    monkeypatch.setattr(handlers, "get_relevant_rules", stale_rules)
    # Act
    _ = harness.rule.write_text("## Universal\nNew original rule.\n", encoding="utf-8")
    second = await harness.read()
    # Assert
    key = "source:rule:local:general:selected.mdc"
    assert harness.calls == 2
    assert manifest(first)[key].revision != manifest(second)[key].revision
    assert (
        manifest(second)[key].revision == sha256(harness.rule.read_bytes()).hexdigest()
    )
    assert any(
        issue.code == "stale_rule_payload" for issue in task_state(second).issues
    )
    assert "Keep selected rules." in str(scoped_packet(second)["filtered_rules"])


@pytest.mark.asyncio
async def test_decisions_are_source_linked_not_inferred_from_recommendations(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    harness.config["explore_log_path"] = ".cortex/analyses/decision.md"
    missing = await harness.read()
    path = write_source(
        harness.root, ".cortex/analyses/decision.md", "## Recommendation\nChoose A.\n"
    )
    recommended = await harness.read()
    # Act
    _ = path.write_text(
        "## Recommendation\nChoose B.\n\n## Open Decisions\nOperator must choose A or B.\n",
        encoding="utf-8",
    )
    opened = await harness.read()
    # Assert
    assert harness.calls == 3
    assert task_state(missing).open_decisions.state is ScopedEvidenceState.MISSING
    assert task_state(recommended).open_decisions.state is ScopedEvidenceState.MISSING
    assert task_state(opened).open_decisions.value == "Operator must choose A or B."
    key = "file:.cortex/analyses/decision.md"
    assert task_state(opened).open_decisions.sources == [key]
    assert manifest(opened)[key].revision == sha256(path.read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_wiki_ownership_and_selected_original_summary_bytes(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    _ = ensure_default_wiki_layout(harness.root)
    memory = write_source(
        harness.root, ".cortex/memory-bank/sources/memory.md", "# Memory\n"
    )
    wiki = write_source(
        harness.root, ".cortex/wiki/sources/wiki.md", "# Wiki\nOriginal body.\n"
    )
    first = await harness.read()
    # Act
    _ = memory.write_text("# Unselected memory changed\n", encoding="utf-8")
    unrelated = await harness.read()
    _ = wiki.write_text(
        "# Wiki\nChanged body with same rendered title.\n", encoding="utf-8"
    )
    second = await harness.read()
    # Assert
    assert first == unrelated
    assert harness.calls == 2
    assert "wiki.md" in str(second["recent_ingested_sources"])
    assert all(
        source.reference != ".cortex/memory-bank/sources/memory.md"
        for source in manifest(second).values()
    )
    assert (
        manifest(second)["file:.cortex/wiki/sources/wiki.md"].revision
        == sha256(wiki.read_bytes()).hexdigest()
    )


@pytest.mark.asyncio
async def test_root_specific_cache_isolation(
    harness: ScopedResourceHarness, tmp_path: Path
) -> None:
    # Arrange
    first = await harness.read()
    # Act
    harness.root = tmp_path / "second-project"
    _ = write_plan(harness.root, goal="Other project goal.")
    harness.rule = write_source(
        harness.root, ".cortex/rules/selected.mdc", "## Universal\nOther rules.\n"
    )
    second = await harness.read()
    # Assert
    assert harness.calls == 2
    assert task_state(first).plan_goal.value != task_state(second).plan_goal.value
    assert task_state(second).plan_goal.value == "Other project goal."


@pytest.mark.asyncio
async def test_source_revisions_use_exact_crlf_bytes(
    harness: ScopedResourceHarness,
) -> None:
    # Arrange
    path = harness.root / ".cortex/plans/selected.md"
    raw = (
        b"---\r\nstatus: READY\r\ndepends_on: []\r\n---\r\n## Goal\r\nExact bytes.\r\n"
    )
    _ = path.write_bytes(raw)
    # Act
    payload = await harness.read()
    # Assert
    assert manifest(payload)["plan:selected"].revision == sha256(raw).hexdigest()
    assert (
        "\r\n"
        in cast(dict[str, str], scoped_packet(payload)["current_plan"])["content"]
    )
    assert task_state(payload).status.value == "READY"
