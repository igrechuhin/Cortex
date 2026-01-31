"""Tests for StubAdapter."""

from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.services.framework_adapters.stub_adapter import (
    StubAdapter,
    StubAdapterLanguage,
)


class TestStubAdapter:
    """Test StubAdapter for non-Python languages."""

    def test_run_tests_returns_not_implemented(self) -> None:
        """run_tests returns TestResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.run_tests()
        assert isinstance(result, TestResult)
        assert result.success is False
        assert result.tests_run == 0
        assert "other" in result.output
        assert "not yet available" in result.output.lower()
        assert len(result.errors) == 1

    def test_fix_errors_returns_not_implemented(self) -> None:
        """fix_errors returns CheckResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.fix_errors()
        assert isinstance(result, CheckResult)
        assert result.check_type == "fix_errors"
        assert result.success is False
        assert "other" in result.output
        assert result.files_modified == []

    def test_format_code_returns_not_implemented(self) -> None:
        """format_code returns CheckResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.format_code()
        assert isinstance(result, CheckResult)
        assert result.check_type == "format"
        assert result.success is False
        assert "other" in result.output

    def test_type_check_returns_not_implemented(self) -> None:
        """type_check returns CheckResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.type_check()
        assert isinstance(result, CheckResult)
        assert result.check_type == "type_check"
        assert result.success is False
        assert "other" in result.output

    def test_lint_code_returns_not_implemented(self) -> None:
        """lint_code returns CheckResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.lint_code()
        assert isinstance(result, CheckResult)
        assert result.check_type == "lint"
        assert result.success is False
        assert "other" in result.output

    def test_adapter_accepts_project_root(self) -> None:
        """StubAdapter accepts StubAdapterLanguage enum for language."""
        adapter = StubAdapter(None, StubAdapterLanguage.OTHER)
        result = adapter.format_code()
        assert result.success is False
        assert "other" in result.output
        run_result = adapter.run_tests()
        assert "other" in run_result.output

    def test_init_with_project_root(self) -> None:
        """StubAdapter accepts project_root and uses it."""
        adapter = StubAdapter("/some/root", "other")
        assert adapter.project_root is not None
        assert "some" in str(adapter.project_root) and "root" in str(
            adapter.project_root
        )
