"""Tests for cortex.discovery.use_case_mapper."""

import pytest

from cortex.discovery.use_case_mapper import map_use_case_to_tools_and_scripts
from cortex.script_analysis.models import UseCaseExtraction


class TestMapUseCaseToToolsAndScripts:
    """Tests for map_use_case_to_tools_and_scripts."""

    @pytest.fixture
    def tool_names(self) -> list[str]:
        """Sample tool names."""
        return ["manage_file", "load_context", "execute_pre_commit_checks"]

    @pytest.fixture
    def script_names(self) -> list[str]:
        """Sample script names."""
        return ["format", "run_tests"]

    def test_returns_two_lists(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Returns (tool_matches, script_matches)."""
        use_case = UseCaseExtraction(use_case_label="format code", keywords=[])
        tools, scripts = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names
        )
        assert isinstance(tools, list)
        assert isinstance(scripts, list)

    def test_match_tuple_format(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Each match is (name, type, score) with type 'tool' or 'script'."""
        use_case = UseCaseExtraction(
            use_case_label="format python files", keywords=["format", "python"]
        )
        tool_matches, script_matches = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names
        )
        for name, kind, score in tool_matches:
            assert isinstance(name, str)
            assert kind == "tool"
            assert isinstance(score, float)
            assert 0 <= score <= 1
        for _name, kind, _score in script_matches:
            assert kind == "script"

    def test_min_score_filters(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Matches below min_score are excluded."""
        use_case = UseCaseExtraction(use_case_label="xyz", keywords=["xyz"])
        tool_matches, script_matches = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names, min_score=0.99
        )
        for _n, _k, s in tool_matches + script_matches:
            assert s >= 0.99

    def test_tool_matches_sorted_by_score_desc(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Tool matches sorted by score descending."""
        use_case = UseCaseExtraction(
            use_case_label="file management", keywords=["file", "manage"]
        )
        tool_matches, _ = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names
        )
        if len(tool_matches) >= 2:
            scores = [m[2] for m in tool_matches]
            assert scores == sorted(scores, reverse=True)

    def test_script_matches_sorted_by_score_desc(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Script matches sorted by score descending."""
        use_case = UseCaseExtraction(
            use_case_label="run tests", keywords=["run", "tests"]
        )
        _, script_matches = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names
        )
        if len(script_matches) >= 2:
            scores = [m[2] for m in script_matches]
            assert scores == sorted(scores, reverse=True)

    def test_keywords_affect_scoring(
        self, tool_names: list[str], script_names: list[str]
    ) -> None:
        """Keywords are used in overlap scoring."""
        use_case = UseCaseExtraction(
            use_case_label="pre commit", keywords=["pre", "commit", "check"]
        )
        tool_matches, _ = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names
        )
        names = [m[0] for m in tool_matches]
        assert "execute_pre_commit_checks" in names

    def test_empty_tool_and_script_lists(self) -> None:
        """Empty inputs yield empty matches."""
        use_case = UseCaseExtraction(use_case_label="anything", keywords=[])
        tools, scripts = map_use_case_to_tools_and_scripts(use_case, [], [])
        assert tools == []
        assert scripts == []
