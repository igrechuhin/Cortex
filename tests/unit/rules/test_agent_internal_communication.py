"""Tests for `.cortex/synapse/rules/general/agent-internal-communication.mdc`."""

from __future__ import annotations

from pathlib import Path


def test_agent_internal_communication_rule_file_has_required_sections() -> None:
    repo = Path(__file__).resolve().parents[3]
    text = (
        repo
        / ".cortex"
        / "synapse"
        / "rules"
        / "general"
        / "agent-internal-communication.mdc"
    ).read_text(encoding="utf-8")
    assert "# Agent-Internal Communication" in text
    assert "Does NOT apply" in text
    assert "think()" in text or "think" in text
