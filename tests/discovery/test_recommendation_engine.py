"""Tests for cortex.discovery.recommendation_engine."""

import pytest

from cortex.discovery.recommendation_engine import recommend_tools_and_scripts


class TestRecommendToolsAndScripts:
    """Tests for recommend_tools_and_scripts."""

    @pytest.fixture
    def tool_names(self) -> list[str]:
        """Sample tool names."""
        return ["manage_file", "load_context", "execute_pre_commit_checks", "rules"]

    @pytest.fixture
    def script_names(self) -> list[str]:
        """Sample script names."""
        return ["format", "run_tests", "type_check"]

    def test_delegates_to_search(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Recommendations use same search as search_tools_and_scripts."""
        result = recommend_tools_and_scripts(
            "format Python files", tool_names, script_names
        )
        names = [r[0] for r in result]
        assert "format" in names

    def test_returns_list_of_tuples(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Returns list of (name, type, score)."""
        result = recommend_tools_and_scripts(
            "run pre-commit checks", tool_names, script_names
        )
        assert isinstance(result, list)
        for item in result:
            assert len(item) == 3
            assert isinstance(item[0], str)
            assert item[1] in ("tool", "script")
            assert isinstance(item[2], float)

    def test_respects_max_results(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Default max_results limits size."""
        result = recommend_tools_and_scripts(
            "file context commit format tests type",
            tool_names,
            script_names,
            max_results=2,
        )
        assert len(result) <= 2

    def test_respects_min_score(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """min_score filters low relevance."""
        result = recommend_tools_and_scripts(
            "format",
            tool_names,
            script_names,
            min_score=0.5,
        )
        for _name, _kind, score in result:
            assert score >= 0.5

    def test_empty_task_description(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Empty task description yields no recommendations (empty query)."""
        result = recommend_tools_and_scripts("", tool_names, script_names)
        assert result == []
