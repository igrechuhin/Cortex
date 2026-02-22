"""Tests for cortex.services.framework_adapters.stub_adapter."""

from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.services.framework_adapters.stub_adapter import (
    StubAdapter,
    StubAdapterLanguage,
)


class TestStubAdapterInServices:
    """Test StubAdapter from services package (public API)."""

    def test_run_tests_returns_test_result(self) -> None:
        """run_tests returns TestResult with not-implemented message."""
        adapter = StubAdapter(None, "other")
        result = adapter.run_tests()
        assert isinstance(result, TestResult)
        assert result.success is False
        assert result.tests_run == 0
        assert "not yet available" in result.output.lower()

    def test_fix_errors_returns_check_result(self) -> None:
        """fix_errors returns CheckResult with check_type fix_errors."""
        adapter = StubAdapter(None, StubAdapterLanguage.OTHER)
        result = adapter.fix_errors()
        assert isinstance(result, CheckResult)
        assert result.check_type == "fix_errors"
        assert result.success is False

    def test_format_code_returns_check_result(self) -> None:
        """format_code returns CheckResult with check_type format."""
        adapter = StubAdapter(None, StubAdapterLanguage.OTHER)
        result = adapter.format_code()
        assert isinstance(result, CheckResult)
        assert result.check_type == "format"
        assert result.success is False

    def test_type_check_returns_check_result(self) -> None:
        """type_check returns CheckResult with check_type type_check."""
        adapter = StubAdapter(None, StubAdapterLanguage.OTHER)
        result = adapter.type_check()
        assert isinstance(result, CheckResult)
        assert result.check_type == "type_check"
        assert result.success is False

    def test_lint_code_returns_check_result(self) -> None:
        """lint_code returns CheckResult with check_type lint."""
        adapter = StubAdapter(None, StubAdapterLanguage.OTHER)
        result = adapter.lint_code()
        assert isinstance(result, CheckResult)
        assert result.check_type == "lint"
        assert result.success is False
