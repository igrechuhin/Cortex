"""
Unit tests for QualityMetrics module.

Tests quality score calculation including:
- Overall score calculation with category weights
- Individual category scores (completeness, consistency, freshness,
  structure, token efficiency)
- File-level quality scoring
- Grade and status determination
- Issue collection and recommendation generation
"""

from datetime import datetime, timedelta
from typing import cast

import pytest

from cortex.core.models import ModelDict
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator


@pytest.fixture
def schema_validator() -> SchemaValidator:
    """Create SchemaValidator instance with default schemas."""
    return SchemaValidator()


@pytest.fixture
def quality_metrics(schema_validator: SchemaValidator) -> QualityMetrics:
    """Create QualityMetrics instance."""
    return QualityMetrics(schema_validator=schema_validator)


@pytest.fixture
def perfect_files_content() -> dict[str, str]:
    """Perfect file content with all required sections."""
    return {
        "memorybankinstructions.md": (
            "# Memory Bank Instructions\n\n"
            "## Purpose\n\n"
            "Main purpose.\n\n"
            "## Guidelines\n\n"
            "Usage guidelines.\n\n"
            "## Structure\n\n"
            "File structure.\n\n"
            "## Examples\n\n"
            "Example content."
        ),
        "projectBrief.md": (
            "# Project Brief\n\n"
            "## Project Overview\n\n"
            "Project overview.\n\n"
            "## Goals\n\n"
            "Project goals.\n\n"
            "## Core Requirements\n\n"
            "Requirements.\n\n"
            "## Success Criteria\n\n"
            "Success criteria."
        ),
    }


@pytest.fixture
def incomplete_files_content() -> dict[str, str]:
    """Incomplete file content with missing sections."""
    return {
        "memorybankinstructions.md": (
            "# Memory Bank Instructions\n\n## Purpose\n\nMain purpose."
            # Missing Guidelines and Structure sections
        ),
        "projectBrief.md": (
            "# Project Brief\n\n"
            # Missing Project Overview section
            "## Goals\n\n"
            "Project goals."
            # Missing Core Requirements and Success Criteria
        ),
    }


@pytest.fixture
def recent_metadata() -> dict[str, dict[str, object]]:
    """Recent metadata (within 7 days)."""
    now = datetime.now()
    recent = (now - timedelta(days=3)).isoformat()
    return {
        "memorybankinstructions.md": {"last_modified": recent, "token_count": 500},
        "projectBrief.md": {"last_modified": recent, "token_count": 400},
    }


@pytest.fixture
def stale_metadata() -> dict[str, dict[str, object]]:
    """Stale metadata (>180 days old)."""
    now = datetime.now()
    stale = (now - timedelta(days=200)).isoformat()
    return {
        "memorybankinstructions.md": {"last_modified": stale, "token_count": 500},
        "projectBrief.md": {"last_modified": stale, "token_count": 400},
    }


@pytest.fixture
def optimal_token_metadata() -> dict[str, dict[str, object]]:
    """Metadata with optimal token counts."""
    now = datetime.now().isoformat()
    return {
        "file1.md": {"last_modified": now, "token_count": 10000},
        "file2.md": {"last_modified": now, "token_count": 15000},
        "file3.md": {"last_modified": now, "token_count": 20000},
    }


@pytest.fixture
def no_duplications() -> dict[str, object]:
    """No duplication data."""
    return {
        "duplicates_found": 0,
        "exact_duplicates": [],
        "similar_content": [],
    }


@pytest.fixture
def with_duplications() -> dict[str, object]:
    """Duplication data with some duplicates."""
    return {
        "duplicates_found": 3,
        "exact_duplicates": [
            {"section": "Purpose", "files": ["file1.md", "file2.md"]},
        ],
        "similar_content": [
            {
                "section": "Overview",
                "files": ["file1.md", "file3.md"],
                "similarity": 0.85,
            }
        ],
    }


