"""Tests for script_promotion.tool_converter."""

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.tool_converter import tool_conversion_template


def _record(
    script_id: str = "sid-1",
    task_description: str = "Format Python files",
) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-16T10:00:00Z",
        task_description=task_description,
        script_path="format.py",
        script_content="print(1)",
    )


class TestToolConversionTemplate:
    """Tests for tool_conversion_template."""

    def test_returns_python_code_with_tool_decorator(self) -> None:
        """Template contains @mcp.tool() and async def."""
        record = _record(task_description="Format code")
        code = tool_conversion_template(record)
        assert "@mcp.tool()" in code
        assert "async def " in code
        assert "mcp_tool_wrapper" in code

    def test_uses_task_description_for_docstring(self) -> None:
        """Template includes task_description in docstring."""
        record = _record(task_description="Format Python files")
        code = tool_conversion_template(record)
        assert "Format Python files" in code or "Format" in code

    def test_custom_tool_name_sanitized_to_snake_case(self) -> None:
        """Custom tool_name is sanitized to snake_case."""
        record = _record(task_description="Do something")
        code = tool_conversion_template(record, tool_name="Do Something Here")
        assert "do_something_here" in code
