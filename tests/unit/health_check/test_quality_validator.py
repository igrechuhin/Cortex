"""Tests for quality validator."""

from typing import cast

from cortex.health_check.models import MergeOpportunity
from cortex.health_check.quality_validator import QualityValidator


class TestQualityValidator:
    """Test quality validator functionality."""

    def test_validate_merge_high_similarity(self):
        """Test merge validation with high similarity."""
        validator = QualityValidator()
        opportunity: MergeOpportunity = {
            "files": ["file1.md", "file2.md"],
            "similarity": 0.90,
            "merge_suggestion": "Merge files",
            "quality_impact": "positive",
            "estimated_savings": "10% reduction",
        }
        result = validator.validate_merge(opportunity)
        assert result["valid"] is True
        issues = cast(list[str], result["issues"])
        assert len(issues) == 0

    def test_validate_merge_low_similarity(self):
        """Test merge validation with low similarity."""
        validator = QualityValidator()
        opportunity: MergeOpportunity = {
            "files": ["file1.md", "file2.md"],
            "similarity": 0.50,
            "merge_suggestion": "Merge files",
            "quality_impact": "positive",
            "estimated_savings": "50% reduction",
        }
        result = validator.validate_merge(opportunity)
        assert result["valid"] is False
        issues = cast(list[str], result["issues"])
        assert len(issues) > 0

    def test_validate_merge_negative_impact(self):
        """Test merge validation with negative quality impact."""
        validator = QualityValidator()
        opportunity: MergeOpportunity = {
            "files": ["file1.md", "file2.md"],
            "similarity": 0.80,
            "merge_suggestion": "Merge files",
            "quality_impact": "negative",
            "estimated_savings": "20% reduction",
        }
        result = validator.validate_merge(opportunity)
        assert result["valid"] is False
        issues = cast(list[str], result["issues"])
        assert len(issues) > 0

    def test_validate_optimization_duplicate(self):
        """Test optimization validation for duplicate issue."""
        validator = QualityValidator()
        result = validator.validate_optimization(
            "file.md", "Duplicate sections detected"
        )
        assert result["valid"] is True
        warnings = cast(list[str], result["warnings"])
        assert len(warnings) > 0

    def test_validate_optimization_split(self):
        """Test optimization validation for split issue."""
        validator = QualityValidator()
        result = validator.validate_optimization(
            "file.md", "Very large file, consider splitting"
        )
        assert result["valid"] is True
        warnings = cast(list[str], result["warnings"])
        assert len(warnings) > 0
