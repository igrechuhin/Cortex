"""Tests for cortex.script_promotion.models."""

import pytest

from cortex.script_promotion.models import ValidationResult


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_minimal_passed(self) -> None:
        """Passed result with default quality_score and empty issues."""
        r = ValidationResult(passed=True)
        assert r.passed is True
        assert r.quality_score == 0.0
        assert r.issues == []

    def test_failed_with_issues(self) -> None:
        """Failed result with issues list."""
        r = ValidationResult(
            passed=False,
            quality_score=0.4,
            issues=["Script content too short", "Missing task description"],
        )
        assert r.passed is False
        assert r.quality_score == 0.4
        assert len(r.issues) == 2
        assert "Script content too short" in r.issues
        assert "Missing task description" in r.issues

    def test_quality_score_bounds(self) -> None:
        """quality_score must be in [0, 1]."""
        _ = ValidationResult(passed=True, quality_score=0.0)
        _ = ValidationResult(passed=True, quality_score=1.0)
        _ = ValidationResult(passed=True, quality_score=0.5)
        with pytest.raises(ValueError):
            _ = ValidationResult(passed=True, quality_score=-0.1)
        with pytest.raises(ValueError):
            _ = ValidationResult(passed=True, quality_score=1.1)
