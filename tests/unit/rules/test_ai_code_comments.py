"""Tests for `.cortex/synapse/rules/general/ai-code-comments.mdc` conventions."""

from __future__ import annotations

from pathlib import Path


def test_ai_code_comments_rule_file_has_required_sections() -> None:
    repo = Path(__file__).resolve().parents[3]
    text = (
        repo / ".cortex" / "synapse" / "rules" / "general" / "ai-code-comments.mdc"
    ).read_text(encoding="utf-8")
    assert "## AI Comment Convention" in text
    assert "## BELIEF Declaration Convention" in text
    assert "## When NOT to use" in text
    assert "## Format" in text
