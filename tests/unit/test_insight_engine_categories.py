"""Category-specific tests for insight_engine insight generation."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
import pytest_mock

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.models import (
    AntiPatternInfo,
    AntiPatternKind,
    CoAccessPattern,
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    ComplexityAssessment,
    ComplexityAssessmentStatus,
    ComplexityHotspot,
    ComplexityMetrics,
    SeverityLevel,
)
from cortex.analysis.pattern_types import UnusedFileEntry
from cortex.core.models import FileOrganizationResult, FileSizeEntry
from cortex.structure.models import HealthGrade


def _build_engine(
    mocker: pytest_mock.MockerFixture,
    *,
    unused_files: list[UnusedFileEntry] | None = None,
    co_access_patterns: list[CoAccessPattern] | None = None,
    organization_result: FileOrganizationResult | None = None,
    anti_patterns: list[AntiPatternInfo] | None = None,
    complexity_result: ComplexityAnalysisResult | None = None,
) -> InsightEngine:
    pattern = mocker.MagicMock()
    pattern.get_unused_files = AsyncMock(return_value=unused_files or [])
    pattern.get_co_access_patterns = AsyncMock(return_value=co_access_patterns or [])

    structure = mocker.MagicMock()
    structure.analyze_file_organization = AsyncMock(
        return_value=organization_result
        or FileOrganizationResult(
            status=ComplexityAnalysisStatus.NO_FILES, file_count=0
        )
    )
    structure.detect_anti_patterns = AsyncMock(return_value=anti_patterns or [])
    structure.measure_complexity_metrics = AsyncMock(
        return_value=complexity_result
        or ComplexityAnalysisResult(status=ComplexityAnalysisStatus.NO_FILES)
    )
    return InsightEngine(pattern, structure)


async def _get_insight(
    engine: InsightEngine, category: str, insight_id: str
) -> dict[str, object]:
    result = (await engine.generate_insights(categories=[category])).model_dump(
        mode="json"
    )
    insights_raw = result["insights"]
    assert isinstance(insights_raw, list)
    insights = cast(list[dict[str, object]], insights_raw)
    matches = [item for item in insights if item.get("id") == insight_id]
    assert len(matches) == 1
    return matches[0]


class TestUsageInsights:
    """Tests for usage pattern insights."""

    @pytest.mark.asyncio
    async def test_detects_unused_files_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for unused files."""
        engine = _build_engine(
            mocker,
            unused_files=[
                UnusedFileEntry(
                    file="unused1.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused2.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused3.md",
                    status="never_accessed",
                    total_accesses=0,
                    last_access=None,
                ),
            ],
        )
        insight = await _get_insight(engine, "usage", "unused_files")
        assert insight["category"] == "usage"
        assert insight["severity"] == "medium"
        assert "unused" in str(insight["title"]).lower()
        assert len(cast(list[str], insight["recommendations"])) > 0

    @pytest.mark.asyncio
    async def test_detects_co_access_patterns_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for co-access patterns."""
        engine = _build_engine(
            mocker,
            co_access_patterns=[
                CoAccessPattern(file_1=f"file{i}.md", file_2=f"file{i + 1}.md")
                for i in range(5)
            ],
        )
        insight = await _get_insight(engine, "usage", "co_access_patterns")
        assert insight["category"] == "usage"
        assert insight["severity"] == "low"
        assert "co-accessed" in str(insight["title"]).lower()


class TestOrganizationInsights:
    """Tests for organization insights."""

    @pytest.mark.asyncio
    async def test_detects_large_files_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for large files."""
        engine = _build_engine(
            mocker,
            organization_result=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                file_count=3,
                issues=["3 files very large"],
                largest_files=[
                    FileSizeEntry(file="large1.md", size_bytes=100000, tokens=0),
                    FileSizeEntry(file="large2.md", size_bytes=90000, tokens=0),
                    FileSizeEntry(file="large3.md", size_bytes=80000, tokens=0),
                ],
                smallest_files=[],
            ),
        )
        insight = await _get_insight(engine, "organization", "large_files")
        assert insight["category"] == "organization"
        assert insight["severity"] == "medium"
        assert "large" in str(insight["title"]).lower()

    @pytest.mark.asyncio
    async def test_detects_small_files_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for small files."""
        engine = _build_engine(
            mocker,
            organization_result=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                file_count=5,
                issues=["5 files very small"],
                largest_files=[],
                smallest_files=[
                    FileSizeEntry(file=f"small{i}.md", size_bytes=300, tokens=0)
                    for i in range(5)
                ],
            ),
        )
        insight = await _get_insight(engine, "organization", "small_files")
        assert insight["category"] == "organization"
        assert insight["severity"] == "low"
        assert "small" in str(insight["title"]).lower()


class TestRedundancyInsights:
    """Tests for redundancy insights."""

    @pytest.mark.asyncio
    async def test_detects_similar_filenames_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for similar filenames."""
        engine = _build_engine(
            mocker,
            anti_patterns=[
                AntiPatternInfo(
                    type=AntiPatternKind.SIMILAR_FILENAMES,
                    file="test1.md",
                    files=["test1.md", "test2.md"],
                    severity=SeverityLevel.MEDIUM,
                    description="Similar filenames detected",
                ),
                AntiPatternInfo(
                    type=AntiPatternKind.SIMILAR_FILENAMES,
                    file="doc1.md",
                    files=["doc1.md", "doc2.md"],
                    severity=SeverityLevel.MEDIUM,
                    description="Similar filenames detected",
                ),
            ],
        )
        insight = await _get_insight(engine, "redundancy", "similar_filenames")
        assert insight["category"] == "redundancy"
        assert insight["severity"] == "medium"
        assert "similar" in str(insight["title"]).lower()


class TestDependencyInsights:
    """Tests for dependency insights."""

    @pytest.mark.asyncio
    async def test_detects_complexity_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for dependency complexity."""
        engine = _build_engine(
            mocker,
            complexity_result=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                metrics=ComplexityMetrics(max_dependency_depth=8),
                complexity_hotspots=[ComplexityHotspot(file="complex.md", score=50.0)],
                assessment=ComplexityAssessment(
                    score=55,
                    grade=HealthGrade.D,
                    status=ComplexityAssessmentStatus.POOR,
                    issues=["High complexity"],
                    recommendations=["Reduce dependencies"],
                ),
            ),
        )
        insight = await _get_insight(engine, "dependencies", "dependency_complexity")
        assert insight["category"] == "dependencies"
        assert insight["severity"] in ["high", "medium"]
        assert "complexity" in str(insight["title"]).lower()

    @pytest.mark.asyncio
    async def test_detects_orphaned_files_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for orphaned files."""
        engine = _build_engine(
            mocker,
            anti_patterns=[
                AntiPatternInfo(
                    type=AntiPatternKind.ORPHANED_FILE,
                    file="orphan1.md",
                    files=["orphan1.md"],
                    severity=SeverityLevel.MEDIUM,
                    description="Orphaned file detected",
                ),
                AntiPatternInfo(
                    type=AntiPatternKind.ORPHANED_FILE,
                    file="orphan2.md",
                    files=["orphan2.md"],
                    severity=SeverityLevel.MEDIUM,
                    description="Orphaned file detected",
                ),
            ],
        )
        insight = await _get_insight(engine, "dependencies", "orphaned_files")
        assert insight["category"] == "dependencies"
        assert insight["severity"] == "medium"
        assert "orphaned" in str(insight["title"]).lower()
