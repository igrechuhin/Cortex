"""Tests for script_promotion.script_integrator."""

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.script_integrator import script_integration_template


def _record(
    script_id: str = "sid-1",
    task_description: str = "Check formatting",
) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-16T10:00:00Z",
        task_description=task_description,
        script_path="check.py",
        script_content="print(1)",
    )


class TestScriptIntegrationTemplate:
    """Tests for script_integration_template."""

    def test_returns_path_and_content_tuple(self) -> None:
        """Returns (relative_path, content) for Synapse script."""
        record = _record(task_description="Check formatting")
        rel_path, content = script_integration_template(record)
        assert rel_path.startswith("scripts/")
        assert rel_path.endswith(".py")
        assert "def main()" in content or "main()" in content

    def test_path_includes_language_directory(self) -> None:
        """Path includes language directory (e.g. scripts/python/)."""
        record = _record(task_description="Format")
        rel_path, _ = script_integration_template(record, language="python")
        assert "scripts/python/" in rel_path

    def test_custom_script_name_used_when_provided(self) -> None:
        """Custom script_name is used as stem when provided."""
        record = _record(task_description="Format")
        rel_path, _ = script_integration_template(
            record, language="python", script_name="check_format"
        )
        assert "check_format.py" in rel_path
