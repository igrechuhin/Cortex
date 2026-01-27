"""
Quality metrics calculation for Memory Bank.

This module calculates quality scores and health metrics for
Memory Bank files to assess overall data quality.
"""

import re
from datetime import datetime
from typing import Literal, cast

from cortex.core.constants import (
    QUALITY_WEIGHT_COMPLETENESS,
    QUALITY_WEIGHT_CONSISTENCY,
    QUALITY_WEIGHT_EFFICIENCY,
    QUALITY_WEIGHT_FRESHNESS,
    QUALITY_WEIGHT_STRUCTURE,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import DetailedFileMetadata, ModelDict

from .models import (
    CategoryBreakdown,
    DuplicationDataModel,
    FileMetadataForQuality,
    FileQualityScore,
    LinkValidationDataModel,
    QualityScoreResult,
)
from .schema_validator import SchemaValidator


def _coerce_file_metadata(
    metadata: DetailedFileMetadata | FileMetadataForQuality | ModelDict,
) -> FileMetadataForQuality:
    if isinstance(metadata, FileMetadataForQuality):
        return metadata
    if isinstance(metadata, DetailedFileMetadata):
        return FileMetadataForQuality(
            last_modified=metadata.last_modified,
            token_count=metadata.token_count,
            size_bytes=metadata.size_bytes,
            read_count=metadata.read_count,
            write_count=metadata.write_count,
        )
    return FileMetadataForQuality.model_validate(metadata)


def _coerce_files_metadata_map(
    files_metadata: dict[
        str, DetailedFileMetadata | FileMetadataForQuality | ModelDict
    ],
) -> dict[str, FileMetadataForQuality]:
    coerced: dict[str, FileMetadataForQuality] = {}
    for file_name, meta in files_metadata.items():
        coerced[file_name] = _coerce_file_metadata(meta)
    return coerced


def _coerce_duplication_data(
    duplication_data: DuplicationDataModel | ModelDict,
) -> DuplicationDataModel:
    if isinstance(duplication_data, DuplicationDataModel):
        return duplication_data
    dup_count_raw = duplication_data.get("duplicates_found", 0)
    dup_count = int(dup_count_raw) if isinstance(dup_count_raw, (int, float)) else 0
    return DuplicationDataModel(duplicates_found=dup_count)


def _coerce_link_validation_data(
    link_validation: LinkValidationDataModel | ModelDict | None,
) -> LinkValidationDataModel | None:
    if link_validation is None or isinstance(link_validation, LinkValidationDataModel):
        return link_validation
    broken_raw = link_validation.get("broken_links", 0)
    if isinstance(broken_raw, list):
        broken = len(broken_raw)
    else:
        broken = int(broken_raw) if isinstance(broken_raw, (int, float)) else 0
    return LinkValidationDataModel(broken_links=broken)


class QualityMetrics:
    """Calculate Memory Bank quality metrics."""

    def __init__(
        self,
        schema_validator: SchemaValidator,
        metadata_index: MetadataIndex | None = None,
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
        files_metadata: dict[
            str, DetailedFileMetadata | FileMetadataForQuality | ModelDict
        ],
        duplication_data: DuplicationDataModel | ModelDict,
        link_validation: LinkValidationDataModel | ModelDict | None = None,
    ) -> QualityScoreResult:
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
        metadata_map = _coerce_files_metadata_map(files_metadata)
        duplication = _coerce_duplication_data(duplication_data)
        link_validation_model = _coerce_link_validation_data(link_validation)

        category_scores = await self._calculate_category_scores(
            files_content, metadata_map, duplication, link_validation_model
        )
        overall_score = self._calculate_weighted_score(category_scores)
        grade, status = self._determine_grade_and_status(overall_score)
        issues = self._collect_all_issues(category_scores, duplication)
        recommendations = self._generate_all_recommendations(category_scores, issues)

        return self._build_score_result(
            overall_score, category_scores, grade, status, issues, recommendations
        )

    async def calculate_file_score(
        self,
        file_name: str,
        content: str,
        metadata: DetailedFileMetadata | FileMetadataForQuality | ModelDict,
    ) -> FileQualityScore:
        """
        Calculate quality score for individual file.

        Args:
            file_name: Name of file
            content: File content
            metadata: File metadata

        Returns:
            FileQualityScore model with file quality details
        """
        # Validate against schema
        validation_result = await self.schema_validator.validate_file(
            file_name, content
        )

        # Calculate freshness for this file
        freshness = self.calculate_file_freshness(_coerce_file_metadata(metadata))

        # Calculate structure score
        structure = self.calculate_file_structure(content)

        # Overall file score
        file_score = int(
            validation_result.score * 0.5 + freshness * 0.25 + structure * 0.25
        )

        return FileQualityScore(
            file_name=file_name,
            score=file_score,
            grade=self.get_grade(file_score),
            validation=validation_result,
            freshness=int(freshness),
            structure=int(structure),
        )

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
            total_score += validation.score

        return total_score / len(files_content)

    def calculate_consistency(
        self,
        duplication_data: DuplicationDataModel | ModelDict,
        link_validation: LinkValidationDataModel | ModelDict | None = None,
    ) -> float:
        """
        Score based on duplication and link integrity.

        Args:
            duplication_data: Duplication scan results
            link_validation: Optional link validation results

        Returns:
            Consistency score 0-100
        """
        duplication_model = _coerce_duplication_data(duplication_data)
        link_model = _coerce_link_validation_data(link_validation)
        score = 100.0

        # Deduct for duplications
        score -= duplication_model.duplicates_found * 5  # 5 points per duplication

        # Deduct for broken links if provided
        if link_model:
            score -= link_model.broken_links * 3  # 3 points per broken link

        return max(0.0, score)

    def calculate_freshness(
        self,
        files_metadata: dict[
            str, FileMetadataForQuality | DetailedFileMetadata | ModelDict
        ],
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

        metadata_map = _coerce_files_metadata_map(files_metadata)
        now = datetime.now()
        scores: list[float] = []

        for metadata in metadata_map.values():
            score = self._calculate_file_freshness_score(metadata, now)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 50.0

    def _calculate_file_freshness_score(
        self, metadata: FileMetadataForQuality, now: datetime
    ) -> float:
        """Calculate freshness score for a single file."""
        if not metadata.last_modified:
            return 50.0

        try:
            last_mod_dt = datetime.fromisoformat(
                metadata.last_modified.replace("Z", "+00:00")
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

    def calculate_file_freshness(
        self, metadata: FileMetadataForQuality | DetailedFileMetadata | ModelDict
    ) -> float:
        """Calculate freshness for a single file.

        Reduced nesting: Extracted date parsing and scoring to helper methods.
        Nesting: 2 levels (down from 5 levels)
        """
        meta = _coerce_file_metadata(metadata)
        if not meta.last_modified:
            return 50.0

        try:
            days_old = self._parse_last_modified_date(meta.last_modified)
            return self._score_by_age(days_old)
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to parse last_modified date: {e}")
            return 50.0

    def _parse_last_modified_date(self, last_modified: str) -> int:
        """Parse last modified date and calculate days old.

        Args:
            last_modified: ISO timestamp string

        Returns:
            Number of days since last modification
        """
        last_mod_dt = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
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
        self,
        files_metadata: dict[
            str, FileMetadataForQuality | DetailedFileMetadata | ModelDict
        ],
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

        metadata_map = _coerce_files_metadata_map(files_metadata)
        total_tokens = sum(meta.token_count for meta in metadata_map.values())

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

    def get_grade(self, score: float) -> Literal["A", "B", "C", "D", "F"]:
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

    def get_status(self, score: float) -> Literal["healthy", "warning", "critical"]:
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
        duplication_data: DuplicationDataModel | ModelDict,
    ) -> list[str]:
        """Collect issues based on scores."""
        issues: list[str] = []

        self._add_completeness_issue(issues, completeness)
        self._add_consistency_issue(
            issues, consistency, _coerce_duplication_data(duplication_data)
        )
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
                (
                    "Review and update stale files, especially "
                    "activeContext.md and progress.md"
                )
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
                (
                    "Review token usage with 'check_token_budget' and "
                    "consider summarizing verbose sections"  # noqa: E501
                )
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
        files_metadata: dict[str, FileMetadataForQuality],
        duplication_data: DuplicationDataModel,
        link_validation: LinkValidationDataModel | None,
    ) -> dict[str, float]:
        """Calculate all individual category scores."""
        files_metadata_wide: dict[
            str, FileMetadataForQuality | DetailedFileMetadata | ModelDict
        ] = {
            file_name: cast(
                FileMetadataForQuality | DetailedFileMetadata | ModelDict, meta
            )
            for file_name, meta in files_metadata.items()
        }
        return {
            "completeness": await self.calculate_completeness(files_content),
            "consistency": self.calculate_consistency(
                duplication_data, link_validation
            ),
            "freshness": self.calculate_freshness(files_metadata_wide),
            "structure": self.calculate_structure(files_content),
            "token_efficiency": self.calculate_token_efficiency(files_metadata_wide),
        }

    def _calculate_weighted_score(self, category_scores: dict[str, float]) -> int:
        """
        Calculate weighted overall score from category scores.

        Algorithm: Weighted sum of quality components
        Purpose: Combine multiple quality dimensions into single 0-100 score
        Rationale: Weights reflect relative importance based on Memory
        Bank usage patterns
                  - Completeness & Consistency: Most critical (50%
                  combined)
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

    def _determine_grade_and_status(
        self, overall_score: int
    ) -> tuple[
        Literal["A", "B", "C", "D", "F"], Literal["healthy", "warning", "critical"]
    ]:
        """Determine grade and status from overall score."""
        return (self.get_grade(overall_score), self.get_status(overall_score))

    def _collect_all_issues(
        self,
        category_scores: dict[str, float],
        duplication_data: DuplicationDataModel,
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
        grade: Literal["A", "B", "C", "D", "F"],
        status: Literal["healthy", "warning", "critical"],
        issues: list[str],
        recommendations: list[str],
    ) -> QualityScoreResult:
        """Build final score result model."""
        return QualityScoreResult(
            overall_score=overall_score,
            breakdown=CategoryBreakdown(
                completeness=int(category_scores["completeness"]),
                consistency=int(category_scores["consistency"]),
                freshness=int(category_scores["freshness"]),
                structure=int(category_scores["structure"]),
                token_efficiency=int(category_scores["token_efficiency"]),
            ),
            grade=grade,
            status=status,
            issues=issues,
            recommendations=recommendations,
        )

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
        duplication_data: DuplicationDataModel,
    ) -> None:
        """Add consistency issue if duplicates found."""
        if consistency < 80:
            if duplication_data.duplicates_found > 0:
                issues.append(
                    (
                        f"Found {duplication_data.duplicates_found} duplicate "
                        f"or similar content sections"
                    )
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
