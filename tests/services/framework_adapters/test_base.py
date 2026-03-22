"""Tests for cortex.services.framework_adapters.base."""

import tempfile
from pathlib import Path

from cortex.services.framework_adapters.base import (
    COVERAGE_ACCEPT_MIN,
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.framework_adapters.stub_adapter import StubAdapter


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
    """Test FrameworkAdapter base behavior via StubAdapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter converts project_root to Path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter: FrameworkAdapter = StubAdapter(tmpdir, "other")
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root_uses_cwd(self) -> None:
        """Adapter uses cwd when project_root is None."""
        adapter = StubAdapter(None, "other")
        assert adapter.project_root == Path.cwd()

    def test_detect_default_returns_none(self) -> None:
        """FrameworkAdapter.detect() default returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            result = StubAdapter.detect(path)
            assert result is None
