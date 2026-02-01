"""Tests for script_promotion.documentation_generator."""

from cortex.script_promotion.documentation_generator import (
    generate_script_doc,
    generate_tool_doc,
)


class TestGenerateToolDoc:
    """Tests for generate_tool_doc."""

    def test_returns_markdown_with_tool_name_and_description(self) -> None:
        """Generated doc contains tool name and description."""
        doc = generate_tool_doc(
            tool_name="format_python",
            description="Format Python files with Black.",
        )
        assert "## format_python" in doc
        assert "Format Python files with Black" in doc

    def test_includes_use_case_label_when_provided(self) -> None:
        """Use case label is included when provided."""
        doc = generate_tool_doc(
            tool_name="foo",
            description="Does foo.",
            use_case_label="format Python files",
        )
        assert "format Python files" in doc


class TestGenerateScriptDoc:
    """Tests for generate_script_doc."""

    def test_returns_markdown_with_path_and_description(self) -> None:
        """Generated doc contains script path and description."""
        doc = generate_script_doc(
            script_path="scripts/python/check_format.py",
            description="Check Python formatting.",
        )
        assert "scripts/python/check_format.py" in doc
        assert "Check Python formatting" in doc
        assert ".venv/bin/python" in doc
