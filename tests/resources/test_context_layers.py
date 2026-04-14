from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.context.l0_identity import build_l0
from cortex.tools.context.l1_essential import build_l1, score_paragraph
from cortex.tools.context.l2_on_demand import build_l2
from cortex.tools.context.l3_deep_search import build_l3
from cortex.tools.context.layers import ContextConfig, ContextLayer


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
