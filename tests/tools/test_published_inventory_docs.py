"""Drift checks: published MCP inventory vs README markers and generated JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cortex.discovery.published_inventory import (
    PUBLISHED_STATIC_RESOURCE_URIS,
    published_inventory_json,
    published_inventory_payload,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_README = _REPO_ROOT / "README.md"
_GENERATED_JSON = _REPO_ROOT / "docs" / "_generated" / "tool-inventory.json"

_INV_MARKER_PATTERN = "".join(
    (
        r"<!--\s*cortex-published-inventory:\s*tools=(\d+)\s+",
        r"resources=(\d+)\s+prompts-max=(\d+)\s*-->",
    )
)
_INVENTORY_MARKER = re.compile(_INV_MARKER_PATTERN)


@pytest.mark.timeout(15)
def test_tool_inventory_json_matches_code() -> None:
    """Checked-in JSON must match :func:`published_inventory_json`."""
    expected = published_inventory_json()
    on_disk = _GENERATED_JSON.read_text(encoding="utf-8")
    assert on_disk == expected, (
        "docs/_generated/tool-inventory.json is stale; overwrite it with the string returned by "
        "cortex.discovery.published_inventory.published_inventory_json() (UTF-8)."
    )


@pytest.mark.timeout(15)
def test_readme_inventory_markers_match_code() -> None:
    """README must embed counts matching TOOL_CATEGORIES and static resources."""
    text = _README.read_text(encoding="utf-8")
    match = _INVENTORY_MARKER.search(text)
    assert match is not None, (
        "README.md must contain "
        "<!-- cortex-published-inventory: tools=N resources=M prompts-max=P -->"
    )
    payload = published_inventory_payload()
    tools_count = int(match.group(1))
    resources_count = int(match.group(2))
    prompts_max = int(match.group(3))
    assert tools_count == payload["tools_count"]
    assert resources_count == payload["resources_count"]
    prompts = payload["prompts"]
    assert isinstance(prompts, dict)
    assert prompts_max == prompts["max_exposed"]


@pytest.mark.timeout(15)
def test_generated_json_matches_resource_uris() -> None:
    """Sanity: JSON static_resources matches module constant."""
    data = json.loads(_GENERATED_JSON.read_text(encoding="utf-8"))
    assert data["static_resources"] == list(PUBLISHED_STATIC_RESOURCE_URIS)
