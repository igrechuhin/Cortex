"""Governance tests for TOOL_CATEGORIES vs actual MCP tools (Phase 58/Step 8).

Ensures `tool_categories.py` remains the authoritative source of truth for
tool-search configuration by requiring a 1:1 match between:

- Actual `@mcp.tool()` registrations under `src/cortex/tools`
- `TOOL_CATEGORIES` entries in `cortex.tools.tool_categories`
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cortex.health_check.tool_analyzer import ToolAnalyzer
from cortex.tools.tool_categories import TOOL_CATEGORIES


def _tools_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "src" / "cortex" / "tools"


class TestToolCategoriesGovernance:
    """Phase 58 governance: registered tools == TOOL_CATEGORIES."""

    def test_registered_tools_match_tool_categories(self) -> None:
        """Every @mcp.tool() must have a ToolCategoryEntry and vice versa."""
        tools_dir = _tools_dir()
        assert tools_dir.is_dir(), f"Tools dir not found: {tools_dir}"

        analyzer = ToolAnalyzer(tools_dir)
        tools = asyncio.run(analyzer.get_registered_tools())
        registered = set(tools.keys())
        categorized = {entry.name for entry in TOOL_CATEGORIES}

        missing_in_categories = sorted(registered - categorized)
        extra_in_categories = sorted(categorized - registered)

        assert not missing_in_categories and not extra_in_categories, (
            "Registered tools must match TOOL_CATEGORIES. "
            f"Missing in TOOL_CATEGORIES: {missing_in_categories}. "
            f"Extra in TOOL_CATEGORIES: {extra_in_categories}."
        )
