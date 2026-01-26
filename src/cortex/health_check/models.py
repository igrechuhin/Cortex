"""Data models for health-check analysis."""

from typing import TypedDict


class MergeOpportunity(TypedDict):
    """Represents a merge opportunity between files."""

    files: list[str]
    similarity: float
    merge_suggestion: str
    quality_impact: str
    estimated_savings: str


class OptimizationOpportunity(TypedDict):
    """Represents an optimization opportunity."""

    file: str
    issue: str
    recommendation: str
    estimated_improvement: str


class PromptAnalysisResult(TypedDict):
    """Results from prompt analysis."""

    total: int
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]


class RuleAnalysisResult(TypedDict):
    """Results from rule analysis."""

    total: int
    categories: list[str]
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]


class ToolAnalysisResult(TypedDict):
    """Results from tool analysis."""

    total: int
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]
    consolidation_opportunities: list[MergeOpportunity]


class HealthCheckReport(TypedDict):
    """Comprehensive health-check report."""

    status: str
    analysis_type: str
    prompts: PromptAnalysisResult
    rules: RuleAnalysisResult
    tools: ToolAnalysisResult
    recommendations: list[str]
