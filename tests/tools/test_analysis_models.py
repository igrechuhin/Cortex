"""Tests for analysis_models module (analyze tool result types)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.tools.analysis_models import (
    AccessFrequencyData,
    AccessFrequencyPattern,
    AnalyzeErrorResult,
    AnalyzeInsightsResult,
    AnalyzeStructureResult,
    AnalyzeTarget,
    AnalyzeUsagePatternsResult,
    AntiPattern,
    CoAccessPatternEntry,
    ComplexityMetrics,
    InsightEntry,
    InsightsData,
    OrganizationMetrics,
    SeverityLevel,
    StructureAnalysis,
    TaskPatternData,
    UnusedFileData,
)


class TestSeverityLevel:
    """Test SeverityLevel enum."""

    def test_severity_values(self) -> None:
        assert SeverityLevel.HIGH.value == "high"
        assert SeverityLevel.MEDIUM.value == "medium"
        assert SeverityLevel.LOW.value == "low"


class TestAnalyzeTarget:
    """Test AnalyzeTarget enum."""

    def test_target_values(self) -> None:
        assert AnalyzeTarget.USAGE_PATTERNS.value == "usage_patterns"
        assert AnalyzeTarget.STRUCTURE.value == "structure"
        assert AnalyzeTarget.INSIGHTS.value == "insights"


class TestCoAccessPatternEntry:
    """Test CoAccessPatternEntry model."""

    def test_valid_entry(self) -> None:
        entry = CoAccessPatternEntry(
            files=["a.md", "b.md"],
            co_access_count=5,
            confidence=0.8,
        )
        assert entry.files == ["a.md", "b.md"]
        assert entry.co_access_count == 5
        assert entry.confidence == 0.8

    def test_rejects_negative_co_access_count(self) -> None:
        with pytest.raises(ValidationError):
            _ = CoAccessPatternEntry(
                files=["a.md"],
                co_access_count=-1,
                confidence=0.5,
            )

    def test_rejects_confidence_above_one(self) -> None:
        with pytest.raises(ValidationError):
            _ = CoAccessPatternEntry(
                files=["a.md"],
                co_access_count=1,
                confidence=1.5,
            )


class TestAccessFrequencyData:
    """Test AccessFrequencyData model."""

    def test_defaults(self) -> None:
        data = AccessFrequencyData()
        assert data.read_count == 0
        assert data.write_count == 0
        assert data.frequency == 0.0
        assert data.last_access is None

    def test_with_values(self) -> None:
        data = AccessFrequencyData(
            read_count=10,
            write_count=2,
            frequency=0.5,
            last_access="2026-02-01",
        )
        assert data.read_count == 10
        assert data.last_access == "2026-02-01"


class TestTaskPatternData:
    """Test TaskPatternData model."""

    def test_valid_entry(self) -> None:
        data = TaskPatternData(
            task_id="t1",
            description="Task",
            file_count=3,
            files=["a.md", "b.md"],
            timestamp="2026-02-01T12:00:00",
        )
        assert data.task_id == "t1"
        assert data.file_count == 3

    def test_defaults(self) -> None:
        data = TaskPatternData(
            task_id="t1",
            description="Task",
            timestamp="2026-02-01",
        )
        assert data.file_count == 0
        assert data.files == []


class TestUnusedFileData:
    """Test UnusedFileData model."""

    def test_valid_entry(self) -> None:
        data = UnusedFileData(
            file_name="old.md",
            days_since_access=30,
            last_access="2026-01-01",
            size_bytes=100,
            recommendation="Consider archiving",
        )
        assert data.file_name == "old.md"
        assert data.recommendation == "Consider archiving"

    def test_rejects_negative_days(self) -> None:
        with pytest.raises(ValidationError):
            _ = UnusedFileData(
                file_name="x.md",
                days_since_access=-1,
            )


class TestAccessFrequencyPattern:
    """Test AccessFrequencyPattern model."""

    def test_default_factories(self) -> None:
        pattern = AccessFrequencyPattern()
        assert pattern.access_frequency == {}
        assert pattern.co_access_patterns == []
        assert pattern.task_patterns == []
        assert pattern.unused_files == []

    def test_with_data(self) -> None:
        freq = AccessFrequencyData(read_count=1)
        co = CoAccessPatternEntry(files=["a", "b"], co_access_count=1, confidence=0.9)
        pattern = AccessFrequencyPattern(
            access_frequency={"f": freq},
            co_access_patterns=[co],
        )
        assert len(pattern.access_frequency) == 1
        assert len(pattern.co_access_patterns) == 1


class TestAntiPattern:
    """Test AntiPattern model (string severity coercion)."""

    def test_severity_from_string(self) -> None:
        ap = AntiPattern(
            type="oversized",
            path="foo.md",
            severity=SeverityLevel.HIGH,
            recommendation="Split file",
        )
        assert ap.severity == SeverityLevel.HIGH

    def test_severity_from_enum(self) -> None:
        ap = AntiPattern(
            type="oversized",
            path="foo.md",
            severity=SeverityLevel.LOW,
            recommendation="Split file",
        )
        assert ap.severity == SeverityLevel.LOW

    def test_optional_size_tokens(self) -> None:
        ap = AntiPattern(
            type="x",
            path="p",
            severity=SeverityLevel.MEDIUM,
            recommendation="r",
            size_tokens=1000,
        )
        assert ap.size_tokens == 1000


class TestOrganizationMetrics:
    """Test OrganizationMetrics model."""

    def test_valid(self) -> None:
        m = OrganizationMetrics(
            total_files=10,
            total_directories=3,
            max_depth=2,
            avg_files_per_directory=3.33,
        )
        assert m.total_files == 10
        assert m.max_depth == 2


class TestComplexityMetrics:
    """Test ComplexityMetrics model."""

    def test_valid(self) -> None:
        m = ComplexityMetrics(
            avg_directory_depth=1.5,
            max_dependencies=10,
            circular_dependencies=["a.py", "b.py"],
        )
        assert m.max_dependencies == 10
        assert len(m.circular_dependencies) == 2

    def test_rejects_negative_avg_depth(self) -> None:
        with pytest.raises(ValidationError):
            _ = ComplexityMetrics(
                avg_directory_depth=-1.0,
                max_dependencies=0,
            )


class TestStructureAnalysis:
    """Test StructureAnalysis model."""

    def test_valid(self) -> None:
        org = OrganizationMetrics(
            total_files=5,
            total_directories=2,
            max_depth=1,
            avg_files_per_directory=2.5,
        )
        complexity = ComplexityMetrics(
            avg_directory_depth=1.0,
            max_dependencies=0,
        )
        analysis = StructureAnalysis(
            organization=org,
            anti_patterns=[],
            complexity_metrics=complexity,
        )
        assert analysis.organization.total_files == 5
        assert analysis.anti_patterns == []


class TestInsightEntry:
    """Test InsightEntry model."""

    def test_valid(self) -> None:
        entry = InsightEntry(
            category="performance",
            description="Slow path",
            impact_score=0.8,
            recommendation="Optimize",
            affected_files=["a.py"],
        )
        assert entry.category == "performance"
        assert entry.affected_files == ["a.py"]


class TestInsightsData:
    """Test InsightsData model."""

    def test_default_factories(self) -> None:
        data = InsightsData()
        assert data.high_impact == []
        assert data.medium_impact == []
        assert data.low_impact == []

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            _ = InsightsData.model_validate({"extra_field": "not_allowed"})


class TestAnalyzeUsagePatternsResult:
    """Test AnalyzeUsagePatternsResult (target coercion)."""

    def test_target_default_and_string_coercion(self) -> None:
        patterns = AccessFrequencyPattern()
        result = AnalyzeUsagePatternsResult(
            time_window_days=7,
            patterns=patterns,
        )
        assert result.target == AnalyzeTarget.USAGE_PATTERNS
        assert getattr(result.status, "value", result.status) == "success"

    def test_from_dict_with_string_target(self) -> None:
        patterns = AccessFrequencyPattern()
        result = AnalyzeUsagePatternsResult.model_validate(
            {
                "status": "success",
                "target": "usage_patterns",
                "time_window_days": 14,
                "patterns": patterns.model_dump(),
            }
        )
        assert result.target == AnalyzeTarget.USAGE_PATTERNS


class TestAnalyzeStructureResult:
    """Test AnalyzeStructureResult."""

    def test_valid(self) -> None:
        org = OrganizationMetrics(
            total_files=1,
            total_directories=1,
            max_depth=0,
            avg_files_per_directory=1.0,
        )
        complexity = ComplexityMetrics(
            avg_directory_depth=0.0,
            max_dependencies=0,
        )
        analysis = StructureAnalysis(
            organization=org,
            anti_patterns=[],
            complexity_metrics=complexity,
        )
        result = AnalyzeStructureResult(analysis=analysis)
        assert result.target == AnalyzeTarget.STRUCTURE
        assert result.analysis.organization.total_files == 1


class TestAnalyzeInsightsResult:
    """Test AnalyzeInsightsResult."""

    def test_with_structured_insights(self) -> None:
        insights = InsightsData()
        result = AnalyzeInsightsResult(
            format="json",
            insights=insights,
        )
        assert result.target == AnalyzeTarget.INSIGHTS
        assert result.format == "json"
        assert isinstance(result.insights, InsightsData)

    def test_with_string_insights(self) -> None:
        result = AnalyzeInsightsResult(
            format="markdown",
            insights="# Summary\n\nText",
        )
        assert result.insights == "# Summary\n\nText"


class TestAnalyzeErrorResult:
    """Test AnalyzeErrorResult."""

    def test_with_target(self) -> None:
        err = AnalyzeErrorResult(
            error="Analysis failed",
            target="structure",
        )
        assert err.error == "Analysis failed"
        assert err.target == "structure"
        assert getattr(err.status, "value", err.status) == "error"

    def test_without_target(self) -> None:
        err = AnalyzeErrorResult(error="Unknown error")
        assert err.target is None
