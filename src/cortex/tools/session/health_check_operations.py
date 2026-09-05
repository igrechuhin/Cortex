"""
Health-Check Operations Tool

This module exposes the health-check analysis system as an MCP tool.

Total: 1 tool
- analyze_health_check: Analyze prompts, rules, and/or tools for merge/optimization opportunities
"""

from enum import Enum
from pathlib import Path

import cortex.tools
from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.health_check.dependency_mapper import DependencyMapper
from cortex.health_check.models import (
    HealthCheckReport,
    HealthCheckReportPayload,
    MergeOpportunity,
    PromptAnalysisResult,
    RuleAnalysisResult,
    ToolAnalysisResult,
)
from cortex.health_check.prompt_analyzer import PromptAnalyzer
from cortex.health_check.quality_validator import QualityValidator
from cortex.health_check.rule_analyzer import RuleAnalyzer
from cortex.health_check.similarity_engine import SimilarityEngine
from cortex.health_check.tool_analyzer import ToolAnalyzer
from cortex.managers.initialization import get_project_root as _get_project_root


def get_project_root(project_root: str | None) -> Path:
    """Resolve project root for the health-check CLI (python -m cortex.health_check)."""
    return _get_project_root(project_root)


def empty_prompt_result() -> PromptAnalysisResult:
    """Return empty prompt analysis result."""
    return PromptAnalysisResult(
        total=0,
        merge_opportunities=[],
        optimization_opportunities=[],
    )


def empty_rule_result() -> RuleAnalysisResult:
    """Return empty rule analysis result."""
    return RuleAnalysisResult(
        total=0,
        categories=[],
        merge_opportunities=[],
        optimization_opportunities=[],
    )


def empty_tool_result() -> ToolAnalysisResult:
    """Return empty tool analysis result."""
    return ToolAnalysisResult(
        total=0,
        merge_opportunities=[],
        optimization_opportunities=[],
        consolidation_opportunities=[],
    )


def _collect_quality_issues(
    opportunities: list[MergeOpportunity], recommendations: list[str]
) -> None:
    """Append quality validator issues for merge opportunities to recommendations."""
    for opp in opportunities:
        val = QualityValidator().validate_merge(opp)
        if not val.get("valid"):
            issues = val.get("issues")
            if isinstance(issues, list):
                recommendations.extend(str(x) for x in issues)


async def _run_prompts_analysis(
    project_root: Path,
    similarity_engine: SimilarityEngine,
    validate_quality: bool,
    include_dependencies: bool,
) -> tuple[PromptAnalysisResult, list[str], dict[str, list[str]] | None]:
    """Run prompt analysis and optional dependency mapping."""
    prompt_analyzer = PromptAnalyzer(project_root, similarity_engine)
    prompt_result = await prompt_analyzer.analyze()
    recommendations: list[str] = []
    if validate_quality:
        _collect_quality_issues(prompt_result.merge_opportunities, recommendations)
    prompt_deps: dict[str, list[str]] | None = None
    if include_dependencies:
        prompts = await prompt_analyzer.get_prompts_for_dependencies()
        prompt_deps = await DependencyMapper(project_root).map_prompt_dependencies(
            prompts
        )
    return prompt_result, recommendations, prompt_deps


async def _run_rules_analysis(
    project_root: Path,
    similarity_engine: SimilarityEngine,
    validate_quality: bool,
    include_dependencies: bool,
) -> tuple[RuleAnalysisResult, list[str], dict[str, list[str]] | None]:
    """Run rule analysis and optional dependency mapping."""
    rule_analyzer = RuleAnalyzer(project_root, similarity_engine)
    rule_result = await rule_analyzer.analyze()
    recommendations: list[str] = []
    if validate_quality:
        _collect_quality_issues(rule_result.merge_opportunities, recommendations)
    rule_deps: dict[str, list[str]] | None = None
    if include_dependencies:
        rules = await rule_analyzer.get_rules_for_dependencies()
        rule_deps = await DependencyMapper(project_root).map_rule_dependencies(rules)
    return rule_result, recommendations, rule_deps


def get_tools_dir() -> Path:
    """Resolve the directory holding Cortex's MCP tool modules.

    Returns:
        Path to the installed `cortex.tools` package
    """
    # AI: resolve from the imported package, not project_root — the repo-relative
    # src/cortex/tools layout only exists in the Cortex repo itself, so consuming
    # projects reported zero tools.
    return Path(cortex.tools.__file__).parent


async def _run_tools_analysis(
    similarity_engine: SimilarityEngine,
    validate_quality: bool,
) -> tuple[ToolAnalysisResult, list[str]]:
    """Run tool analysis and collect quality issues."""
    tool_analyzer = ToolAnalyzer(get_tools_dir(), similarity_engine)
    tool_result = await tool_analyzer.analyze()
    recommendations: list[str] = []
    if validate_quality:
        _collect_quality_issues(tool_result.merge_opportunities, recommendations)
    return tool_result, recommendations


def _build_report_json(
    report: HealthCheckReport,
    prompt_deps: dict[str, list[str]] | None,
    rule_deps: dict[str, list[str]] | None,
) -> str:
    """Build JSON string from report and optional dependency maps."""
    payload = report.model_copy(
        update={
            "prompt_dependencies": prompt_deps,
            "rule_dependencies": rule_deps,
        }
    )
    return payload.model_dump_json(indent=2)


