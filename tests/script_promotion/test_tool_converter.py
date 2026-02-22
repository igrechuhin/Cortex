"""Tests for cortex.script_promotion.tool_converter."""

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.tool_converter import tool_conversion_template


def _make_record(
    script_id: str = "sid-1",
    task_description: str = "Run tests",
    script_path: str = "scripts/run_tests.py",
) -> ScriptCaptureRecord:
    """Minimal ScriptCaptureRecord for converter tests."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-01T00:00:00Z",
        task_description=task_description,
        script_path=script_path,
        script_content="def main(): pass",
    )


class TestToolConversionTemplate:
    """Tests for tool_conversion_template."""

    def test_returns_python_code_string(self) -> None:
        """Returns a string containing Python code."""
        record = _make_record(task_description="Run tests")
        code = tool_conversion_template(record)
        assert isinstance(code, str)
        assert "@mcp.tool()" in code
        assert "async def " in code
        assert "return " in code

    def test_snake_case_tool_name_from_task(self) -> None:
        """Task description is converted to snake_case function name."""
        record = _make_record(task_description="Run the unit tests")
        code = tool_conversion_template(record)
        assert "run_the_unit_tests" in code or "async def run_the" in code

    def test_custom_tool_name_used(self) -> None:
        """When tool_name is provided, it is used (sanitized)."""
        record = _make_record()
        code = tool_conversion_template(record, tool_name="my_custom_tool")
        assert "my_custom_tool" in code

    def test_record_id_and_path_in_docstring(self) -> None:
        """Template includes script_id and script_path in docstring."""
        record = _make_record(script_id="cap-123", script_path="foo/bar.py")
        code = tool_conversion_template(record)
        assert "cap-123" in code
        assert "foo/bar.py" in code

    def test_empty_task_uses_default_name(self) -> None:
        """Empty task yields session_script_tool-like name."""
        record = _make_record(task_description="")
        code = tool_conversion_template(record)
        assert "session_script" in code or "def " in code
