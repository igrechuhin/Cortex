"""Tests for discovery.search_interface."""

from cortex.discovery.search_interface import search_tools_and_scripts


class TestSearchToolsAndScripts:
    """Tests for search_tools_and_scripts."""

    def test_returns_list_of_name_type_score(self) -> None:
        """Returns list of (name, type, score) sorted by score."""
        result = search_tools_and_scripts(
            query="format python",
            tool_names=["manage_file", "fix_formatting"],
            script_names=["check_format", "run_tests"],
            min_score=0.1,
        )
        assert isinstance(result, list)
        for name, typ, score in result:
            assert isinstance(name, str)
            assert typ in ("tool", "script")
            assert 0 <= score <= 1
        if len(result) >= 2:
            assert result[0][2] >= result[1][2]

    def test_format_query_matches_format_tools(self) -> None:
        """Query 'format' returns tools/scripts with 'format' in name."""
        result = search_tools_and_scripts(
            query="format",
            tool_names=["manage_file", "fix_formatting"],
            script_names=["check_format"],
            min_score=0.2,
        )
        names = [r[0] for r in result]
        assert "fix_formatting" in names or "check_format" in names

    def test_respects_max_results(self) -> None:
        """Result length does not exceed max_results."""
        result = search_tools_and_scripts(
            query="check",
            tool_names=["check_format", "check_linting", "check_types"],
            script_names=["check_format", "check_linting"],
            min_score=0.1,
            max_results=2,
        )
        assert len(result) <= 2