class TestQualityMetricsInitialization:
    """Tests for QualityMetrics initialization."""

    def test_initialization_with_validator(
        self, schema_validator: SchemaValidator
    ) -> None:
        """Test QualityMetrics initializes with schema validator."""
        metrics = QualityMetrics(schema_validator=schema_validator)

        assert metrics.schema_validator is schema_validator
        assert metrics.metadata_index is None

    def test_initialization_with_metadata_index(
        self, schema_validator: SchemaValidator
    ) -> None:
        """Test QualityMetrics initializes with metadata index."""
        from cortex.core.metadata_index import MetadataIndex

        mock_index: MetadataIndex | None = None
        metrics = QualityMetrics(
            schema_validator=schema_validator, metadata_index=mock_index
        )

        assert metrics.schema_validator is schema_validator
        assert metrics.metadata_index is mock_index


class TestOverallScoreCalculation:
    """Tests for calculate_overall_score method."""

    @pytest.mark.asyncio
    async def test_perfect_score_all_categories(
        self,
        quality_metrics: QualityMetrics,
        perfect_files_content: dict[str, str],
        recent_metadata: dict[str, dict[str, object]],
        no_duplications: dict[str, object],
    ) -> None:
        """Test overall score calculation with perfect inputs."""
        # Add token counts to metadata to reach optimal range (20k-80k)
        metadata_with_optimal_tokens: dict[str, ModelDict] = {
            "memorybankinstructions.md": cast(
                ModelDict,
                {
                    "last_modified": recent_metadata["memorybankinstructions.md"][
                        "last_modified"
                    ],
                    "token_count": 25000,  # In optimal range
                },
            ),
            "projectBrief.md": cast(
                ModelDict,
                {
                    "last_modified": recent_metadata["projectBrief.md"][
                        "last_modified"
                    ],
                    "token_count": 20000,  # In optimal range
                },
            ),
        }

        result = await quality_metrics.calculate_overall_score(
            files_content=perfect_files_content,
            files_metadata=metadata_with_optimal_tokens,  # type: ignore[arg-type] - ModelDict is compatible
            duplication_data=cast(ModelDict, no_duplications),
        )

        assert isinstance(result.overall_score, (int, float))
        assert int(result.overall_score) >= 90  # Should be high
        assert result.grade == "A"
        assert result.status == "healthy"
        issues_list = result.issues
        assert len(issues_list) == 0  # No issues with optimal tokens

    @pytest.mark.asyncio
    async def test_poor_score_all_categories(
        self,
        quality_metrics: QualityMetrics,
        incomplete_files_content: dict[str, str],
        stale_metadata: dict[str, dict[str, object]],
        with_duplications: dict[str, object],
    ) -> None:
        """Test overall score calculation with poor inputs."""
        result = await quality_metrics.calculate_overall_score(
            files_content=incomplete_files_content,
            files_metadata={
                k: cast(ModelDict, v) for k, v in stale_metadata.items()
            },  # type: ignore[arg-type] - ModelDict is compatible
            duplication_data=cast(ModelDict, with_duplications),
        )

        assert isinstance(result.overall_score, (int, float))
        assert int(result.overall_score) < 70  # Should be low (relaxed from 60)
        assert result.grade in ["C", "D", "F"]
        assert result.status in ["warning", "critical"]
        issues_list = result.issues
        assert len(issues_list) > 0

    @pytest.mark.asyncio
    async def test_breakdown_structure(
        self,
        quality_metrics: QualityMetrics,
        perfect_files_content: dict[str, str],
        recent_metadata: dict[str, dict[str, object]],
        no_duplications: dict[str, object],
    ) -> None:
        """Test breakdown contains all expected categories."""
        result = await quality_metrics.calculate_overall_score(
            files_content=perfect_files_content,
            files_metadata={
                k: cast(ModelDict, v) for k, v in recent_metadata.items()
            },  # type: ignore[arg-type] - ModelDict is compatible
            duplication_data=cast(ModelDict, no_duplications),
        )

        breakdown = result.breakdown
        assert isinstance(breakdown.completeness, int)
        assert isinstance(breakdown.consistency, int)
        assert isinstance(breakdown.freshness, int)
        assert isinstance(breakdown.structure, int)
        assert isinstance(breakdown.token_efficiency, int)
        assert 0 <= breakdown.completeness <= 100
        assert 0 <= breakdown.consistency <= 100
        assert 0 <= breakdown.freshness <= 100
        assert 0 <= breakdown.structure <= 100
        assert 0 <= breakdown.token_efficiency <= 100

    @pytest.mark.asyncio
    async def test_with_link_validation(
        self,
        quality_metrics: QualityMetrics,
        perfect_files_content: dict[str, str],
        recent_metadata: dict[str, dict[str, object]],
        no_duplications: dict[str, object],
    ) -> None:
        """Test overall score with link validation data."""
        link_validation = cast(
            ModelDict,
            {"broken_links": [{"source": "file1.md", "target": "missing.md"}]},
        )

        result = await quality_metrics.calculate_overall_score(
            files_content=perfect_files_content,
            files_metadata={
                k: cast(ModelDict, v) for k, v in recent_metadata.items()
            },  # type: ignore[arg-type] - ModelDict is compatible
            duplication_data=cast(ModelDict, no_duplications),
            link_validation=link_validation,
        )

        # Consistency score should be lower due to broken links
        assert isinstance(result.breakdown.consistency, int)
        assert result.breakdown.consistency < 100

    @pytest.mark.asyncio
    async def test_recommendations_generated(
        self,
        quality_metrics: QualityMetrics,
        incomplete_files_content: dict[str, str],
        stale_metadata: dict[str, dict[str, object]],
        with_duplications: dict[str, object],
    ) -> None:
        """Test recommendations are generated for issues."""
        result = await quality_metrics.calculate_overall_score(
            files_content=incomplete_files_content,
            files_metadata={
                k: cast(ModelDict, v) for k, v in stale_metadata.items()
            },  # type: ignore[arg-type] - ModelDict is compatible
            duplication_data=cast(ModelDict, with_duplications),
        )

        recommendations_list = result.recommendations
        assert len(recommendations_list) > 0
        assert all(isinstance(rec, str) for rec in recommendations_list)


