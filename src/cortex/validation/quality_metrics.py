"""
Quality metrics calculation for Memory Bank.

This module calculates quality scores and health metrics for
Memory Bank files to assess overall data quality.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING, cast

from cortex.core.constants import (
    QUALITY_WEIGHT_COMPLETENESS,
    QUALITY_WEIGHT_CONSISTENCY,
    QUALITY_WEIGHT_EFFICIENCY,
    QUALITY_WEIGHT_FRESHNESS,
    QUALITY_WEIGHT_STRUCTURE,
)

from .schema_validator import SchemaValidator

if TYPE_CHECKING:
    from cortex.core.metadata_index import MetadataIndex


class QualityMetrics:
    """Calculate Memory Bank quality metrics."""

    def __init__(
        self,
        schema_validator: SchemaValidator,
        metadata_index: "MetadataIndex | None" = None,
    ):
        """
        Initialize with schema validator and optional metadata index.

        Args:
            schema_validator: SchemaValidator instance
            metadata_index: Optional MetadataIndex instance
        """
        self.schema_validator: SchemaValidator = schema_validator
        self.metadata_index: MetadataIndex | None = (
            metadata_index if metadata_index is not None else None
        )

    async def calculate_overall_score(
        self,
        files_content: dict[str, str],
        files_metadata: dict[str, dict[str, object]],
        duplication_data: dict[str, object],
        link_validation: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Calculate overall Memory Bank quality score.

        Args:
            files_content: Dict mapping file names to content
            files_metadata: Dict mapping file names to metadata
            duplication_data: Duplication scan results
            link_validation: Optional link validation results

        Returns:
            {
                "overall_score": 0-100,
                "breakdown": {...},
                "grade": "A/B/C/D/F",
                "status": "healthy/warning/critical",
                "issues": [...],
                "recommendations": [...]
            }
        """
        category_scores = await self._calculate_category_scores(
            files_content, files_metadata, duplication_data, link_validation
        )
        overall_score = self._calculate_weighted_score(category_scores)
        grade, status = self._determine_grade_and_status(overall_score)
        issues = self._collect_all_issues(category_scores, duplication_data)
        recommendations = self._generate_all_recommendations(category_scores, issues)

        return self._build_score_result(
            overall_score, category_scores, grade, status, issues, recommendations
        )

    async def calculate_file_score(
        self, file_name: str, content: str, metadata: dict[str, object]
    ) -> dict[str, object]:
        """
        Calculate quality score for individual file.

        Args:
            file_name: Name of file
            content: File content
            metadata: File metadata

        Returns:
            File quality score and details
        """
        # Validate against schema
        validation_result = await self.schema_validator.validate_file(
            file_name, content
        )

        # Calculate freshness for this file
        freshness = self.calculate_file_freshness(metadata)

        # Calculate structure score
        structure = self.calculate_file_structure(content)

        # Overall file score
        file_score = int(
            validation_result["score"] * 0.5 + freshness * 0.25 + structure * 0.25
        )

        return {
            "file_name": file_name,
            "score": file_score,
            "grade": self.get_grade(file_score),
            "validation": validation_result,
            "freshness": int(freshness),
            "structure": int(structure),
        }

    async def calculate_completeness(self, files_content: dict[str, str]) -> float:
        """
        Score based on required sections present across all files.

        Args:
            files_content: Dict mapping file names to content

        Returns:
            Completeness score 0-100
        """
        if not files_content:
            return 0.0

        total_score = 0
        for file_name, content in files_content.items():
            validation = await self.schema_validator.validate_file(file_name, content)
            total_score += validation["score"]

        return total_score / len(files_content)

    def calculate_consistency(
        self,
        duplication_data: dict[str, object],
        link_validation: dict[str, object] | None = None,
    ) -> float:
        """
        Score based on duplication and link integrity.

        Args:
            duplication_data: Duplication scan results
            link_validation: Optional link validation results

        Returns:
            Consistency score 0-100
        """
        score = 100.0

        # Deduct for duplications
        duplicates_found_raw = duplication_data.get("duplicates_found", 0)
        duplicates_found = (
            int(duplicates_found_raw)
            if isinstance(duplicates_found_raw, (int, float))
            else 0
        )
        score -= duplicates_found * 5  # 5 points per duplication

        # Deduct for broken links if provided
        if link_validation:
            broken_links = self._extract_broken_links(link_validation)
            score -= len(broken_links) * 3  # 3 points per broken link

        return max(0.0, score)

    def _extract_broken_links(self, link_validation: dict[str, object]) -> list[str]:
        """Extract broken links from validation data.

        Args:
            link_validation: Link validation results

        Returns:
            List of broken link strings
        """
        broken_links_raw: object = link_validation.get("broken_links", [])
        if not isinstance(broken_links_raw, list):
            return []

        broken_links: list[str] = []
        broken_links_list = cast(list[object], broken_links_raw)
        for item_obj in broken_links_list:
            if item_obj is not None:
                broken_links.append(str(item_obj))

        return broken_links

    def calculate_freshness(
        self, files_metadata: dict[str, dict[str, object]]
    ) -> float:
        """
        Score based on last modified times.

        Args:
            files_metadata: Dict mapping file names to metadata

        Returns:
            Freshness score 0-100
        """
        if not files_metadata:
            return 50.0

        now = datetime.now()
        scores: list[float] = []

        for metadata in files_metadata.values():
            score = self._calculate_file_freshness_score(metadata, now)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 50.0

    def _calculate_file_freshness_score(
        self, metadata: dict[str, object], now: datetime
    ) -> float:
        """Calculate freshness score for a single file."""
        last_modified_raw: object = metadata.get("last_modified")
        if not last_modified_raw:
            return 50.0

        try:
            last_modified_str = str(last_modified_raw)
            last_mod_dt = datetime.fromisoformat(
                last_modified_str.replace("Z", "+00:00")
            )
            days_old = (now - last_mod_dt).days
            return self._score_by_age(days_old)
        except Exception:
            return 50.0

    def _score_by_age(self, days_old: int) -> float:
        """Calculate freshness score based on age in days.

        Args:
            days_old: Number of days since last modification

        Returns:
            Freshness score 0-100
        """
        # Use early returns to reduce nesting
        if days_old <= 7:
            return 100.0
        if days_old <= 30:
            return 80.0
        if days_old <= 90:
            return 60.0
        if days_old <= 180:
            return 40.0
        return 20.0

    def calculate_file_freshness(self, metadata: dict[str, object]) -> float:
        """Calculate freshness for a single file.

        Reduced nesting: Extracted date parsing and scoring to helper methods.
        Nesting: 2 levels (down from 5 levels)
        """
        last_modified_raw: object = metadata.get("last_modified")
        if not last_modified_raw:
            return 50.0

        try:
            days_old = self._parse_last_modified_date(last_modified_raw)
            return self._score_by_age(days_old)
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to parse last_modified date: {e}")
            return 50.0

    def _parse_last_modified_date(self, last_modified_raw: object) -> int:
        """Parse last modified date and calculate days old.

        Args:
            last_modified_raw: Raw last modified timestamp

        Returns:
            Number of days since last modification
        """
        last_modified_str = str(last_modified_raw)
        last_mod_dt = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
        return (datetime.now() - last_mod_dt).days

    def calculate_structure(self, files_content: dict[str, str]) -> float:
        """
        Score based on heading hierarchy and organization.

        Args:
            files_content: Dict mapping file names to content

        Returns:
            Structure score 0-100
        """
        if not files_content:
            return 0.0

        scores: list[float] = []
        for content in files_content.values():
            scores.append(self.calculate_file_structure(content))

        return sum(scores) / len(scores)

    def calculate_file_structure(self, content: str) -> float:
        """Calculate structure score for a single file."""
        score = 100.0
        lines = content.split("\n")
        prev_level = 0

        for line in lines:
            match = re.match(r"^(#{1,})\s+(.+)$", line)
            if match:
                level = len(match.group(1))

                # Deduct for skipped levels
                if prev_level > 0 and level > prev_level + 1:
                    score -= 10

                # Deduct for very deep nesting (>4 levels)
                if level > 4:
                    score -= 5

                prev_level = level

        return max(0.0, score)

    def calculate_token_efficiency(
        self, files_metadata: dict[str, dict[str, object]]
    ) -> float:
        """
        Score based on token usage efficiency.

        Args:
            files_metadata: Dict mapping file names to metadata

        Returns:
            Token efficiency score 0-100
        """
        if not files_metadata:
            return 100.0

        total_tokens = 0
        for m in files_metadata.values():
            token_count_raw: object = m.get("token_count", 0)
            if isinstance(token_count_raw, (int, float)):
                total_tokens += int(token_count_raw)

        # Ideal range: 20k-80k tokens total
        # Too few: probably incomplete
        # Too many: probably bloated

        if 20000 <= total_tokens <= 80000:
            return 100.0
        elif total_tokens < 20000:
            # Penalize for being too sparse
            ratio = total_tokens / 20000
            return 50 + (ratio * 50)
        else:
            # Penalize for being too large
            excess = total_tokens - 80000
            penalty = min(50, (excess / 1000) * 2)
            return max(50.0, 100 - penalty)

    def get_grade(self, score: float) -> str:
        """
        Convert score to letter grade.

        Args:
            score: Score 0-100

        Returns:
            Letter grade A/B/C/D/F
        """
        # Use early returns to reduce nesting
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def get_status(self, score: float) -> str:
        """
        Get health status based on score.

        Args:
            score: Score 0-100

        Returns:
            Status string
        """
        if score >= 80:
            return "healthy"
        elif score >= 60:
            return "warning"
        else:
            return "critical"

    def collect_issues(
        self,
        completeness: float,
        consistency: float,
        freshness: float,
        structure: float,
        token_efficiency: float,
        duplication_data: dict[str, object],
    ) -> list[str]:
        """Collect issues based on scores."""
        issues: list[str] = []

        self._add_completeness_issue(issues, completeness)
        self._add_consistency_issue(issues, consistency, duplication_data)
        self._add_freshness_issue(issues, freshness)
        self._add_structure_issue(issues, structure)
        self._add_token_efficiency_issue(issues, token_efficiency)

        return issues

    def generate_recommendations(
        self,
        completeness: float,
        consistency: float,
        freshness: float,
        structure: float,
        token_efficiency: float,
        issues: list[str],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations: list[str] = []

        self._add_completeness_recommendation(recommendations, completeness)
        self._add_consistency_recommendation(recommendations, consistency)
        self._add_freshness_recommendation(recommendations, freshness)
        self._add_structure_recommendation(recommendations, structure)
        self._add_token_efficiency_recommendation(recommendations, token_efficiency)
        self._add_general_recommendation(recommendations, issues)

        return recommendations

    def _add_completeness_recommendation(
        self, recommendations: list[str], completeness: float
    ) -> None:
        """Add completeness recommendation if needed."""
        if completeness < 80:
            recommendations.append(
                "Run 'validate_memory_bank' to see which sections are missing"
            )

    def _add_consistency_recommendation(
        self, recommendations: list[str], consistency: float
    ) -> None:
        """Add consistency recommendation if needed."""
        if consistency < 80:
            recommendations.append(
                "Run 'check_duplications' to identify and refactor duplicate content"
            )

    def _add_freshness_recommendation(
        self, recommendations: list[str], freshness: float
    ) -> None:
        """Add freshness recommendation if needed."""
        if freshness < 60:
            recommendations.append(
                "Review and update stale files, especially activeContext.md and progress.md"
            )

    def _add_structure_recommendation(
        self, recommendations: list[str], structure: float
    ) -> None:
        """Add structure recommendation if needed."""
        if structure < 80:
            recommendations.append(
                "Fix heading hierarchy - avoid skipping levels (## -> ####)"
            )

    def _add_token_efficiency_recommendation(
        self, recommendations: list[str], token_efficiency: float
    ) -> None:
        """Add token efficiency recommendation if needed."""
        if token_efficiency < 70:
            recommendations.append(
                "Review token usage with 'check_token_budget' and consider summarizing verbose sections"
            )

    def _add_general_recommendation(
        self, recommendations: list[str], issues: list[str]
    ) -> None:
        """Add general recommendation if no issues."""
        if not issues:
            recommendations.append(
                "Memory Bank is in good shape! Keep maintaining regular updates."
            )

    async def _calculate_category_scores(
        self,
        files_content: dict[str, str],
        files_metadata: dict[str, dict[str, object]],
        duplication_data: dict[str, object],
        link_validation: dict[str, object] | None,
    ) -> dict[str, float]:
        """Calculate all individual category scores."""
        return {
            "completeness": await self.calculate_completeness(files_content),
            "consistency": self.calculate_consistency(
                duplication_data, link_validation
            ),
            "freshness": self.calculate_freshness(files_metadata),
            "structure": self.calculate_structure(files_content),
            "token_efficiency": self.calculate_token_efficiency(files_metadata),
        }

    def _calculate_weighted_score(self, category_scores: dict[str, float]) -> int:
        """
        Calculate weighted overall score from category scores.

        Algorithm: Weighted sum of quality components
        Purpose: Combine multiple quality dimensions into single 0-100 score
        Rationale: Weights reflect relative importance based on Memory Bank usage patterns
                  - Completeness & Consistency: Most critical (50% combined)
                  - Structure: Important for maintainability (20%)
                  - Freshness & Efficiency: Supporting metrics (30% combined)

        Args:
            category_scores: Dict of category name to score (0.0-1.0)

        Returns:
            Overall quality score (0-100)
        """
        weights = {
            "completeness": QUALITY_WEIGHT_COMPLETENESS,
            "consistency": QUALITY_WEIGHT_CONSISTENCY,
            "freshness": QUALITY_WEIGHT_FRESHNESS,
            "structure": QUALITY_WEIGHT_STRUCTURE,
            "token_efficiency": QUALITY_WEIGHT_EFFICIENCY,
        }
        return int(
            category_scores["completeness"] * weights["completeness"]
            + category_scores["consistency"] * weights["consistency"]
            + category_scores["freshness"] * weights["freshness"]
            + category_scores["structure"] * weights["structure"]
            + category_scores["token_efficiency"] * weights["token_efficiency"]
        )

    def _determine_grade_and_status(self, overall_score: int) -> tuple[str, str]:
        """Determine grade and status from overall score."""
        return (self.get_grade(overall_score), self.get_status(overall_score))

    def _collect_all_issues(
        self,
        category_scores: dict[str, float],
        duplication_data: dict[str, object],
    ) -> list[str]:
        """Collect all issues from category scores."""
        return self.collect_issues(
            category_scores["completeness"],
            category_scores["consistency"],
            category_scores["freshness"],
            category_scores["structure"],
            category_scores["token_efficiency"],
            duplication_data,
        )

    def _generate_all_recommendations(
        self, category_scores: dict[str, float], issues: list[str]
    ) -> list[str]:
        """Generate all recommendations from category scores and issues."""
        return self.generate_recommendations(
            category_scores["completeness"],
            category_scores["consistency"],
            category_scores["freshness"],
            category_scores["structure"],
            category_scores["token_efficiency"],
            issues,
        )

    def _build_score_result(
        self,
        overall_score: int,
        category_scores: dict[str, float],
        grade: str,
        status: str,
        issues: list[str],
        recommendations: list[str],
    ) -> dict[str, object]:
        """Build final score result dictionary."""
        return {
            "overall_score": overall_score,
            "breakdown": {
                "completeness": int(category_scores["completeness"]),
                "consistency": int(category_scores["consistency"]),
                "freshness": int(category_scores["freshness"]),
                "structure": int(category_scores["structure"]),
                "token_efficiency": int(category_scores["token_efficiency"]),
            },
            "grade": grade,
            "status": status,
            "issues": issues,
            "recommendations": recommendations,
        }

    def _add_completeness_issue(self, issues: list[str], completeness: float) -> None:
        """Add completeness issue if score is low."""
        if completeness < 80:
            issues.append(
                f"Completeness score is {int(completeness)}/100 - "
                + "some required sections may be missing"
            )

    def _add_consistency_issue(
        self,
        issues: list[str],
        consistency: float,
        duplication_data: dict[str, object],
    ) -> None:
        """Add consistency issue if duplicates found."""
        if consistency < 80:
            duplicates_raw: object = duplication_data.get("duplicates_found", 0)
            duplicates = (
                int(duplicates_raw) if isinstance(duplicates_raw, (int, float)) else 0
            )
            if duplicates > 0:
                issues.append(
                    f"Found {duplicates} duplicate or similar content sections"
                )

    def _add_freshness_issue(self, issues: list[str], freshness: float) -> None:
        """Add freshness issue if score is low."""
        if freshness < 60:
            issues.append(
                "Some files haven't been updated recently - "
                + "Memory Bank may be stale"
            )

    def _add_structure_issue(self, issues: list[str], structure: float) -> None:
        """Add structure issue if score is low."""
        if structure < 80:
            issues.append(
                "Structure issues detected - "
                + "check heading hierarchy and organization"
            )

    def _add_token_efficiency_issue(
        self, issues: list[str], token_efficiency: float
    ) -> None:
        """Add token efficiency issue if score is low."""
        if token_efficiency < 70:
            issues.append(
                "Token usage is outside optimal range - "
                + "consider reviewing content size"
            )
