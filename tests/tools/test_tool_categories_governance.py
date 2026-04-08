"""Governance tests for TOOL_CATEGORIES vs actual MCP tools (Phase 58/Step 8).

Ensures `categories.py` remains the authoritative source of truth for
tool-search configuration by requiring a 1:1 match between:

- Actual `@mcp.tool()` registrations under `src/cortex/tools`
- `TOOL_CATEGORIES` entries in `cortex.tools.structure.categories`
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cortex.health_check.tool_analyzer import AnalyzedTool, ToolAnalyzer
from cortex.managers.initialization import get_project_root
from cortex.tools.structure.categories import (
    MAX_REGISTERED_TOOLS,
    TARGET_REGISTERED_TOOLS,
    TOOL_CATEGORIES,
    get_category_summary,
)


def _tools_dir() -> Path:
    return get_project_root() / "src" / "cortex" / "tools"


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

    def test_consolidated_tools_not_registered_as_separate_mcp_tools(self) -> None:
        """Pruned/consolidated callables must not appear as standalone MCP tools."""
        tools_dir = _tools_dir()
        analyzer = ToolAnalyzer(tools_dir)
        tools = asyncio.run(analyzer.get_registered_tools())
        registered = set(tools.keys())
        must_not_register = {
            "list_plans",
            "get_plan",
            "run_tool_optimization_workflow",
        }
        leaked = sorted(registered & must_not_register)
        assert not leaked, (
            "These names were consolidated or pruned; they must not be separate "
            f"@mcp.tool registrations: {leaked}"
        )

    def test_registered_tools_respect_budget(self) -> None:
        """Total registered tools must not exceed the configured budget."""
        summary = get_category_summary()
        total_tools = sum(summary.values())

        assert total_tools <= MAX_REGISTERED_TOOLS, (
            "Registered tools exceed MAX_REGISTERED_TOOLS; either consolidate or "
            "remove tools, or intentionally raise MAX_REGISTERED_TOOLS in "
            "categories.py alongside an updated consolidation plan."
        )

        # Sanity check: TOOL_CATEGORIES should remain the single source of truth.
        assert total_tools == len(TOOL_CATEGORIES)

    def test_max_registered_tools_cap(self) -> None:
        """Budget cap matches target (see docs/api/tools.md)."""
        assert MAX_REGISTERED_TOOLS == 12
        assert TARGET_REGISTERED_TOOLS <= MAX_REGISTERED_TOOLS


class TestToolDescriptionGovernance:
    """Phase 92 governance: tool docstrings follow description rubric."""

    def _get_registered_tools(self) -> dict[str, AnalyzedTool]:
        """Helper to load registered tools using ToolAnalyzer."""
        tools_dir = _tools_dir()
        assert tools_dir.is_dir(), f"Tools dir not found: {tools_dir}"
        analyzer = ToolAnalyzer(tools_dir)
        return asyncio.run(analyzer.get_registered_tools())

    def test_registered_tools_have_use_when_and_examples(self) -> None:
        """Every registered tool docstring should include USE WHEN and EXAMPLES sections."""
        tools = self._get_registered_tools()
        missing_use_when: list[str] = []
        missing_examples: list[str] = []

        for name, tool in tools.items():
            doc = (tool.docstring or "").lower()
            if "use when" not in doc:
                missing_use_when.append(name)
            if "examples" not in doc:
                missing_examples.append(name)

        assert not missing_use_when and not missing_examples, (
            "All MCP tools must document usage via USE WHEN/EXAMPLES sections. "
            f"Missing USE WHEN: {sorted(missing_use_when)}; "
            f"Missing EXAMPLES: {sorted(missing_examples)}."
        )

    def test_high_risk_tools_include_anti_pattern_guidance(self) -> None:
        """High-risk tools must include explicit anti-pattern guidance (DO NOT / Prefer)."""
        tools = self._get_registered_tools()
        # health_check and get_structure_info are now MCP resources, not tools.
        high_risk_tools = {
            "manage_file",
            "update_memory_bank",
        }

        missing_guidance: list[str] = []
        for name in sorted(high_risk_tools):
            tool = tools.get(name)
            assert (
                tool is not None
            ), f"High-risk tool {name!r} not found in registered tools"
            doc = (tool.docstring or "").lower()
            if not any(
                phrase in doc
                for phrase in (
                    "do not",
                    "don't ",
                    "prefer ",
                    "preferred over",
                    "preferred to",
                )
            ):
                missing_guidance.append(name)

        assert not missing_guidance, (
            "High-risk tools must include at least one explicit anti-pattern callout "
            "(DO NOT / Prefer ...). Missing guidance for: "
            f"{sorted(missing_guidance)}."
        )
