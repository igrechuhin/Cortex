"""Tests for discovery.recommendation_engine."""

from cortex.discovery.recommendation_engine import recommend_tools_and_scripts


class TestRecommendToolsAndScripts:
    """Tests for recommend_tools_and_scripts."""

    def test_returns_list_of_name_type_score(self) -> None:
        """Returns list of (name, type, score) for task description."""
        result = recommend_tools_and_scripts(
            task_description="Format Python files with Black",
            tool_names=["manage_file", "fix_formatting", "execute_pre_commit_checks"],
            script_names=["check_format", "fix_formatting"],
            min_score=0.2,
            max_results=10,
        )
        assert isinstance(result, list)
        for name, typ, score in result:
            assert isinstance(name, str)
            assert typ in ("tool", "script")
            assert 0 <= score <= 1

    def test_format_task_returns_format_recommendations(self) -> None:
        """Task about formatting returns format-related tools/scripts."""
        result = recommend_tools_and_scripts(
            task_description="format Python code",
            tool_names=["manage_file", "fix_formatting"],
            script_names=["check_format", "fix_formatting"],
            min_score=0.2,
        )
        names = [r[0] for r in result]
        assert "fix_formatting" in names or "check_format" in names
