"""Tests for discovery.use_case_mapper."""

from cortex.discovery.use_case_mapper import map_use_case_to_tools_and_scripts
from cortex.script_analysis.models import UseCaseExtraction


class TestMapUseCaseToToolsAndScripts:
    """Tests for map_use_case_to_tools_and_scripts."""

    def test_returns_tool_and_script_matches(self) -> None:
        """Returns (tool_matches, script_matches) with (name, type, score)."""
        use_case = UseCaseExtraction(
            use_case_label="format Python files",
            keywords=["black", "format"],
        )
        tool_names = ["manage_file", "fix_formatting", "execute_pre_commit_checks"]
        script_names = ["check_format", "fix_formatting"]
        tool_matches, script_matches = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names, min_score=0.2
        )
        assert isinstance(tool_matches, list)
        assert isinstance(script_matches, list)
        for name, typ, score in tool_matches + script_matches:
            assert isinstance(name, str)
            assert typ in ("tool", "script")
            assert 0 <= score <= 1

    def test_format_use_case_matches_format_tools(self) -> None:
        """Use case 'format' matches tools/scripts with 'format' in name."""
        use_case = UseCaseExtraction(
            use_case_label="format code",
            keywords=["format"],
        )
        tool_names = ["manage_file", "fix_formatting"]
        script_names = ["check_format", "run_tests"]
        tool_matches, script_matches = map_use_case_to_tools_and_scripts(
            use_case, tool_names, script_names, min_score=0.2
        )
        names = [m[0] for m in tool_matches] + [m[0] for m in script_matches]
        assert "fix_formatting" in names or "check_format" in names
