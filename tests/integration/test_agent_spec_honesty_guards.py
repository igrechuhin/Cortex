"""Guards against agent specs that invite fabricated gate results.

Regression: commit Phase C shipped a pre-filled `"status":"passed"` JSON
template, so an agent whose validation tool call failed could copy the
template verbatim and pass the gate it never ran.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.integration.conftest import synapse_path

NO_FABRICATION_RULE = "Never write a value you did not observe"


def _agent_specs() -> list[Path]:
    return sorted((synapse_path() / "claude-agents").glob("*.md"))


def test_agent_specs_have_no_prefilled_passed_status() -> None:
    """Handoff templates must use placeholders, not a literal passed status."""
    offenders = [
        path.name
        for path in _agent_specs()
        if re.search(r'"status"\s*:\s*"passed"', path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Pre-filled passed status in: {offenders}"


def test_handoff_writing_agents_forbid_unobserved_values() -> None:
    """Every agent writing a gate result carries the no-fabrication rule."""
    missing = [
        path.name
        for path in _agent_specs()
        if '"operation":"write"' in (text := path.read_text(encoding="utf-8"))
        and NO_FABRICATION_RULE not in text
    ]
    assert not missing, f"Missing no-fabrication rule in: {missing}"


def test_resource_reading_agents_are_granted_resource_tool() -> None:
    """Agents told to read cortex:// resources must have the tool granted."""
    missing: list[str] = []
    for path in _agent_specs():
        text = path.read_text(encoding="utf-8")
        tools = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE)
        if (
            "cortex://" in text
            and tools
            and "ReadMcpResourceTool" not in tools.group(1)
        ):
            missing.append(path.name)
    assert not missing, f"Missing ReadMcpResourceTool grant in: {missing}"
