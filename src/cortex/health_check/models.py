"""Data models for health-check analysis."""

from enum import Enum

from pydantic import BaseModel, Field

from cortex.core.models import DictLikeModel


class QualityImpact(str, Enum):
    """Impact classification for a potential merge."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MergeOpportunity(DictLikeModel):
    """Represents a merge opportunity between files."""

    files: list[str]
    similarity: float
    merge_suggestion: str
    quality_impact: QualityImpact
    estimated_savings: str


class OptimizationOpportunity(DictLikeModel):
    """Represents an optimization opportunity."""

    file: str
    issue: str
    recommendation: str
    estimated_improvement: str


class PromptAnalysisResult(DictLikeModel):
    """Results from prompt analysis."""

    total: int
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]


class RuleAnalysisResult(DictLikeModel):
    """Results from rule analysis."""

    total: int
    categories: list[str]
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]


class ToolAnalysisResult(DictLikeModel):
    """Results from tool analysis."""

    total: int
    merge_opportunities: list[MergeOpportunity]
    optimization_opportunities: list[OptimizationOpportunity]
    consolidation_opportunities: list[MergeOpportunity]


type HealthCheckReport = dict[str, object]


class HealthCheckReportPayload(BaseModel):
    """JSON payload for health-check report (report + optional dependencies)."""

    status: str = Field(..., description="Report status")
    analysis_type: str = Field(..., description="prompts | rules | tools | all")
    prompts: PromptAnalysisResult = Field(..., description="Prompt analysis result")
    rules: RuleAnalysisResult = Field(..., description="Rule analysis result")
    tools: ToolAnalysisResult = Field(..., description="Tool analysis result")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )
    prompt_dependencies: dict[str, list[str]] | None = Field(
        None, description="Optional prompt dependency map"
    )
    rule_dependencies: dict[str, list[str]] | None = Field(
        None, description="Optional rule dependency map"
    )
