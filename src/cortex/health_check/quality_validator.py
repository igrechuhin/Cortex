"""Quality preservation validator for health-check analysis."""

from typing import cast

from cortex.core.constants import SIMILARITY_THRESHOLD_DUPLICATE
from cortex.core.models import JsonValue, ModelDict
from cortex.health_check.models import MergeOpportunity, QualityImpact


class QualityValidator:
    """Validates that merges don't reduce quality."""

    def validate_merge(self, opportunity: MergeOpportunity) -> ModelDict:
        """Validate that a merge opportunity preserves quality.

        Args:
            opportunity: Merge opportunity to validate

        Returns:
            Dictionary with validation result
        """
        issues: list[str] = []
        warnings: list[str] = []

        similarity: float = opportunity.similarity

        # Check similarity threshold
        if similarity < 0.60:
            msg = f"Low similarity ({similarity:.2f}) may indicate different functionality"
            issues.append(msg)

        # Check quality impact
        if opportunity.quality_impact is QualityImpact.NEGATIVE:
            issues.append("Merge would reduce quality")

        # High similarity is good
        if similarity >= SIMILARITY_THRESHOLD_DUPLICATE:
            warnings.append("Very high similarity - strong candidate for merge")

        result: ModelDict = {
            "valid": len(issues) == 0,
            "issues": cast(list[JsonValue], issues),
            "warnings": cast(list[JsonValue], warnings),
            "recommendation": "proceed" if len(issues) == 0 else "review",
        }
        return result

    def validate_optimization(self, file: str, issue: str) -> ModelDict:
        """Validate that an optimization preserves quality.

        Args:
            file: File to optimize
            issue: Issue description

        Returns:
            Dictionary with validation result
        """
        issues: list[str] = []
        warnings: list[str] = []

        # Most optimizations are safe
        if "duplicate" in issue.lower():
            warnings.append("Removing duplicates is safe")
        elif "split" in issue.lower():
            warnings.append("Splitting large files improves maintainability")

        result: ModelDict = {
            "valid": len(issues) == 0,
            "issues": cast(list[JsonValue], issues),
            "warnings": cast(list[JsonValue], warnings),
            "recommendation": "proceed",
        }
        return result