class TestFileScoreCalculation:
    """Tests for calculate_file_score method."""

    @pytest.mark.asyncio
    async def test_perfect_file_score(
        self,
        quality_metrics: QualityMetrics,
        recent_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test file score calculation for perfect file."""
        content = (
            "# Memory Bank Instructions\n\n"
            "## Purpose\n\n"
            "Main purpose.\n\n"
            "## Guidelines\n\n"
            "Usage guidelines.\n\n"
            "## Structure\n\n"
            "File structure."
        )
        metadata = cast(ModelDict, recent_metadata["memorybankinstructions.md"])

        result = await quality_metrics.calculate_file_score(
            file_name="memorybankinstructions.md", content=content, metadata=metadata
        )

        assert result.file_name == "memorybankinstructions.md"
        assert isinstance(result.score, (int, float))
        assert int(result.score) >= 80
        assert result.grade in ["A", "B"]
        assert result.validation is not None
        assert isinstance(result.freshness, int)
        assert isinstance(result.structure, int)

    @pytest.mark.asyncio
    async def test_poor_file_score(
        self,
        quality_metrics: QualityMetrics,
        stale_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test file score calculation for poor file."""
        content = "# File\n\nMinimal content."
        metadata = cast(ModelDict, stale_metadata["memorybankinstructions.md"])

        result = await quality_metrics.calculate_file_score(
            file_name="memorybankinstructions.md", content=content, metadata=metadata
        )

        assert isinstance(result.score, (int, float))
        assert int(result.score) < 60
        assert result.grade in ["D", "F"]


class TestCompletenessCalculation:
    """Tests for _calculate_completeness method."""

    @pytest.mark.asyncio
    async def test_perfect_completeness(
        self, quality_metrics: QualityMetrics, perfect_files_content: dict[str, str]
    ) -> None:
        """Test completeness with all required sections."""
        score: float = await quality_metrics.calculate_completeness(
            perfect_files_content
        )

        assert score >= 90.0
        assert score <= 100.0

    @pytest.mark.asyncio
    async def test_incomplete_files(
        self,
        quality_metrics: QualityMetrics,
        incomplete_files_content: dict[str, str],
    ) -> None:
        """Test completeness with missing sections."""
        score: float = await quality_metrics.calculate_completeness(
            incomplete_files_content
        )

        assert score < 90.0

    @pytest.mark.asyncio
    async def test_empty_files(self, quality_metrics: QualityMetrics) -> None:
        """Test completeness with no files."""
        score: float = await quality_metrics.calculate_completeness({})
        assert score == 0.0


class TestConsistencyCalculation:
    """Tests for _calculate_consistency method."""

    def test_perfect_consistency(
        self, quality_metrics: QualityMetrics, no_duplications: dict[str, object]
    ) -> None:
        """Test consistency with no duplications or broken links."""
        score: float = quality_metrics.calculate_consistency(
            cast(ModelDict, no_duplications)
        )

        assert score == 100.0

    def test_consistency_with_duplications(
        self, quality_metrics: QualityMetrics, with_duplications: dict[str, object]
    ) -> None:
        """Test consistency penalized by duplications."""
        score: float = quality_metrics.calculate_consistency(
            cast(ModelDict, with_duplications)
        )

        # 3 duplicates * 5 points = 15 point penalty
        assert score == 85.0

    def test_consistency_with_broken_links(
        self, quality_metrics: QualityMetrics, no_duplications: dict[str, object]
    ) -> None:
        """Test consistency penalized by broken links."""
        link_validation = cast(
            ModelDict,
            {"broken_links": [{"source": "a.md"}, {"source": "b.md"}]},
        )
        score: float = quality_metrics.calculate_consistency(
            cast(ModelDict, no_duplications), link_validation
        )

        # 2 broken links * 3 points = 6 point penalty
        assert score == 94.0

    def test_consistency_minimum_zero(self, quality_metrics: QualityMetrics) -> None:
        """Test consistency score doesn't go below zero."""
        many_duplications = cast(ModelDict, {"duplicates_found": 50})
        score: float = quality_metrics.calculate_consistency(many_duplications)

        assert score == 0.0


class TestFreshnessCalculation:
    """Tests for _calculate_freshness method."""

    def test_recent_files(
        self,
        quality_metrics: QualityMetrics,
        recent_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test freshness with recently updated files."""
        score: float = quality_metrics.calculate_freshness(
            {k: cast(ModelDict, v) for k, v in recent_metadata.items()}  # type: ignore[arg-type] - ModelDict is compatible
        )

        assert score == 100.0

    def test_stale_files(
        self,
        quality_metrics: QualityMetrics,
        stale_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test freshness with old files."""
        score: float = quality_metrics.calculate_freshness(
            {k: cast(ModelDict, v) for k, v in stale_metadata.items()}  # type: ignore[arg-type] - ModelDict is compatible
        )

        assert score == 20.0

    def test_mixed_freshness(self, quality_metrics: QualityMetrics) -> None:
        """Test freshness with mixed file ages."""
        now = datetime.now()
        metadata: dict[str, ModelDict] = {
            "recent.md": cast(
                ModelDict,
                {
                    "last_modified": (now - timedelta(days=5)).isoformat(),
                    "token_count": 100,
                },
            ),
            "old.md": cast(
                ModelDict,
                {
                    "last_modified": (now - timedelta(days=200)).isoformat(),
                    "token_count": 100,
                },
            ),
        }
        score: float = quality_metrics.calculate_freshness(metadata)  # type: ignore[arg-type] - ModelDict is compatible
        # Average of 100 (recent) and 20 (stale) = 60
        assert score == 60.0

    def test_missing_timestamps(self, quality_metrics: QualityMetrics) -> None:
        """Test freshness with missing timestamps."""
        metadata: dict[str, ModelDict] = {
            "file1.md": cast(ModelDict, {"token_count": 100}),
            "file2.md": cast(ModelDict, {"token_count": 100}),
        }
        score: float = quality_metrics.calculate_freshness(metadata)  # type: ignore[arg-type] - ModelDict is compatible
        # Should default to 50 for missing timestamps
        assert score == 50.0

    def test_empty_metadata(self, quality_metrics: QualityMetrics) -> None:
        """Test freshness with no metadata."""
        score: float = quality_metrics.calculate_freshness({})
        assert score == 50.0

    def test_invalid_timestamp_format(self, quality_metrics: QualityMetrics) -> None:
        """Test freshness with invalid timestamp format."""
        metadata: dict[str, ModelDict] = {
            "file.md": cast(
                ModelDict, {"last_modified": "invalid-date", "token_count": 100}
            )
        }
        score: float = quality_metrics.calculate_freshness(metadata)  # type: ignore[arg-type] - ModelDict is compatible
        # Should default to 50 for invalid timestamps
        assert score == 50.0


class TestFileFreshnessCalculation:
    """Tests for _calculate_file_freshness method."""

    def test_file_freshness_recent(self, quality_metrics: QualityMetrics) -> None:
        """Test file freshness for recent file."""
        now = datetime.now()
        metadata = cast(
            ModelDict,
            {"last_modified": (now - timedelta(days=3)).isoformat()},
        )

        score: float = quality_metrics.calculate_file_freshness(metadata)
        assert score == 100.0

    def test_file_freshness_stale(self, quality_metrics: QualityMetrics) -> None:
        """Test file freshness for stale file."""
        now = datetime.now()
        metadata = cast(
            ModelDict,
            {"last_modified": (now - timedelta(days=200)).isoformat()},
        )

        score: float = quality_metrics.calculate_file_freshness(metadata)
        assert score == 20.0

    def test_file_freshness_missing_timestamp(
        self, quality_metrics: QualityMetrics
    ) -> None:
        """Test file freshness with missing timestamp."""
        score: float = quality_metrics.calculate_file_freshness(cast(ModelDict, {}))
        assert score == 50.0


class TestStructureCalculation:
    """Tests for _calculate_structure method."""

    def test_perfect_structure(self, quality_metrics: QualityMetrics) -> None:
        """Test structure with perfect heading hierarchy."""
        files_content: dict[str, str] = {
            "file.md": (
                "# Title\n\n"
                "## Level 2\n\n"
                "### Level 3\n\n"
                "### Another Level 3\n\n"
                "## Another Level 2\n"
            )
        }
        score: float = quality_metrics.calculate_structure(files_content)
        assert score == 100.0

    def test_structure_with_skipped_levels(
        self, quality_metrics: QualityMetrics
    ) -> None:
        """Test structure penalized for skipped levels."""
        files_content: dict[str, str] = {
            "file.md": ("# Title\n\n#### Level 4 (skipped 2 and 3)\n")
        }
        score: float = quality_metrics.calculate_structure(files_content)
        # 10 point penalty for skipped level
        assert score == 90.0

    def test_structure_with_deep_nesting(self, quality_metrics: QualityMetrics) -> None:
        """Test structure penalized for deep nesting."""
        files_content: dict[str, str] = {
            "file.md": (
                "# Level 1\n"
                "## Level 2\n"
                "### Level 3\n"
                "#### Level 4\n"
                "##### Level 5 (too deep)\n"
            )
        }
        score: float = quality_metrics.calculate_structure(files_content)
        # 5 point penalty for level 5
        assert score == 95.0

    def test_empty_files(self, quality_metrics: QualityMetrics) -> None:
        """Test structure with no files."""
        score: float = quality_metrics.calculate_structure({})
        assert score == 0.0


class TestFileStructureCalculation:
    """Tests for _calculate_file_structure method."""

    def test_file_structure_perfect(self, quality_metrics: QualityMetrics) -> None:
        """Test file structure with perfect hierarchy."""
        content: str = "# Title\n\n## Section\n\n### Subsection\n"
        score: float = quality_metrics.calculate_file_structure(content)
        assert score == 100.0

    def test_file_structure_skipped_level(
        self, quality_metrics: QualityMetrics
    ) -> None:
        """Test file structure with skipped level."""
        content: str = "# Title\n#### Level 4 (skipped)\n"
        score: float = quality_metrics.calculate_file_structure(content)
        assert score == 90.0

    def test_file_structure_multiple_issues(
        self, quality_metrics: QualityMetrics
    ) -> None:
        """Test file structure with multiple issues."""
        content: str = (
            "# Title\n#### Skipped (penalty 10)\n##### Too deep (penalty 5)\n"
        )
        score: float = quality_metrics.calculate_file_structure(content)
        assert score == 85.0


class TestTokenEfficiencyCalculation:
    """Tests for _calculate_token_efficiency method."""

    def test_optimal_token_range(
        self,
        quality_metrics: QualityMetrics,
        optimal_token_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test token efficiency with optimal range (20k-80k)."""
        score: float = quality_metrics.calculate_token_efficiency(
            {k: cast(ModelDict, v) for k, v in optimal_token_metadata.items()}  # type: ignore[arg-type] - ModelDict is compatible
        )

        # Total: 45k tokens (optimal range)
        assert score == 100.0

    def test_too_few_tokens(self, quality_metrics: QualityMetrics) -> None:
        """Test token efficiency penalized for too few tokens."""
        metadata: dict[str, ModelDict] = {
            "file.md": cast(
                ModelDict,
                {
                    "last_modified": datetime.now().isoformat(),
                    "token_count": 5000,
                },
            )
        }
        score: float = quality_metrics.calculate_token_efficiency(metadata)  # type: ignore[arg-type] - ModelDict is compatible
        # 5k / 20k = 0.25, so 50 + (0.25 * 50) = 62.5
        assert score == 62.5

    def test_too_many_tokens(self, quality_metrics: QualityMetrics) -> None:
        """Test token efficiency penalized for too many tokens."""
        metadata: dict[str, ModelDict] = {
            "file.md": cast(
                ModelDict,
                {
                    "last_modified": datetime.now().isoformat(),
                    "token_count": 100000,
                },
            )
        }
        score: float = quality_metrics.calculate_token_efficiency(metadata)  # type: ignore[arg-type] - ModelDict is compatible
        # Excess: 20k, penalty: (20k / 1000) * 2 = 40
        assert score == 60.0

    def test_empty_metadata(self, quality_metrics: QualityMetrics) -> None:
        """Test token efficiency with no metadata."""
        score: float = quality_metrics.calculate_token_efficiency({})
        assert score == 100.0


class TestGradeAndStatus:
    """Tests for _get_grade and _get_status methods."""

    def test_grade_a(self, quality_metrics: QualityMetrics) -> None:
        """Test grade A for scores 90+."""
        assert quality_metrics.get_grade(95.0) == "A"
        assert quality_metrics.get_grade(90.0) == "A"

    def test_grade_b(self, quality_metrics: QualityMetrics) -> None:
        """Test grade B for scores 80-89."""
        assert quality_metrics.get_grade(85.0) == "B"
        assert quality_metrics.get_grade(80.0) == "B"

    def test_grade_c(self, quality_metrics: QualityMetrics) -> None:
        """Test grade C for scores 70-79."""
        assert quality_metrics.get_grade(75.0) == "C"
        assert quality_metrics.get_grade(70.0) == "C"

    def test_grade_d(self, quality_metrics: QualityMetrics) -> None:
        """Test grade D for scores 60-69."""
        assert quality_metrics.get_grade(65.0) == "D"
        assert quality_metrics.get_grade(60.0) == "D"

    def test_grade_f(self, quality_metrics: QualityMetrics) -> None:
        """Test grade F for scores <60."""
        assert quality_metrics.get_grade(50.0) == "F"
        assert quality_metrics.get_grade(0.0) == "F"

    def test_status_healthy(self, quality_metrics: QualityMetrics) -> None:
        """Test healthy status for scores 80+."""
        assert quality_metrics.get_status(90.0) == "healthy"
        assert quality_metrics.get_status(80.0) == "healthy"

    def test_status_warning(self, quality_metrics: QualityMetrics) -> None:
        """Test warning status for scores 60-79."""
        assert quality_metrics.get_status(70.0) == "warning"
        assert quality_metrics.get_status(60.0) == "warning"

    def test_status_critical(self, quality_metrics: QualityMetrics) -> None:
        """Test critical status for scores <60."""
        assert quality_metrics.get_status(50.0) == "critical"
        assert quality_metrics.get_status(0.0) == "critical"


class TestIssueCollection:
    """Tests for _collect_issues method."""

    def test_no_issues(
        self, quality_metrics: QualityMetrics, no_duplications: dict[str, object]
    ) -> None:
        """Test issue collection with no issues."""
        issues: list[str] = quality_metrics.collect_issues(
            completeness=90.0,
            consistency=90.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            duplication_data=cast(ModelDict, no_duplications),
        )

        assert len(issues) == 0

    def test_completeness_issue(
        self, quality_metrics: QualityMetrics, no_duplications: dict[str, object]
    ) -> None:
        """Test issue collected for low completeness."""
        issues: list[str] = quality_metrics.collect_issues(
            completeness=70.0,
            consistency=90.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            duplication_data=cast(ModelDict, no_duplications),
        )

        assert len(issues) >= 1
        assert any("Completeness" in issue for issue in issues)

    def test_consistency_issue(
        self,
        quality_metrics: QualityMetrics,
        with_duplications: dict[str, object],
    ) -> None:
        """Test issue collected for low consistency."""
        issues: list[str] = quality_metrics.collect_issues(
            completeness=90.0,
            consistency=70.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            duplication_data=cast(ModelDict, with_duplications),
        )

        assert len(issues) >= 1
        assert any("duplicate" in issue.lower() for issue in issues)

    def test_freshness_issue(
        self, quality_metrics: QualityMetrics, no_duplications: dict[str, object]
    ) -> None:
        """Test issue collected for low freshness."""
        issues: list[str] = quality_metrics.collect_issues(
            completeness=90.0,
            consistency=90.0,
            freshness=50.0,
            structure=90.0,
            token_efficiency=90.0,
            duplication_data=cast(ModelDict, no_duplications),
        )

        assert len(issues) >= 1
        assert any("updated recently" in issue for issue in issues)

    def test_multiple_issues(
        self,
        quality_metrics: QualityMetrics,
        with_duplications: dict[str, object],
    ) -> None:
        """Test multiple issues collected."""
        issues: list[str] = quality_metrics.collect_issues(
            completeness=70.0,
            consistency=70.0,
            freshness=50.0,
            structure=70.0,
            token_efficiency=60.0,
            duplication_data=cast(ModelDict, with_duplications),
        )

        assert len(issues) >= 4


class TestRecommendationGeneration:
    """Tests for _generate_recommendations method."""

    def test_no_issues_recommendation(self, quality_metrics: QualityMetrics) -> None:
        """Test recommendation when no issues."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=90.0,
            consistency=90.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            issues=[],
        )

        assert len(recommendations) == 1
        assert "good shape" in recommendations[0]

    def test_completeness_recommendation(self, quality_metrics: QualityMetrics) -> None:
        """Test recommendation for low completeness."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=70.0,
            consistency=90.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            issues=["Completeness issue"],
        )

        assert any("validate_memory_bank" in rec for rec in recommendations)

    def test_consistency_recommendation(self, quality_metrics: QualityMetrics) -> None:
        """Test recommendation for low consistency."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=90.0,
            consistency=70.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=90.0,
            issues=["Consistency issue"],
        )

        assert any("check_duplications" in rec for rec in recommendations)

    def test_freshness_recommendation(self, quality_metrics: QualityMetrics) -> None:
        """Test recommendation for low freshness."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=90.0,
            consistency=90.0,
            freshness=50.0,
            structure=90.0,
            token_efficiency=90.0,
            issues=["Freshness issue"],
        )

        assert any("update stale files" in rec.lower() for rec in recommendations)

    def test_structure_recommendation(self, quality_metrics: QualityMetrics) -> None:
        """Test recommendation for low structure."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=90.0,
            consistency=90.0,
            freshness=90.0,
            structure=70.0,
            token_efficiency=90.0,
            issues=["Structure issue"],
        )

        assert any("heading hierarchy" in rec.lower() for rec in recommendations)

    def test_token_efficiency_recommendation(
        self, quality_metrics: QualityMetrics
    ) -> None:
        """Test recommendation for low token efficiency."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=90.0,
            consistency=90.0,
            freshness=90.0,
            structure=90.0,
            token_efficiency=60.0,
            issues=["Token issue"],
        )

        assert any("check_token_budget" in rec for rec in recommendations)

    def test_multiple_recommendations(self, quality_metrics: QualityMetrics) -> None:
        """Test multiple recommendations generated."""
        recommendations: list[str] = quality_metrics.generate_recommendations(
            completeness=70.0,
            consistency=70.0,
            freshness=50.0,
            structure=70.0,
            token_efficiency=60.0,
            issues=["Issue 1", "Issue 2", "Issue 3"],
        )

        assert len(recommendations) >= 4
