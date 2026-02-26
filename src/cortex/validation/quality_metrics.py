"""
Quality metrics calculation for Memory Bank.

This module calculates quality scores and health metrics for
Memory Bank files to assess overall data quality.
"""

from datetime import datetime
from typing import cast

from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import DetailedFileMetadata, ModelDict

from .models import (
    DuplicationDataModel,
    FileMetadataForQuality,
    FileQualityScore,
    HealthGrade,
    LinkValidationDataModel,
    QualityHealthStatus,
    QualityScoreResult,
)
from .quality_metrics_coercion import (
    coerce_duplication_data,
    coerce_files_metadata_map,
    coerce_link_validation_data,
)
from .quality_metrics_issues import collect_all_issues
from .quality_metrics_recommendations import generate_all_recommendations
from .quality_metrics_result import (
    build_score_result,
    score_to_grade,
    score_to_status,
)
from .quality_metrics_scoring import (
    calculate_file_freshness_from_metadata,
    calculate_file_freshness_score,
    calculate_file_structure_score,
    calculate_token_efficiency_score,
    calculate_weighted_score,
)
from .schema_validator import SchemaValidator


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
        metadata_map = coerce_files_metadata_map(files_metadata)
        duplication = coerce_duplication_data(duplication_data)
        link_validation_model = coerce_link_validation_data(link_validation)

        category_scores = await self._calculate_category_scores(
            files_content, metadata_map, duplication, link_validation_model
        )
        overall_score = calculate_weighted_score(category_scores)
        grade = score_to_grade(overall_score)
        status = score_to_status(overall_score)
        issues = self._collect_all_issues(category_scores, duplication)
        recommendations = self._generate_all_recommendations(category_scores, issues)

        return build_score_result(
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
        validation_result = await self.schema_validator.validate_file(
            file_name, content
        )

        freshness = calculate_file_freshness_from_metadata(metadata)
        structure = calculate_file_structure_score(content)

        file_score = int(
            validation_result.score * 0.5 + freshness * 0.25 + structure * 0.25
        )

        return FileQualityScore(
            file_name=file_name,
            score=file_score,
            grade=score_to_grade(file_score),
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
        duplication_model = coerce_duplication_data(duplication_data)
        link_model = coerce_link_validation_data(link_validation)
        score = 100.0

        score -= duplication_model.duplicates_found * 5

        if link_model:
            score -= link_model.broken_links * 3

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

        metadata_map = coerce_files_metadata_map(files_metadata)
        now = datetime.now()
        scores: list[float] = []

        for metadata in metadata_map.values():
            score = calculate_file_freshness_score(metadata, now)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 50.0

    def calculate_file_freshness(
        self, metadata: FileMetadataForQuality | DetailedFileMetadata | ModelDict
    ) -> float:
        """Calculate freshness for a single file."""
        try:
            return calculate_file_freshness_from_metadata(metadata)
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to parse last_modified date: {e}")
            return 50.0

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
            scores.append(calculate_file_structure_score(content))

        return sum(scores) / len(scores)

    def calculate_file_structure(self, content: str) -> float:
        """Calculate structure score for a single file."""
        return calculate_file_structure_score(content)

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
        metadata_map = coerce_files_metadata_map(files_metadata)
        return calculate_token_efficiency_score(metadata_map)

    def get_grade(self, score: float) -> HealthGrade:
        """Convert score to letter grade."""
        return score_to_grade(score)

    def get_status(self, score: float) -> QualityHealthStatus:
        """Get health status based on score."""
        return score_to_status(score)

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
        return collect_all_issues(
            completeness,
            consistency,
            freshness,
            structure,
            token_efficiency,
            duplication_data,
        )

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
        return generate_all_recommendations(
            completeness,
            consistency,
            freshness,
            structure,
            token_efficiency,
            issues,
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

    def _collect_all_issues(
        self,
        category_scores: dict[str, float],
        duplication_data: DuplicationDataModel,
    ) -> list[str]:
        """Collect all issues from category scores."""
        return collect_all_issues(
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
        return generate_all_recommendations(
            category_scores["completeness"],
            category_scores["consistency"],
            category_scores["freshness"],
            category_scores["structure"],
            category_scores["token_efficiency"],
            issues,
        )
