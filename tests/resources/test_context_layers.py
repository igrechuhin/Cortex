from __future__ import annotations

from pathlib import Path

import pytest

from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import write_session_goal
from cortex.tools.context.l0_identity import build_l0
from cortex.tools.context.l1_essential import build_l1, score_paragraph
from cortex.tools.context.l2_on_demand import build_l2
from cortex.tools.context.l3_deep_search import build_l3
from cortex.tools.context.layers import ContextConfig, ContextLayer
from cortex.tools.context.relevance_ranking import RELEVANCE_RANKING_ENV_FLAG


def count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


@pytest.mark.asyncio
async def test_build_l0_with_budget_and_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-app"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    session_dir = tmp_path / ".cortex" / ".session"
    _ = session_dir.mkdir(parents=True)
    _ = (session_dir / "session-goal.md").write_text(
        "Goal line one\nGoal line two\nGoal line three",
        encoding="utf-8",
    )

    def _fake_commit(_: Path) -> str:
        return "abc123 implement layered context"

    monkeypatch.setattr(
        "cortex.tools.context.l0_identity._read_last_commit_summary", _fake_commit
    )

    result = await build_l0(tmp_path, ContextConfig(max_l0_tokens=150))

    assert result.layer == ContextLayer.IDENTITY
    assert count_tokens(result.content) <= 150
    assert "demo-app" in result.content


@pytest.mark.asyncio
async def test_build_l1_prefers_blocker_paragraphs(tmp_path: Path) -> None:
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    _ = memory_bank.mkdir(parents=True)
    _ = (memory_bank / "activeContext.md").write_text(
        "## Current Focus\n\nactive feature work\n\n## Blockers\n\ncritical blocker here",
        encoding="utf-8",
    )
    _ = (memory_bank / "progress.md").write_text(
        "## Notes\n\nroutine update\n\n## Decision\n\ndecision captured",
        encoding="utf-8",
    )

    result = await build_l1(
        tmp_path, ContextConfig(max_l1_tokens=120, l1_source_limit=3)
    )

    assert result.layer == ContextLayer.ESSENTIAL
    assert count_tokens(result.content) <= 120
    assert "blocker" in result.content.lower()
    assert score_paragraph("critical blocker") > score_paragraph("routine update")


def test_score_paragraph_boosts_typed_decision() -> None:
    decision = "<!-- memory_type: decision -->\nroutine update"
    status = "<!-- memory_type: status -->\nroutine update"
    assert score_paragraph(decision) > score_paragraph(status)


@pytest.mark.asyncio
async def test_build_l2_resolves_topic_and_empty_when_missing(tmp_path: Path) -> None:
    plans = tmp_path / ".cortex" / "plans"
    _ = plans.mkdir(parents=True)
    _ = (plans / "fastmcp-v3-phase2.md").write_text(
        "# Plan\n\nDetails for phase2 plan.\n\nMore lines.",
        encoding="utf-8",
    )

    found = await build_l2(
        tmp_path, ContextConfig(max_l2_tokens=500), "fastmcp-v3-phase2"
    )
    missing = await build_l2(tmp_path, ContextConfig(max_l2_tokens=500), "nonexistent")

    assert found.layer == ContextLayer.ON_DEMAND
    assert found.content
    assert found.sources == [".cortex/plans/fastmcp-v3-phase2.md"]
    assert missing.layer == ContextLayer.ON_DEMAND
    assert missing.content == ""
    assert missing.sources == []


@pytest.mark.asyncio
async def test_build_l3_returns_ranked_results(tmp_path: Path) -> None:
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    _ = memory_bank.mkdir(parents=True)
    _ = (memory_bank / "roadmap.md").write_text(
        "## Pending\n\nblocker item one\n\nanother paragraph",
        encoding="utf-8",
    )
    _ = (memory_bank / "activeContext.md").write_text(
        "## Active\n\nblocker item two\n\nmore context",
        encoding="utf-8",
    )

    result = await build_l3(tmp_path, "blocker")

    assert result.layer == ContextLayer.DEEP_SEARCH
    assert "roadmap.md" in "\n".join(result.sources)
    assert "activeContext.md" in "\n".join(result.sources)


def _write_l0_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-app"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    session_dir = tmp_path / ".cortex" / ".session"
    _ = session_dir.mkdir(parents=True)
    _ = (session_dir / "session-goal.md").write_text(
        "Fix the auth token refresh bug urgently", encoding="utf-8"
    )

    def _fake_commit(_: Path) -> str:
        return "zzzpad zzzpad zzzpad zzzpad zzzpad"

    monkeypatch.setattr(
        "cortex.tools.context.l0_identity._read_last_commit_summary", _fake_commit
    )


@pytest.mark.asyncio
async def test_build_l0_relevance_ranking_preserves_goal_keywords_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: a tiny budget forces the positional word-cut to reach into the
    # "Primary goal" line; ranking should move that line earlier so it
    # survives the cut instead.
    _write_l0_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    # Act
    result = await build_l0(tmp_path, ContextConfig(max_l0_tokens=15))

    # Assert
    assert "token" in result.content


