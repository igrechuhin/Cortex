"""Tests for cortex.services.models."""

import pytest

from cortex.services.models import (
    CheckResultModel,
    LanguageInfoModel,
    TestResultModel,
)


class TestServiceBaseModel:
    """Test ServiceBaseModel strict validation."""

    def test_extra_forbid_rejects_unknown_fields(self) -> None:
        """Model rejects unknown fields (extra='forbid')."""
        with pytest.raises(ValueError):
            _ = TestResultModel.model_validate(
                {
                    "success": True,
                    "tests_run": 1,
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "pass_rate": 1.0,
                    "output": "ok",
                    "unknown": "x",
                }
            )


class TestLanguageInfoModel:
    """Test LanguageInfoModel validation and bounds."""

    def test_minimal_valid_instance(self) -> None:
        """Language and confidence required; optional fields default to None."""
        m = LanguageInfoModel(
            language="python",
            confidence=0.9,
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
        )
        assert m.language == "python"
        assert m.confidence == 0.9
        assert m.test_framework is None
        assert m.formatter is None
        assert m.linter is None
        assert m.type_checker is None
        assert m.build_tool is None

    def test_confidence_bounds(self) -> None:
        """Confidence must be in [0, 1]."""
        _ = LanguageInfoModel(
            language="go",
            confidence=0.0,
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
        )
        _ = LanguageInfoModel(
            language="go",
            confidence=1.0,
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
        )
        with pytest.raises(ValueError):
            _ = LanguageInfoModel(
                language="go",
                confidence=-0.1,
                test_framework=None,
                formatter=None,
                linter=None,
                type_checker=None,
                build_tool=None,
            )
        with pytest.raises(ValueError):
            _ = LanguageInfoModel(
                language="go",
                confidence=1.1,
                test_framework=None,
                formatter=None,
                linter=None,
                type_checker=None,
                build_tool=None,
            )

    def test_full_instance_and_dict_like(self) -> None:
        """Full fields and dict-like access (DictLikeModel)."""
        m = LanguageInfoModel(
            language="python",
            test_framework="pytest",
            formatter="black",
            linter="ruff",
            type_checker="pyright",
            build_tool=None,
            confidence=0.95,
        )
        assert m["language"] == "python"
        assert m["test_framework"] == "pytest"
        assert m.get("build_tool") is None
        assert "language" in m


class TestCheckResultModel:
    """Test CheckResultModel validation and defaults."""

    def test_minimal_valid_instance(self) -> None:
        """Required: check_type, success, output; lists default to empty."""
        m = CheckResultModel(
            check_type="format",
            success=True,
            output="done",
        )
        assert m.check_type == "format"
        assert m.success is True
        assert m.output == "done"
        assert m.errors == []
        assert m.warnings == []
        assert m.files_modified == []

    def test_with_errors_and_files_modified(self) -> None:
        """Errors and files_modified can be set."""
        m = CheckResultModel(
            check_type="lint",
            success=False,
            output="ruff failed",
            errors=["E501 line too long"],
            files_modified=["src/foo.py"],
        )
        assert m.errors == ["E501 line too long"]
        assert m.files_modified == ["src/foo.py"]


class TestTestResultModel:
    """Test TestResultModel validation and bounds."""

    def test_minimal_valid_instance(self) -> None:
        """All numeric and output fields required; coverage optional."""
        m = TestResultModel(
            success=True,
            tests_run=10,
            tests_passed=10,
            tests_failed=0,
            pass_rate=1.0,
            coverage=None,
            output="passed",
        )
        assert m.success is True
        assert m.tests_run == 10
        assert m.coverage is None
        assert m.errors == []

    def test_coverage_bounds_when_provided(self) -> None:
        """Coverage when set must be in [0, 1]."""
        m = TestResultModel(
            success=True,
            tests_run=5,
            tests_passed=5,
            tests_failed=0,
            pass_rate=1.0,
            coverage=0.92,
            output="ok",
        )
        assert m.coverage == 0.92
        with pytest.raises(ValueError):
            _ = TestResultModel(
                success=True,
                tests_run=5,
                tests_passed=5,
                tests_failed=0,
                pass_rate=1.0,
                coverage=1.5,
                output="ok",
            )
        with pytest.raises(ValueError):
            _ = TestResultModel(
                success=True,
                tests_run=5,
                tests_passed=5,
                tests_failed=0,
                pass_rate=1.0,
                coverage=-0.1,
                output="ok",
            )

    def test_tests_run_ge_zero(self) -> None:
        """tests_run must be >= 0."""
        with pytest.raises(ValueError):
            _ = TestResultModel(
                success=True,
                tests_run=-1,
                tests_passed=0,
                tests_failed=0,
                pass_rate=0.0,
                coverage=None,
                output="",
            )

    def test_pass_rate_bounds(self) -> None:
        """pass_rate must be in [0, 1]."""
        _ = TestResultModel(
            success=True,
            tests_run=1,
            tests_passed=1,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output="",
        )
        _ = TestResultModel(
            success=True,
            tests_run=1,
            tests_passed=1,
            tests_failed=0,
            pass_rate=1.0,
            coverage=None,
            output="",
        )
        with pytest.raises(ValueError):
            _ = TestResultModel(
                success=True,
                tests_run=1,
                tests_passed=1,
                tests_failed=0,
                pass_rate=1.1,
                coverage=None,
                output="",
            )
