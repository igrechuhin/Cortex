"""Run helpers for the analyze tool.

Extracted from analysis_operations to keep the main module within line limits.
"""

import json
from pathlib import Path

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.context.analysis_helpers import AnalysisTarget, parse_analysis_target
from cortex.tools.context.effectiveness_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)


async def analyze_usage_patterns(
    pattern_analyzer: PatternAnalyzer, time_window_days: int
) -> str:
    """Analyze usage patterns and return JSON response."""
    access_frequency = await pattern_analyzer.get_access_frequency(
        time_range_days=time_window_days
    )
    co_access = await pattern_analyzer.get_co_access_patterns(
        time_range_days=time_window_days
    )
    task_patterns = await pattern_analyzer.get_task_patterns(
        time_range_days=time_window_days
    )
    unused_files = await pattern_analyzer.get_unused_files(
        time_range_days=time_window_days
    )

    patterns = {
        "access_frequency": access_frequency,
        "co_access_patterns": co_access,
        "task_patterns": task_patterns,
        "unused_files": unused_files,
    }

    return json.dumps(
        {
            "status": "success",
            "target": "usage_patterns",
            "time_window_days": time_window_days,
            "patterns": patterns,
        },
        indent=2,
    )


async def analyze_structure(structure_analyzer: StructureAnalyzer) -> str:
    """Analyze structure and return JSON response."""
    organization = await structure_analyzer.analyze_file_organization()
    anti_patterns = await structure_analyzer.detect_anti_patterns()
    complexity = await structure_analyzer.measure_complexity_metrics()

    analysis = {
        "organization": organization.model_dump(mode="json"),
        "anti_patterns": [p.model_dump(mode="json") for p in anti_patterns],
        "complexity_metrics": complexity.model_dump(mode="json"),
    }

    return json.dumps(
        {"status": "success", "target": "structure", "analysis": analysis}, indent=2
    )


async def analyze_insights(
    insight_engine: InsightEngine, export_format: str, categories: list[str] | None
) -> str:
    """Analyze insights and return JSON response."""
    insights = await insight_engine.generate_insights(
        min_impact_score=0.5, categories=categories
    )
    if export_format == "markdown":
        exported = await insight_engine.export_insights(insights, format="markdown")
    elif export_format == "text":
        exported = await insight_engine.export_insights(insights, format="text")
    else:
        exported = insights.model_dump(mode="json")

    return json.dumps(
        {
            "status": "success",
            "target": "insights",
            "format": export_format,
            "insights": exported,
        },
        indent=2,
    )


async def get_analysis_managers(
    mgrs: ManagersDict,
) -> tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]:
    """Unwrap and return analysis managers."""
    pattern_analyzer = await get_manager(mgrs, "pattern_analyzer", PatternAnalyzer)
    structure_analyzer = await get_manager(
        mgrs, "structure_analyzer", StructureAnalyzer
    )
    insight_engine = await get_manager(mgrs, "insight_engine", InsightEngine)
    return pattern_analyzer, structure_analyzer, insight_engine


async def run_context_analysis(
    target: str,
    root: Path,
    *,
    max_sessions: int | None = None,
    max_calls_per_session: int | None = None,
) -> str:
    """Dispatch context-effectiveness and statistics analysis."""
    if target in ("context", "context_effectiveness"):
        result = analyze_current_session(
            root,
            max_response_calls=max_calls_per_session,
        )
        return json.dumps(result.model_dump(mode="json"), indent=2)
    if target in ("context_all_sessions", "context_effectiveness_all"):
        result = analyze_session_logs(root)
        return json.dumps(result.model_dump(mode="json"), indent=2)
    if target in ("context_stats", "context_statistics"):
        stats = get_context_statistics(root, max_recent_entries=max_sessions)
        return json.dumps(stats.model_dump(mode="json"), indent=2)
    return analysis_invalid_target_response(target)


async def run_health_analysis(root: Path, analysis_type: str = "all") -> str:
    """Run health-check analysis using the shared engine."""
    from cortex.tools.session.health_check_operations import (
        HealthCheckAnalysisType,
        run_health_check_analysis,
    )

    requested = analysis_type.strip().lower().replace("-", "_")
    if requested == "health_check":
        requested = "all"
    valid_types = {member.value for member in HealthCheckAnalysisType}
    resolved_type = requested if requested in valid_types else "all"

    return await run_health_check_analysis(
        analysis_type=HealthCheckAnalysisType(resolved_type),
        similarity_threshold=0.75,
        include_dependencies=True,
        validate_quality=True,
        project_root=root,
    )


def analysis_invalid_target_response(target_display: str) -> str:
    """Build JSON error response for invalid analysis target."""
    valid = [t.value for t in AnalysisTarget]
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid target: {target_display}",
            "valid_targets": valid,
        },
        indent=2,
    )


async def execute_analysis_target(
    target: AnalysisTarget,
    analyzers: tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine],
    time_window_days: int | None,
    export_format: str,
    categories: list[str] | None,
) -> str:
    """Run the analysis handler for the resolved target."""
    pattern_analyzer, structure_analyzer, insight_engine = analyzers
    if target == AnalysisTarget.USAGE_PATTERNS:
        window = time_window_days or 30
        return await analyze_usage_patterns(pattern_analyzer, window)
    if target == AnalysisTarget.STRUCTURE:
        return await analyze_structure(structure_analyzer)
    if target == AnalysisTarget.INSIGHTS:
        return await analyze_insights(insight_engine, export_format, categories)
    return analysis_invalid_target_response(target.value)


async def dispatch_analysis_target(
    target: str | AnalysisTarget,
    analyzers: tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine],
    time_window_days: int | None,
    export_format: str,
    categories: list[str] | None,
) -> str:
    """Dispatch analysis to appropriate handler based on target."""
    if not isinstance(target, AnalysisTarget):
        parsed = parse_analysis_target(target)
        if parsed is None:
            return analysis_invalid_target_response(target)
        target = parsed
    return await execute_analysis_target(
        target, analyzers, time_window_days, export_format, categories
    )
