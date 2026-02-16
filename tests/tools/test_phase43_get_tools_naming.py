"""Tests for Phase 43: get_* tools are read-only (naming convention).

All MCP tools whose name starts with get_ must be read-only (Resource candidates).
No side-effecting operation should be named get_*. See Phase 43 plan and
docs/api/tools.md "Tools vs Resources".
"""

from cortex.discovery.tool_registry import get_known_tool_names

# Phase 43: read-only get_* tool names (subset of get_known_tool_names()).
# Keep in sync with discovery/tool_registry.py. Any new get_* tool must be read-only.
# Phase 50: get_dependency_graph, get_link_graph, get_memory_bank_stats, get_version_history
# consolidated into query_memory_bank (no longer get_* tools).
_READ_ONLY_GET_TOOLS: frozenset[str] = frozenset(
    {
        "get_file_metadata",
        "get_memory_bank_structure",
        "get_optimization_insights",
        "get_quality_score",
        "get_relevance_scores",
        "get_refactoring_history",
        "get_relevant_rules",
        "get_structure_info",
    }
)


class TestPhase43GetToolsNaming:
    """Assert no get_* tool is side-effecting (naming convention)."""

    def test_all_get_tools_are_in_read_only_list(self) -> None:
        """Every get_* tool in the registry must be in the read-only allow list."""
        known = get_known_tool_names()
        get_tools = [n for n in known if n.startswith("get_")]
        not_allowed = [n for n in get_tools if n not in _READ_ONLY_GET_TOOLS]
        assert not not_allowed, (
            "get_* tools must be read-only (Phase 43). "
            + "Add to _READ_ONLY_GET_TOOLS or rename: "
            + ", ".join(not_allowed)
        )

    def test_read_only_list_matches_registry_get_tools(self) -> None:
        """Read-only set equals get_* names in registry (no extras, no missing)."""
        known = set(get_known_tool_names())
        get_in_registry = frozenset(n for n in known if n.startswith("get_"))
        assert _READ_ONLY_GET_TOOLS == get_in_registry, (
            "Sync _READ_ONLY_GET_TOOLS with get_known_tool_names() get_* entries. "
            + f"Missing: {get_in_registry - _READ_ONLY_GET_TOOLS}. "
            + f"Extra: {_READ_ONLY_GET_TOOLS - get_in_registry}."
        )
