"""Tests for cortex.services.framework_adapters.base."""

import tempfile
from collections.abc import Sequence
from pathlib import Path

from cortex.services.framework_adapters.base import (
    COVERAGE_ACCEPT_MIN,
    CheckResult,
    FrameworkAdapter,
    ProgressCallback,
    TestResult,
)


class _MinimalAdapter(FrameworkAdapter):
    """Concrete adapter implementing only the base-class contract, for testing
    ``FrameworkAdapter`` itself rather than any language-specific behavior."""

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        return TestResult(
            success=True,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=1.0,
            coverage=None,
            output="",
            errors=[],
        )

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        return CheckResult(check_type="fix_errors", success=True, output="")

    def format_code(self) -> CheckResult:
        return CheckResult(check_type="format", success=True, output="")

    def type_check(self) -> CheckResult:
        return CheckResult(check_type="type_check", success=True, output="")

    def lint_code(self) -> CheckResult:
        return CheckResult(check_type="lint", success=True, output="")


class TestCheckResult:
    """Test CheckResult model."""

    def test_minimal_valid_instance(self) -> None:
        """Required: check_type, success, output; lists default to empty."""
        r = CheckResult(check_type="format", success=True, output="done")
        assert r.check_type == "format"
        assert r.success is True
        assert r.output == "done"
        assert r.errors == []
        assert r.warnings == []
        assert r.files_modified == []

    def test_dict_like_access(self) -> None:
        """CheckResult is DictLikeModel; supports get and []."""
        r = CheckResult(
            check_type="lint",
            success=False,
            output="failed",
            errors=["E501"],
        )
        assert r["check_type"] == "lint"
        assert r.get("errors") == ["E501"]


class TestTestResult:
    """Test TestResult model."""

    def test_required_fields(self) -> None:
        """output and errors are required; coverage optional via type."""
        r = TestResult(
            success=True,
            tests_run=5,
            tests_passed=5,
            tests_failed=0,
            pass_rate=1.0,
            coverage=None,
            output="ok",
            errors=[],
        )
        assert r.success is True
        assert r.tests_run == 5
        assert r.output == "ok"
        assert r.errors == []
        assert r.warnings == []
        assert r["skipped_tests"] == 0

    def test_with_warnings(self) -> None:
        """warnings default to empty but can be set."""
        r = TestResult(
            success=True,
            tests_run=10,
            tests_passed=10,
            tests_failed=0,
            pass_rate=1.0,
            coverage=0.895,
            output="ok",
            errors=[],
            warnings=["Coverage below 90%"],
        )
        assert r.warnings == ["Coverage below 90%"]


class TestCOVERAGE_ACCEPT_MIN:
    """Test coverage constant."""

    def test_value(self) -> None:
        """COVERAGE_ACCEPT_MIN is 89.5% for accept-with-warning."""
        assert COVERAGE_ACCEPT_MIN == 0.895


class TestFrameworkAdapter:
    """Test FrameworkAdapter base behavior via a minimal concrete adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter converts project_root to Path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter: FrameworkAdapter = _MinimalAdapter(tmpdir)
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root_uses_cwd(self) -> None:
        """Adapter uses cwd when project_root is None."""
        adapter = _MinimalAdapter(None)
        assert adapter.project_root == Path.cwd()

    def test_detect_default_returns_none(self) -> None:
        """FrameworkAdapter.detect() default returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            result = _MinimalAdapter.detect(path)
            assert result is None
