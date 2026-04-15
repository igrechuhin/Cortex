"""Shared structure-analyzer mocks for analysis operation tests."""

from unittest.mock import AsyncMock, MagicMock

from cortex.analysis.models import (
    AntiPatternInfo,
    AntiPatternKind,
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    ComplexityMetrics,
    SeverityLevel,
)
from cortex.core.models import FileOrganizationResult


def naming_inconsistency_anti_pattern() -> AntiPatternInfo:
    """Single low-severity naming anti-pattern (structure tests)."""
    return AntiPatternInfo(
        type=AntiPatternKind.NAMING_INCONSISTENCY,
        severity=SeverityLevel.LOW,
        description="Naming inconsistency",
    )


def structure_analyzer_mock(
    *,
    file_count: int = 1,
    anti_patterns: list[AntiPatternInfo] | None = None,
    max_dependency_depth: int = 2,
) -> MagicMock:
    """MagicMock structure_analyzer with AsyncMock analyze/detect/measure methods."""
    m = MagicMock()
    m.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(
            status=ComplexityAnalysisStatus.ANALYZED,
            file_count=file_count,
        )
    )
    m.detect_anti_patterns = AsyncMock(return_value=list(anti_patterns or []))
    m.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(
            status=ComplexityAnalysisStatus.ANALYZED,
            metrics=ComplexityMetrics(max_dependency_depth=max_dependency_depth),
        )
    )
    return m
