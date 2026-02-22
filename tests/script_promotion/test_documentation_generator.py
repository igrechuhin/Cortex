"""Tests for cortex.script_promotion.documentation_generator."""

from cortex.script_promotion.documentation_generator import (
    generate_script_doc,
    generate_tool_doc,
)


class TestGenerateToolDoc:
    """Tests for generate_tool_doc."""

    def test_minimal(self) -> None:
        """Tool doc with name and description only."""
        out = generate_tool_doc("my_tool", "Does something.")
        assert "## my_tool" in out
        assert "Does something." in out
        assert "my_tool(project_root (optional))" in out

    def test_with_use_case_label(self) -> None:
        """Use case label is included when provided."""
        out = generate_tool_doc(
            "run_tests",
            "Runs tests.",
            use_case_label="testing",
        )
        assert "**Use case**: testing" in out

    def test_with_example_args(self) -> None:
        """Custom example_args appear in example."""
        out = generate_tool_doc(
            "manage_file",
            "Manages files.",
            example_args="file_name, operation",
        )
        assert "manage_file(file_name, operation)" in out


class TestGenerateScriptDoc:
    """Tests for generate_script_doc."""

    def test_minimal(self) -> None:
        """Script doc with path and description."""
        out = generate_script_doc(
            "scripts/python/check_foo.py",
            "Checks foo.",
        )
        assert "## scripts/python/check_foo.py" in out
        assert "Checks foo." in out
        assert ".venv/bin/python" in out
        assert ".cortex/synapse/scripts/python/check_foo.py" in out

    def test_with_use_case_and_language(self) -> None:
        """Use case and language are reflected."""
        out = generate_script_doc(
            "scripts/python/run_tests.py",
            "Runs tests.",
            language="python",
            use_case_label="testing",
        )
        assert "**Use case**: testing" in out
        assert ".venv" in out