class HealthCheckAnalysisType(str, Enum):
    """Type of health-check analysis."""

    PROMPTS = "prompts"
    RULES = "rules"
    TOOLS = "tools"
    ALL = "all"


_AnalysesByTypeResult = tuple[
    PromptAnalysisResult,
    RuleAnalysisResult,
    ToolAnalysisResult,
    list[str],
    dict[str, list[str]] | None,
    dict[str, list[str]] | None,
]


async def _run_analyses_impl(
    at: str,
    project_root: Path,
    se: SimilarityEngine,
    validate_quality: bool,
    include_dependencies: bool,
) -> _AnalysesByTypeResult:
    """Run analyzers for given type; return results, recs, and optional deps."""
    pr, rr, tr = empty_prompt_result(), empty_rule_result(), empty_tool_result()
    recs: list[str] = []
    pdeps: dict[str, list[str]] | None = None
    rdeps: dict[str, list[str]] | None = None
    if at in ("prompts", "all"):
        pr, recs, pdeps = await _run_prompts_analysis(
            project_root, se, validate_quality, include_dependencies
        )
    if at in ("rules", "all"):
        rr, r, rdeps = await _run_rules_analysis(
            project_root, se, validate_quality, include_dependencies
        )
        recs = recs + r
    if at in ("tools", "all"):
        tr, r = await _run_tools_analysis(se, validate_quality)
        recs = recs + r
    return pr, rr, tr, recs, pdeps, rdeps


async def _run_analyses_by_type(
    analysis_type: HealthCheckAnalysisType | str,
    project_root: Path,
    se: SimilarityEngine,
    validate_quality: bool,
    include_dependencies: bool,
) -> _AnalysesByTypeResult:
    """Run analyzers by analysis_type; return results, recs, and optional deps."""
    at = (
        analysis_type.value
        if isinstance(analysis_type, HealthCheckAnalysisType)
        else analysis_type
    )
    return await _run_analyses_impl(
        at, project_root, se, validate_quality, include_dependencies
    )


async def run_health_check_analysis(
    analysis_type: HealthCheckAnalysisType | str,
    similarity_threshold: float,
    include_dependencies: bool,
    validate_quality: bool,
    project_root: Path,
) -> str:
    """Run health-check analysis and return JSON report."""
    se = SimilarityEngine(high_threshold=similarity_threshold)
    pr, rr, tr, recs, pdeps, rdeps = await _run_analyses_by_type(
        analysis_type, project_root, se, validate_quality, include_dependencies
    )
    at_str = (
        analysis_type.value
        if isinstance(analysis_type, HealthCheckAnalysisType)
        else analysis_type
    )
    report: HealthCheckReport = HealthCheckReportPayload(
        status="success",
        analysis_type=at_str,
        prompts=pr,
        rules=rr,
        tools=tr,
        recommendations=recs,
        prompt_dependencies=None,
        rule_dependencies=None,
    )
    return _build_report_json(report, pdeps, rdeps)


async def analyze_health_check(
    analysis_type: HealthCheckAnalysisType | str = HealthCheckAnalysisType.ALL,
    similarity_threshold: float = 0.75,
    include_dependencies: bool = True,
    validate_quality: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze prompts, rules, and/or MCP tools for merge and optimization opportunities.

    USE WHEN: User wants health-check analysis of prompts, rules, or tools;
    user wants merge/optimization suggestions; user wants dependency mapping.

    EXAMPLES: 'analyze health check for all', 'analyze prompts only with
    threshold 0.8', 'run health check with dependencies'.

    RETURNS: JSON with status, analysis_type, prompts/rules/tools sections,
    merge_opportunities, optimization_opportunities, recommendations, and
    optional prompt_dependencies/rule_dependencies.

    Args:
        analysis_type: Scope of analysis. "prompts", "rules", "tools", or "all"
            (default). Only the selected layer(s) are analyzed.
        similarity_threshold: Similarity threshold for merge detection (0.0–1.0).
            Default 0.75. Higher values require stronger similarity to suggest merges.
        include_dependencies: If True, include prompt/rule dependency mapping
            in the report. Default True.
        validate_quality: If True, run quality validation on merge opportunities
            and append recommendations. Default True.
        ctx: MCP context (automatically provided).
    """
    await log_client(ctx, "info", "analyze_health_check: starting")
    root = await resolve_project_root_async(None, ctx)
    result = await run_health_check_analysis(
        analysis_type=analysis_type,
        similarity_threshold=similarity_threshold,
        include_dependencies=include_dependencies,
        validate_quality=validate_quality,
        project_root=root,
    )
    await log_client(ctx, "info", "analyze_health_check: completed")
    return result


# Phase 43: Health check resource (read-only, template param)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze_health_check_resource(analysis_type: str) -> str:
    """Resource: Health-check analysis (default params). Read via cortex://health/analyze/{analysis_type}. analysis_type: prompts, rules, tools, or all."""
    valid_str = (
        analysis_type
        if analysis_type in ("prompts", "rules", "tools", "all")
        else "all"
    )
    root = await resolve_project_root_async(None, None)
    return await run_health_check_analysis(
        analysis_type=valid_str,
        similarity_threshold=0.75,
        include_dependencies=True,
        validate_quality=True,
        project_root=root,
    )
