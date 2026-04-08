"""Cursor agent prompts reference agent-internal brevity for structured results."""

from __future__ import annotations

from pathlib import Path


def test_implement_code_mentions_agent_internal_brevity() -> None:
    repo = Path(__file__).resolve().parents[2]
    text = (
        repo / ".cortex" / "synapse" / "cursor-agents" / "implement-code.md"
    ).read_text(encoding="utf-8")
    assert "Agent-Internal Communication" in text
    assert "cortex://rules" in text


def test_shared_defaults_mentions_agent_internal_brevity() -> None:
    repo = Path(__file__).resolve().parents[2]
    text = (
        repo / ".cortex" / "synapse" / "cursor-agents" / "shared-defaults.md"
    ).read_text(encoding="utf-8")
    assert "Agent-internal result text" in text
    assert "cortex://rules" in text
