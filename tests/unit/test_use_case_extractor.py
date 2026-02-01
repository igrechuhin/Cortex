"""Tests for use_case_extractor."""

from cortex.script_analysis.use_case_extractor import extract_use_case
from cortex.script_detection.models import ScriptCaptureRecord


class TestExtractUseCase:
    """Tests for extract_use_case."""

    def test_extracts_label_from_task_description_with_format(self) -> None:
        """Use case label inferred from task_description containing 'format'."""
        record = ScriptCaptureRecord(
            script_id="id-1",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Format Python code in the repo",
            script_path="scripts/format.py",
            script_content="import black\nblack.format_file(...)",
        )
        result = extract_use_case(record)
        assert result.use_case_label == "format code"
        assert "format" in result.keywords or "python" in result.keywords

    def test_extracts_label_from_task_description_with_lint(self) -> None:
        """Use case label inferred from task_description containing 'lint'."""
        record = ScriptCaptureRecord(
            script_id="id-2",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Lint the codebase",
            script_path="lint.sh",
            script_content="ruff check .",
        )
        result = extract_use_case(record)
        assert result.use_case_label == "lint code"

    def test_extracts_label_from_task_description_with_test(self) -> None:
        """Use case label inferred from task_description containing 'test'."""
        record = ScriptCaptureRecord(
            script_id="id-3",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Run tests with pytest",
            script_path="run_tests.py",
            script_content="import pytest\npytest.main()",
        )
        result = extract_use_case(record)
        assert result.use_case_label == "run tests"

    def test_falls_back_to_custom_utility_when_no_keyword_match(self) -> None:
        """When no keyword matches, label is custom utility or from combined text."""
        record = ScriptCaptureRecord(
            script_id="id-4",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Custom one-off data migration",
            script_path="migrate.py",
            script_content="print('migrate')",
        )
        result = extract_use_case(record)
        assert result.use_case_label in ("custom utility", "migrate", "session script")
        assert len(result.keywords) >= 1

    def test_uses_usage_context_when_provided(self) -> None:
        """usage_context is included in text used for keywords."""
        record = ScriptCaptureRecord(
            script_id="id-5",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Check something",
            script_path="check.py",
            script_content="",
            usage_context="Validate config files",
        )
        result = extract_use_case(record)
        assert "validate" in result.use_case_label or "check" in result.keywords
