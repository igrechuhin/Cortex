"""
Health-Check Operations Tool

This module exposes the health-check analysis system as an MCP tool.

Total: 1 tool
- analyze_health_check: Analyze prompts, rules, and/or tools for merge/optimization opportunities
"""

import json
from pathlib import Path
from typing import Literal

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.health_check.dependency_mapper import DependencyMapper
from cortex.health_check.models import (
    HealthCheckReport,
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
from cortex.server import mcp


def get_project_root(project_root: str | None) -> Path:
    """Resolve project root path."""
    if project_root:
        return Path(project_root).resolve()
    return Path.cwd()


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
        _collect_quality_issues(prompt_result["merge_opportunities"], recommendations)
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
        _collect_quality_issues(rule_result["merge_opportunities"], recommendations)
    rule_deps: dict[str, list[str]] | None = None
    if include_dependencies:
        rules = await rule_analyzer.get_rules_for_dependencies()
        rule_deps = await DependencyMapper(project_root).map_rule_dependencies(rules)
    return rule_result, recommendations, rule_deps


async def _run_tools_analysis(
    project_root: Path,
    similarity_engine: SimilarityEngine,
    validate_quality: bool,
) -> tuple[ToolAnalysisResult, list[str]]:
    """Run tool analysis and collect quality issues."""
    tools_dir = project_root / "src" / "cortex" / "tools"
    tool_analyzer = ToolAnalyzer(tools_dir, similarity_engine)
    tool_result = await tool_analyzer.analyze()
    recommendations: list[str] = []
    if validate_quality:
        _collect_quality_issues(tool_result["merge_opportunities"], recommendations)
    return tool_result, recommendations


def _build_report_json(
    report: HealthCheckReport,
    prompt_deps: dict[str, list[str]] | None,
    rule_deps: dict[str, list[str]] | None,
) -> str:
    """Build JSON string from report and optional dependency maps."""
    payload: dict[str, object] = dict(report)
    if prompt_deps is not None:
        payload["prompt_dependencies"] = prompt_deps
    if rule_deps is not None:
        payload["rule_dependencies"] = rule_deps
    return json.dumps(payload, indent=2)


async def _run_analyses_by_type(
    analysis_type: Literal["prompts", "rules", "tools", "all"],
    project_root: Path,
    se: SimilarityEngine,
    validate_quality: bool,
    include_dependencies: bool,
) -> tuple[
    PromptAnalysisResult,
    RuleAnalysisResult,
    ToolAnalysisResult,
    list[str],
    dict[str, list[str]] | None,
    dict[str, list[str]] | None,
]:
    """Run analyzers by analysis_type; return results, recs, and optional deps."""
    pr, rr, tr = empty_prompt_result(), empty_rule_result(), empty_tool_result()
    recs: list[str] = []
    pdeps: dict[str, list[str]] | None = None
    rdeps: dict[str, list[str]] | None = None
    if analysis_type in ("prompts", "all"):
        pr, recs, pdeps = await _run_prompts_analysis(
            project_root, se, validate_quality, include_dependencies
        )
    if analysis_type in ("rules", "all"):
        rr, r, rdeps = await _run_rules_analysis(
            project_root, se, validate_quality, include_dependencies
        )
        recs = recs + r
    if analysis_type in ("tools", "all"):
        tr, r = await _run_tools_analysis(project_root, se, validate_quality)
        recs = recs + r
    return pr, rr, tr, recs, pdeps, rdeps


async def run_health_check_analysis(
    analysis_type: Literal["prompts", "rules", "tools", "all"],
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
    report: HealthCheckReport = {
        "status": "success",
        "analysis_type": analysis_type,
        "prompts": pr,
        "rules": rr,
        "tools": tr,
        "recommendations": recs,
    }
    return _build_report_json(report, pdeps, rdeps)


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze_health_check(
    analysis_type: Literal["prompts", "rules", "tools", "all"] = "all",
    similarity_threshold: float = 0.75,
    include_dependencies: bool = True,
    validate_quality: bool = True,
    project_root: str | None = None,
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
    """
    root = get_project_root(project_root)
    await log_client(ctx, "info", "analyze_health_check: starting")
    result = await run_health_check_analysis(
        analysis_type=analysis_type,
        similarity_threshold=similarity_threshold,
        include_dependencies=include_dependencies,
        validate_quality=validate_quality,
        project_root=root,
    )
    await log_client(ctx, "info", "analyze_health_check: completed")
    return result
