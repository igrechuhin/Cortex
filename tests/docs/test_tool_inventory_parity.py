"""Parity: canonical TOOL_CATEGORIES vs generated JSON and agent-facing docs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from cortex.tools.structure.categories import TOOL_CATEGORIES

_REPO_ROOT = Path(__file__).resolve().parents[2]
_README = _REPO_ROOT / "README.md"
_AGENTS = _REPO_ROOT / "AGENTS.md"
_GENERATED_JSON = _REPO_ROOT / "docs" / "_generated" / "tool-inventory.json"


def _section(text: str, heading: str, next_heading_level: str = "##") -> str:
    """Return the body of *heading* (a `##` line) until the next same-level heading."""
    pattern = rf"(?ms)^{re.escape(heading)}\s*\n+(.*?)(?=^{next_heading_level}\s|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE)
    assert match is not None, f"missing section {heading!r}"
    return match.group(1)


def test_tool_categories_match_generated_json() -> None:
    data = json.loads(_GENERATED_JSON.read_text(encoding="utf-8"))
    names_on_disk = set(data["tool_names"])
    expected = {entry.name for entry in TOOL_CATEGORIES}
    assert names_on_disk == expected
    assert data["tools_count"] == len(TOOL_CATEGORIES)


def test_readme_key_tools_lists_all_registered_tools() -> None:
    readme = _README.read_text(encoding="utf-8")
    key_tools = _section(readme, "## Key Tools")
    for entry in TOOL_CATEGORIES:
        assert entry.name in key_tools, (
            f"README Key Tools section must mention `{entry.name}` "
            "(sync with TOOL_CATEGORIES)."
        )


def _subsection_between(text: str, start_heading: str, end_heading: str) -> str:
    start = text.index(start_heading)
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def test_agents_tools_table_lists_all_registered_tools() -> None:
    agents = _AGENTS.read_text(encoding="utf-8")
    tools_block = _subsection_between(agents, "### Tools", "### Resources")
    for entry in TOOL_CATEGORIES:
        assert entry.name in tools_block, (
            f"AGENTS.md tools table must mention `{entry.name}` "
            "(sync with TOOL_CATEGORIES)."
        )
