"""Type definitions for insight system.

This module contains shared type definitions used across the insight
analysis modules to avoid circular imports.
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.analysis.models import InsightEvidence, RecommendationEntry


class InsightDict(BaseModel):
    """Type definition for insight dictionary."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(description="Insight identifier")
    category: str = Field(description="Insight category")
    title: str = Field(description="Insight title")
    description: str = Field(description="Insight description")
    impact_score: float = Field(ge=0.0, le=1.0, description="Impact score (0-1)")
    severity: str = Field(description="Severity level")
    evidence: InsightEvidence | None = Field(
        default=None, description="Supporting evidence"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )
    estimated_token_savings: int = Field(ge=0, description="Estimated token savings")
    affected_files: list[str] = Field(
        default_factory=list, description="Affected file paths"
    )


class SummaryDict(BaseModel):
    """Type definition for summary dictionary."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Summary status")
    message: str = Field(description="Summary message")
    high_severity_count: int = Field(ge=0, description="High severity count")
    medium_severity_count: int = Field(ge=0, description="Medium severity count")
    low_severity_count: int = Field(ge=0, description="Low severity count")
    top_recommendations: list[RecommendationEntry] = Field(
        default_factory=lambda: list[RecommendationEntry](),
        description="Top recommendations",
    )


class InsightsResultDict(BaseModel):
    """Type definition for generate_insights return value."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    generated_at: str = Field(description="Generation timestamp")
    total_insights: int = Field(ge=0, description="Total number of insights")
    high_impact_count: int = Field(ge=0, description="High impact count")
    medium_impact_count: int = Field(ge=0, description="Medium impact count")
    low_impact_count: int = Field(ge=0, description="Low impact count")
    estimated_total_token_savings: int = Field(
        ge=0, description="Total estimated token savings"
    )
    insights: list[InsightDict] = Field(
        default_factory=lambda: list[InsightDict](),
        description="List of insights",
    )
    summary: SummaryDict = Field(description="Summary information")
