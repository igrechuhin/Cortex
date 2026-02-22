"""Tests for cortex.discovery.search_interface."""

import pytest

from cortex.discovery.search_interface import search_tools_and_scripts


class TestSearchToolsAndScripts:
    """Tests for search_tools_and_scripts."""

    @pytest.fixture
    def tool_names(self) -> list[str]:
        """Sample tool names for tests."""
        return ["manage_file", "load_context", "execute_pre_commit_checks", "rules"]

    @pytest.fixture
    def script_names(self) -> list[str]:
        """Sample script names for tests."""
        return ["format", "run_tests", "type_check"]

    def test_empty_query_returns_empty(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Empty or whitespace-only query returns []."""
        assert search_tools_and_scripts("", tool_names, script_names) == []
        assert search_tools_and_scripts("   ", tool_names, script_names) == []

    def test_single_char_tokens_ignored(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Query tokens shorter than 2 chars are ignored; can yield []."""
        result = search_tools_and_scripts("a b c", tool_names, script_names)
        # No token has length >= 2, so q_tokens is empty -> []
        assert result == []

    def test_exact_match_scores_high(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Query matching a name returns that name with high score."""
        result = search_tools_and_scripts("manage_file", tool_names, script_names)
        assert len(result) >= 1
        name, kind, score = result[0]
        assert name == "manage_file"
        assert kind == "tool"
        assert score >= 0.2

    def test_partial_match_included(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Query 'load' matches load_context."""
        result = search_tools_and_scripts("load", tool_names, script_names)
        names = [r[0] for r in result]
        assert "load_context" in names

    def test_results_sorted_by_score_descending(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Results are sorted by score descending."""
        result = search_tools_and_scripts(
            "execute pre commit checks", tool_names, script_names
        )
        if len(result) >= 2:
            scores = [r[2] for r in result]
            assert scores == sorted(scores, reverse=True)

    def test_respects_max_results(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """At most max_results items returned."""
        result = search_tools_and_scripts(
            "file context commit rules format tests",
            tool_names,
            script_names,
            max_results=3,
        )
        assert len(result) <= 3

    def test_min_score_filters_low_matches(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Results below min_score are excluded."""
        result = search_tools_and_scripts(
            "manage file",
            tool_names,
            script_names,
            min_score=0.9,
        )
        for _name, _kind, score in result:
            assert score >= 0.9

    def test_returns_tuples_name_type_score(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Each result is (name, type, score) with type 'tool' or 'script'."""
        result = search_tools_and_scripts("format", tool_names, script_names)
        assert len(result) >= 1
        name, kind, score = result[0]
        assert isinstance(name, str)
        assert kind in ("tool", "script")
        assert isinstance(score, float)
        assert 0 <= score <= 1

    def test_script_names_searched(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Script names appear in results when query matches."""
        result = search_tools_and_scripts("run tests", tool_names, script_names)
        names = [r[0] for r in result]
        assert "run_tests" in names or any("test" in n for n in names)
