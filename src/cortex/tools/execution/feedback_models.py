"""
Models for provide_feedback tool results.
"""

from __future__ import annotations

from pydantic import Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class LearningSummary(StrictBaseModel):
    """Learning engine summary statistics."""

    total_feedback: int
    approval_rate: float
    min_confidence_threshold: float


class ProvideFeedbackResult(ToolResultBase):
    """Result of provide_feedback operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    feedback_id: str
    learning_enabled: bool
    message: str
    learning_summary: LearningSummary | None = None


class ProvideFeedbackErrorResult(ErrorResultBase):
    """Error result for provide_feedback operations."""

    suggestion_id: str | None = None
    feedback_type: str | None = None


ProvideFeedbackResultUnion = ProvideFeedbackResult | ProvideFeedbackErrorResult
