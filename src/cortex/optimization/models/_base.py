"""Base and core optimization models.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID


class OptimizationBaseModel(DictLikeModel):
    """Base model for optimization types with strict validation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )


class OptimizationMetadata(OptimizationBaseModel):
    """Metadata for optimization result."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    task_description: str | None = Field(
        default=None, description="Task description used for optimization"
    )
    token_budget: int | None = Field(
        default=None, ge=0, description="Token budget used"
    )
    relevance_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Relevance threshold used"
    )
    processing_time_ms: float | None = Field(
        default=None, ge=0.0, description="Processing time in milliseconds"
    )
    relevance_scores: dict[str, float] | None = Field(
        default=None, description="Relevance scores per file"
    )
    error: str | None = Field(default=None, description="Error message if any")
    phase1_files: int | None = Field(
        default=None, ge=0, description="Number of files from phase 1"
    )
    phase2_files: int | None = Field(
        default=None, ge=0, description="Number of files from phase 2"
    )
    phase2_sections: int | None = Field(
        default=None, ge=0, description="Number of sections from phase 2"
    )


class OptimizationResultModel(OptimizationBaseModel):
    """Result of context optimization."""

    selected_files: list[str] = Field(
        default_factory=list, description="Files selected for context"
    )
    selected_sections: dict[str, list[str]] = Field(
        default_factory=dict, description="Sections selected per file"
    )
    total_tokens: int = Field(..., ge=0, description="Total token count")
    utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Budget utilization 0-1"
    )
    excluded_files: list[str] = Field(
        default_factory=list, description="Files excluded from context"
    )
    strategy_used: str = Field(..., description="Strategy used for optimization")
    metadata: OptimizationMetadata = Field(
        default_factory=OptimizationMetadata, description="Additional metadata"
    )
