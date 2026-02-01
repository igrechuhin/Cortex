"""Analyze captured session scripts for patterns and promotion potential."""

from cortex.script_analysis.gap_analyzer import analyze_gap
from cortex.script_analysis.models import (
    GapAnalysis,
    ScriptAnalysisResult,
    UseCaseExtraction,
)
from cortex.script_analysis.use_case_extractor import extract_use_case
from cortex.script_detection.models import ScriptCaptureRecord


def _reusability_score(use_case: UseCaseExtraction) -> float:
    """Estimate reusability from use-case clarity (0-1)."""
    if not use_case.use_case_label or use_case.use_case_label == "session script":
        return 0.2
    if use_case.keywords:
        return min(0.9, 0.3 + 0.1 * len(use_case.keywords[:10]))
    return 0.5


def _promotion_potential(
    reusability: float,
    gap: GapAnalysis,
) -> float:
    """Combine reusability and gap to estimate promotion potential (0-1)."""
    base = reusability
    if gap.is_gap:
        return min(1.0, base + 0.2)
    return max(0.0, base - 0.2)


def analyze_script(
    record: ScriptCaptureRecord,
    known_tool_names: list[str],
    known_script_names: list[str],
    gap_overlap_threshold: float = 0.3,
) -> ScriptAnalysisResult:
    """Analyze a captured script: use case, gap, and promotion potential.

    Args:
        record: Captured script record.
        known_tool_names: List of existing MCP tool names.
        known_script_names: List of existing Synapse script names (e.g. file stems).
        gap_overlap_threshold: Minimum overlap to consider tool/script as covering.

    Returns:
        ScriptAnalysisResult with use_case, gap, reusability_score,
        and promotion_potential.
    """
    use_case = extract_use_case(record)
    gap = analyze_gap(
        use_case,
        known_tool_names,
        known_script_names,
        overlap_threshold=gap_overlap_threshold,
    )
    reusability = _reusability_score(use_case)
    promotion = _promotion_potential(reusability, gap)

    return ScriptAnalysisResult(
        script_id=record.script_id,
        use_case=use_case,
        gap=gap,
        reusability_score=round(reusability, 4),
        promotion_potential=round(promotion, 4),
    )
