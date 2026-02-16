"""Unit tests for tool_categories module (Phase 49 Step 4).

Validates tool categorization, lookup helpers, config generation,
and consistency with actual registered MCP tools.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from cortex.tools.tool_categories import (
    TOOL_CATEGORIES,
    ToolCategory,
    ToolCategoryConfig,
    ToolCategoryEntry,
    ToolCategoryName,
    ToolSearchResult,
    build_category_config,
    get_always_loaded_tool_names,
    get_category_summary,
    get_deferred_tool_names,
    get_tool_category,
    get_tools_by_category,
    search_deferred_tools,
)

# ---------------------------------------------------------------------------
# Constants for expected counts (update when tools are added/removed)
# ---------------------------------------------------------------------------

_MIN_ALWAYS_LOADED = 12  # at least this many core tools
_MIN_DEFERRED_MEDIUM = 15
_MIN_DEFERRED_LOW = 10
_MIN_TOTAL_TOOLS = (
    48  # Phase 50: query_memory_bank + query_usage consolidated 15 tools → 2
)


@pytest.mark.timeout(5)
class TestToolCategoryEnum:
    """Tests for ToolCategory enum."""

    def test_has_three_values(self) -> None:
        """ToolCategory has exactly three tiers."""
        assert len(ToolCategory) == 3

    def test_values_are_lowercase_strings(self) -> None:
        """Each enum value is a lowercase snake_case string."""
        for cat in ToolCategory:
            assert cat.value == cat.value.lower()
            assert "_" in cat.value or cat.value == "always_loaded"

    def test_str_representation(self) -> None:
        """Enum members behave as strings."""
        assert ToolCategory.ALWAYS_LOADED == "always_loaded"
        assert ToolCategory.DEFERRED_MEDIUM == "deferred_medium"
        assert ToolCategory.DEFERRED_LOW == "deferred_low"


@pytest.mark.timeout(5)
class TestToolCategoryEntry:
    """Tests for ToolCategoryEntry Pydantic model."""

    def test_create_entry(self) -> None:
        """Can create an entry with all fields."""
        entry = ToolCategoryEntry(
            name="test_tool",
            category=ToolCategory.ALWAYS_LOADED,
            rationale="Testing entry creation",
        )
        assert entry.name == "test_tool"
        assert entry.category == ToolCategory.ALWAYS_LOADED
        assert entry.rationale == "Testing entry creation"

    def test_entry_is_frozen(self) -> None:
        """ToolCategoryEntry instances are immutable."""
        entry = ToolCategoryEntry(
            name="test_tool",
            category=ToolCategory.DEFERRED_LOW,
            rationale="immutable test",
        )
        with pytest.raises(ValidationError):
            entry.name = "changed"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        """Entry can be serialized and deserialized."""
        entry = ToolCategoryEntry(
            name="manage_file",
            category=ToolCategory.ALWAYS_LOADED,
            rationale="Core file ops",
        )
        data = entry.model_dump()
        restored = ToolCategoryEntry.model_validate(data)
        assert restored == entry


@pytest.mark.timeout(5)
class TestToolCategoryConfig:
    """Tests for ToolCategoryConfig Pydantic model."""

    def test_default_disabled(self) -> None:
        """Default config has enabled=False."""
        config = ToolCategoryConfig()
        assert config.enabled is False
        assert config.always_loaded == []
        assert config.deferred_medium == []
        assert config.deferred_low == []

    def test_config_is_frozen(self) -> None:
        """Config instances are immutable."""
        config = ToolCategoryConfig(enabled=True, always_loaded=["a"])
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]


@pytest.mark.timeout(5)
class TestToolCategoriesMapping:
    """Tests for the canonical TOOL_CATEGORIES mapping."""

    def test_is_tuple(self) -> None:
        """TOOL_CATEGORIES is an immutable tuple."""
        assert isinstance(TOOL_CATEGORIES, tuple)

    def test_minimum_tool_count(self) -> None:
        """At least _MIN_TOTAL_TOOLS tools are catalogued."""
        assert len(TOOL_CATEGORIES) >= _MIN_TOTAL_TOOLS

    def test_no_duplicate_names(self) -> None:
        """Every tool name appears exactly once."""
        names = [e.name for e in TOOL_CATEGORIES]
        assert len(names) == len(
            set(names)
        ), f"Duplicates found: {[n for n in names if names.count(n) > 1]}"

    def test_every_entry_has_nonempty_rationale(self) -> None:
        """Every entry must document its categorization rationale."""
        for entry in TOOL_CATEGORIES:
            assert entry.rationale.strip(), f"{entry.name} has empty rationale"

    def test_every_entry_has_valid_category(self) -> None:
        """Every entry has a valid ToolCategory."""
        for entry in TOOL_CATEGORIES:
            assert isinstance(entry.category, ToolCategory)

    def test_always_loaded_minimum(self) -> None:
        """Enough tools are marked always_loaded for the core workflow."""
        always = [
            e for e in TOOL_CATEGORIES if e.category == ToolCategory.ALWAYS_LOADED
        ]
        assert len(always) >= _MIN_ALWAYS_LOADED

    def test_deferred_medium_minimum(self) -> None:
        """Enough tools are deferred_medium."""
        medium = [
            e for e in TOOL_CATEGORIES if e.category == ToolCategory.DEFERRED_MEDIUM
        ]
        assert len(medium) >= _MIN_DEFERRED_MEDIUM

    def test_deferred_low_minimum(self) -> None:
        """Enough tools are deferred_low."""
        low = [e for e in TOOL_CATEGORIES if e.category == ToolCategory.DEFERRED_LOW]
        assert len(low) >= _MIN_DEFERRED_LOW

    def test_core_tools_are_always_loaded(self) -> None:
        """Critical tools that appear in every session are always_loaded."""
        core_tools = {
            "manage_file",
            "validate",
            "load_context",
            "execute_pre_commit_checks",
            "get_structure_info",
            "rules",
        }
        for name in core_tools:
            cat = get_tool_category(name)
            assert (
                cat == ToolCategory.ALWAYS_LOADED
            ), f"Core tool {name!r} should be ALWAYS_LOADED, got {cat}"

    def test_analytics_tools_are_deferred_low(self) -> None:
        """Usage analytics consolidated tool should be deferred_low (Phase 50)."""
        analytics_tool = "query_usage"
        cat = get_tool_category(analytics_tool)
        assert (
            cat == ToolCategory.DEFERRED_LOW
        ), f"Analytics tool {analytics_tool!r} should be DEFERRED_LOW, got {cat}"


@pytest.mark.timeout(5)
class TestGetToolCategory:
    """Tests for get_tool_category() lookup."""

    def test_known_tool(self) -> None:
        """Returns correct category for a known tool."""
        assert get_tool_category("manage_file") == ToolCategory.ALWAYS_LOADED

    def test_unknown_tool(self) -> None:
        """Returns None for an uncatalogued tool name."""
        assert get_tool_category("nonexistent_tool_xyz") is None

    def test_empty_string(self) -> None:
        """Returns None for empty string."""
        assert get_tool_category("") is None


@pytest.mark.timeout(5)
class TestGetToolsByCategory:
    """Tests for get_tools_by_category() filter."""

    def test_always_loaded_returns_entries(self) -> None:
        """Returns non-empty list for ALWAYS_LOADED."""
        result = get_tools_by_category(ToolCategory.ALWAYS_LOADED)
        assert len(result) >= _MIN_ALWAYS_LOADED
        assert all(e.category == ToolCategory.ALWAYS_LOADED for e in result)

    def test_deferred_medium_returns_entries(self) -> None:
        """Returns non-empty list for DEFERRED_MEDIUM."""
        result = get_tools_by_category(ToolCategory.DEFERRED_MEDIUM)
        assert len(result) >= _MIN_DEFERRED_MEDIUM

    def test_deferred_low_returns_entries(self) -> None:
        """Returns non-empty list for DEFERRED_LOW."""
        result = get_tools_by_category(ToolCategory.DEFERRED_LOW)
        assert len(result) >= _MIN_DEFERRED_LOW

    def test_all_categories_cover_all_tools(self) -> None:
        """Sum of all categories equals total tools."""
        total = sum(len(get_tools_by_category(cat)) for cat in ToolCategory)
        assert total == len(TOOL_CATEGORIES)


@pytest.mark.timeout(5)
class TestGetAlwaysLoadedToolNames:
    """Tests for get_always_loaded_tool_names()."""

    def test_returns_sorted_list(self) -> None:
        """Result is sorted alphabetically."""
        names = get_always_loaded_tool_names()
        assert names == sorted(names)

    def test_contains_core_tools(self) -> None:
        """Contains essential core tools."""
        names = get_always_loaded_tool_names()
        assert "manage_file" in names
        assert "validate" in names
        assert "load_context" in names

    def test_no_deferred_tools(self) -> None:
        """No deferred tools appear in always_loaded list."""
        always = set(get_always_loaded_tool_names())
        deferred = set(get_deferred_tool_names())
        overlap = always & deferred
        assert not overlap, f"Overlap between always and deferred: {overlap}"


@pytest.mark.timeout(5)
class TestGetDeferredToolNames:
    """Tests for get_deferred_tool_names()."""

    def test_returns_sorted_list(self) -> None:
        """Result is sorted alphabetically."""
        names = get_deferred_tool_names()
        assert names == sorted(names)

    def test_includes_medium_and_low(self) -> None:
        """Contains tools from both deferred_medium and deferred_low."""
        names = set(get_deferred_tool_names())
        assert "suggest_refactoring" in names  # medium
        assert "rollback_file_version" in names  # low

    def test_no_always_loaded_tools(self) -> None:
        """No always_loaded tools appear in deferred list."""
        deferred = set(get_deferred_tool_names())
        always = set(get_always_loaded_tool_names())
        overlap = deferred & always
        assert not overlap, f"Overlap: {overlap}"


@pytest.mark.timeout(5)
class TestBuildCategoryConfig:
    """Tests for build_category_config()."""

    def test_returns_config_model(self) -> None:
        """Returns a ToolCategoryConfig instance."""
        config = build_category_config()
        assert isinstance(config, ToolCategoryConfig)

    def test_disabled_by_default(self) -> None:
        """Config has enabled=False (deferred loading not yet supported)."""
        config = build_category_config()
        assert config.enabled is False

    def test_all_tools_present(self) -> None:
        """All catalogued tools appear in exactly one list."""
        config = build_category_config()
        all_names = set(
            config.always_loaded + config.deferred_medium + config.deferred_low
        )
        catalogued_names = {e.name for e in TOOL_CATEGORIES}
        assert all_names == catalogued_names

    def test_no_overlap_between_lists(self) -> None:
        """No tool appears in more than one list."""
        config = build_category_config()
        a = set(config.always_loaded)
        m = set(config.deferred_medium)
        lo = set(config.deferred_low)
        assert not (a & m), f"always ∩ medium: {a & m}"
        assert not (a & lo), f"always ∩ low: {a & lo}"
        assert not (m & lo), f"medium ∩ low: {m & lo}"

    def test_lists_are_sorted(self) -> None:
        """All category lists are sorted."""
        config = build_category_config()
        assert config.always_loaded == sorted(config.always_loaded)
        assert config.deferred_medium == sorted(config.deferred_medium)
        assert config.deferred_low == sorted(config.deferred_low)

    def test_serialization_roundtrip(self) -> None:
        """Config can be serialized to JSON and back."""
        config = build_category_config()
        data = config.model_dump()
        restored = ToolCategoryConfig.model_validate(data)
        assert restored == config


@pytest.mark.timeout(5)
class TestGetCategorySummary:
    """Tests for get_category_summary()."""

    def test_returns_dict_with_all_categories(self) -> None:
        """Summary has exactly three keys."""
        summary = get_category_summary()
        assert set(summary.keys()) == {
            "always_loaded",
            "deferred_medium",
            "deferred_low",
        }

    def test_counts_are_positive(self) -> None:
        """Every category has at least one tool."""
        summary = get_category_summary()
        for cat, count in summary.items():
            assert count > 0, f"Category {cat} has 0 tools"

    def test_counts_sum_to_total(self) -> None:
        """Sum of counts equals total catalogued tools."""
        summary = get_category_summary()
        assert sum(summary.values()) == len(TOOL_CATEGORIES)

    def test_summary_keys_match_category_values(self) -> None:
        """Summary keys exactly match ToolCategory enum values."""
        summary = get_category_summary()
        category_values = {cat.value for cat in ToolCategory}
        assert set(summary.keys()) == category_values


@pytest.mark.timeout(5)
class TestToolCategoryNameLiteral:
    """Tests for ToolCategoryName type alias."""

    def test_literal_values_match_enum(self) -> None:
        """Literal values match ToolCategory enum values."""
        # ToolCategoryName is Literal["always_loaded", "deferred_medium",
        # "deferred_low"].  Verify the enum values match.
        enum_values = {cat.value for cat in ToolCategory}
        expected: set[ToolCategoryName] = {
            "always_loaded",
            "deferred_medium",
            "deferred_low",
        }
        assert enum_values == expected


# ---------------------------------------------------------------------------
# search_deferred_tools (Phase 49 Step 5)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
class TestToolSearchResult:
    """Tests for ToolSearchResult model."""

    def test_create_result(self) -> None:
        """Can create a result with name, category, rationale."""
        r = ToolSearchResult(
            name="suggest_refactoring",
            category=ToolCategory.DEFERRED_MEDIUM,
            rationale="Refactoring workflow",
        )
        assert r.name == "suggest_refactoring"
        assert r.category == ToolCategory.DEFERRED_MEDIUM
        assert r.rationale == "Refactoring workflow"

    def test_result_is_frozen(self) -> None:
        """ToolSearchResult instances are immutable."""
        r = ToolSearchResult(
            name="x",
            category=ToolCategory.DEFERRED_LOW,
            rationale="y",
        )
        with pytest.raises(ValidationError):
            r.name = "z"  # type: ignore[misc]


@pytest.mark.timeout(5)
class TestSearchDeferredTools:
    """Tests for search_deferred_tools()."""

    def test_empty_query_returns_empty(self) -> None:
        """Empty or whitespace-only query returns no matches."""
        assert search_deferred_tools("") == []
        assert search_deferred_tools("   ") == []

    def test_query_matches_name(self) -> None:
        """Query matching a tool name returns that tool."""
        results = search_deferred_tools("suggest_refactoring", limit=5)
        assert len(results) >= 1
        names = [r.name for r in results]
        assert "suggest_refactoring" in names

    def test_query_matches_rationale(self) -> None:
        """Query matching rationale text returns those tools."""
        results = search_deferred_tools("refactoring", limit=10)
        assert len(results) >= 1
        assert any("refactor" in r.rationale.lower() for r in results)

    def test_case_insensitive(self) -> None:
        """Search is case-insensitive."""
        lower = search_deferred_tools("REFACTOR", limit=5)
        mixed = search_deferred_tools("Refactor", limit=5)
        assert len(lower) >= 1 and len(mixed) >= 1
        assert {r.name for r in lower} == {r.name for r in mixed}

    def test_category_filter_medium(self) -> None:
        """Filtering by deferred_medium returns only medium tools."""
        results = search_deferred_tools("tool", category="deferred_medium", limit=50)
        assert all(r.category == ToolCategory.DEFERRED_MEDIUM for r in results)

    def test_category_filter_low(self) -> None:
        """Filtering by deferred_low returns only low tools."""
        results = search_deferred_tools("usage", category="deferred_low", limit=50)
        assert all(r.category == ToolCategory.DEFERRED_LOW for r in results)

    def test_limit_caps_results(self) -> None:
        """Limit parameter caps the number of results."""
        results = search_deferred_tools("a", limit=3)
        assert len(results) <= 3

    def test_no_match_returns_empty(self) -> None:
        """Query that matches no tool returns empty list."""
        results = search_deferred_tools("xyznonexistent123", limit=10)
        assert results == []

    def test_special_regex_chars_escaped(self) -> None:
        """Query with regex special chars is escaped (literal match)."""
        # "(" is escaped so we don't match "refactoring" etc. by accident
        results = search_deferred_tools("(", limit=5)
        assert isinstance(results, list)

    def test_search_tools_is_always_loaded(self) -> None:
        """search_tools is catalogued as always_loaded for discovery."""
        cat = get_tool_category("search_tools")
        assert cat == ToolCategory.ALWAYS_LOADED

    def test_category_filter_with_empty_results(self) -> None:
        """Category filter works even when no matches found."""
        # Search for something that won't match, but with category filter
        results = search_deferred_tools(
            "xyznonexistent123", category="deferred_medium", limit=10
        )
        assert results == []

    def test_search_with_deferred_low_category_filter(self) -> None:
        """Search with deferred_low category filter returns only low-priority tools."""
        results = search_deferred_tools("usage", category="deferred_low", limit=10)
        assert all(r.category == ToolCategory.DEFERRED_LOW for r in results)
        assert len(results) > 0

    def test_limit_zero_returns_empty(self) -> None:
        """Limit of 0 returns empty list even if matches exist."""
        results = search_deferred_tools("tool", limit=0)
        assert results == []

    def test_limit_one_returns_single_result(self) -> None:
        """Limit of 1 returns at most one result."""
        results = search_deferred_tools("refactor", limit=1)
        assert len(results) <= 1
        if results:
            assert isinstance(results[0], ToolSearchResult)

    def test_re_compile_error_returns_empty(self) -> None:
        """If re.compile raises (e.g. invalid pattern), search returns empty list."""
        with patch(
            "cortex.tools.tool_categories.re.compile",
            side_effect=re.error("mock invalid pattern"),
        ):
            results = search_deferred_tools("valid_query", limit=5)
        assert results == []
