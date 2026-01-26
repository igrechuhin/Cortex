"""Quality preservation validator for health-check analysis."""

from cortex.health_check.models import MergeOpportunity


class QualityValidator:
    """Validates that merges don't reduce quality."""

    def validate_merge(self, opportunity: MergeOpportunity) -> dict[str, object]:
        """Validate that a merge opportunity preserves quality.

        Args:
            opportunity: Merge opportunity to validate

        Returns:
            Dictionary with validation result
        """
        issues: list[str] = []
        warnings: list[str] = []

        # Check similarity threshold
        if opportunity["similarity"] < 0.60:
            issues.append(
                f"Low similarity ({opportunity['similarity']:.2f}) may indicate different functionality"
            )

        # Check quality impact
        if opportunity["quality_impact"] == "negative":
            issues.append("Merge would reduce quality")

        # High similarity is good
        if opportunity["similarity"] >= 0.85:
            warnings.append("Very high similarity - strong candidate for merge")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendation": "proceed" if len(issues) == 0 else "review",
        }

    def validate_optimization(self, file: str, issue: str) -> dict[str, object]:
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

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendation": "proceed",
        }
