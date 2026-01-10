"""Type definitions for insight system.

This module contains shared type definitions used across the insight
analysis modules to avoid circular imports.
"""

from typing import TypedDict


class InsightDict(TypedDict, total=False):
    """Type definition for insight dictionary."""

    id: str
    category: str
    title: str
    description: str
    impact_score: float
    severity: str
    evidence: dict[str, object]
    recommendations: list[str]
    estimated_token_savings: int
    affected_files: list[str]


class SummaryDict(TypedDict, total=False):
    """Type definition for summary dictionary."""

    status: str
    message: str
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    top_recommendations: list[dict[str, object]]


class InsightsResultDict(TypedDict):
    """Type definition for generate_insights return value."""

    generated_at: str
    total_insights: int
    high_impact_count: int
    medium_impact_count: int
    low_impact_count: int
    estimated_total_token_savings: int
    insights: list[InsightDict]
    summary: SummaryDict
