"""Tests for cortex.script_promotion.script_integrator."""

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.script_integrator import script_integration_template


def _make_record(
    task_description: str = "Run tests",
    script_id: str = "sid-1",
    script_path: str = "scripts/run_tests.py",
) -> ScriptCaptureRecord:
    """Minimal ScriptCaptureRecord for integrator tests."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-01T00:00:00Z",
        task_description=task_description,
        script_path=script_path,
        script_content="def main(): pass",
    )


class TestScriptIntegrationTemplate:
    """Tests for script_integration_template."""

    def test_returns_path_and_content(self) -> None:
        """Returns (relative_path, content) tuple."""
        record = _make_record(task_description="Check formatting")
        path, content = script_integration_template(record)
        assert path == "scripts/python/check_formatting.py"
        assert "def main()" in content
        assert "sys.exit(main())" in content

    def test_custom_script_name_used(self) -> None:
        """When script_name is provided, it is used as stem."""
        record = _make_record()
        path, _ = script_integration_template(
            record,
            language="python",
            script_name="my_script",
        )
        assert path == "scripts/python/my_script.py"

    def test_language_in_path(self) -> None:
        """Language appears in path."""
        record = _make_record()
        path, _ = script_integration_template(record, language="shell")
        assert path.startswith("scripts/shell/")

    def test_stem_derived_from_task_when_no_name(self) -> None:
        """Stem is derived from task words when script_name not given."""
        record = _make_record(task_description="Run the unit tests now")
        path, _ = script_integration_template(record)
        assert "run_the_unit" in path or "run_the_unit_tests" in path

    def test_empty_task_uses_default_stem(self) -> None:
        """Empty task yields session_script stem."""
        record = _make_record(task_description="")
        path, _ = script_integration_template(record)
        assert path == "scripts/python/session_script.py"