@pytest.mark.asyncio
async def test_build_l0_positional_truncation_drops_goal_keyword_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: same fixture and budget, ranking left at its disabled default.
    _write_l0_fixture(tmp_path, monkeypatch)
    monkeypatch.delenv(RELEVANCE_RANKING_ENV_FLAG, raising=False)

    # Act
    result = await build_l0(tmp_path, ContextConfig(max_l0_tokens=15))

    # Assert
    assert "token" not in result.content


def _write_l2_fixture(tmp_path: Path) -> Path:
    # AI: heading and body share one blank-line-delimited paragraph block
    # (single "\n" between them) so each section is one ranking candidate,
    # matching how `_truncate_paragraphs` splits on blank lines.
    plans = tmp_path / ".cortex" / "plans"
    _ = plans.mkdir(parents=True)
    path = plans / "auth-fix.md"
    context_section = "## Context\n" + (
        "This plan covers routine maintenance chores and changelog "
        "housekeeping for the release notes generator with unrelated "
        "background padding text to consume additional space here."
    )
    auth_section = "## Auth Token Bug Fix\nFix the auth token bug."
    risks_section = "## Risks\n" + (
        "Generic risk boilerplate about deployment windows and rollback "
        "procedures for unrelated release trains entirely."
    )
    testing_section = "## Testing\n" + (
        "Generic testing boilerplate notes about CI pipelines and coverage "
        "thresholds for unrelated release trains as well."
    )
    _ = path.write_text(
        "\n\n".join([context_section, auth_section, risks_section, testing_section])
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_build_l2_relevance_ranking_keeps_relevant_section_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: budget only fits one paragraph; the semantically relevant
    # "Auth Token Bug Fix" section is not the first paragraph positionally.
    _ = _write_l2_fixture(tmp_path)
    _ = write_session_goal(
        tmp_path, SessionGoal(goal="fix the auth token bug", plan_slug=None)
    )
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=15), "auth-fix")

    # Assert
    assert "auth token bug" in result.content.lower()


@pytest.mark.asyncio
async def test_build_l2_positional_truncation_ignores_relevance_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: same fixture/budget/goal, ranking left at its disabled default.
    _ = _write_l2_fixture(tmp_path)
    _ = write_session_goal(
        tmp_path, SessionGoal(goal="fix the auth token bug", plan_slug=None)
    )
    monkeypatch.delenv(RELEVANCE_RANKING_ENV_FLAG, raising=False)

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=15), "auth-fix")

    # Assert: the first (boilerplate) paragraph alone already exceeds the
    # budget, so positional greedy-fill keeps nothing.
    assert result.content == ""


@pytest.mark.asyncio
async def test_build_l2_no_truncation_when_budget_exceeds_total_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: negative case - budget larger than all paragraphs combined.
    _ = _write_l2_fixture(tmp_path)
    _ = write_session_goal(
        tmp_path, SessionGoal(goal="fix the auth token bug", plan_slug=None)
    )
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=500), "auth-fix")

    # Assert: nothing is dropped, regardless of ranking being enabled.
    assert "Context" in result.content
    assert "Auth Token Bug Fix" in result.content
    assert "Risks" in result.content
    assert "Testing" in result.content


@pytest.mark.asyncio
async def test_build_l2_single_paragraph_no_ranking_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: negative case - a single-paragraph file (ranking is a no-op
    # for fewer than two candidates).
    plans = tmp_path / ".cortex" / "plans"
    _ = plans.mkdir(parents=True)
    _ = (plans / "solo.md").write_text("Only one paragraph here.", encoding="utf-8")
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=500), "solo")

    # Assert
    assert result.content == "Only one paragraph here."


@pytest.mark.asyncio
async def test_build_l2_empty_file_returns_empty_content(tmp_path: Path) -> None:
    # Arrange: negative case - an empty candidate list (empty file content).
    plans = tmp_path / ".cortex" / "plans"
    _ = plans.mkdir(parents=True)
    _ = (plans / "blank.md").write_text("", encoding="utf-8")

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=500), "blank")

    # Assert
    assert result.content == ""


@pytest.mark.asyncio
async def test_build_l2_fails_open_when_ranking_encoder_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: negative case - the embedding encoder raises; context loading
    # must never break, so output should match the positional-truncation path.
    _ = _write_l2_fixture(tmp_path)
    _ = write_session_goal(
        tmp_path, SessionGoal(goal="fix the auth token bug", plan_slug=None)
    )
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    class _RaisingEncoder:
        dim = 8
        version = "raising-v1"

        def encode(self, text: str) -> list[float]:
            raise RuntimeError("embedding backend unavailable")

    monkeypatch.setattr(
        "cortex.tools.context.relevance_ranking._shared_encoder", _RaisingEncoder()
    )

    # Act
    result = await build_l2(tmp_path, ContextConfig(max_l2_tokens=15), "auth-fix")

    # Assert: same result as the disabled/positional path - fails open.
    assert result.content == ""
