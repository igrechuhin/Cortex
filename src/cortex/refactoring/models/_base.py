"""
Refactoring base models and common types.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel, RiskLevel
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID


class RefactoringBaseModel(DictLikeModel):
    """Base model for refactoring types with strict validation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Common Metric Models
# ============================================================================


class RefactoringImpactMetrics(RefactoringBaseModel):
    """Estimated impact metrics for refactoring operations."""

    # token_savings may be negative when a refactoring increases token usage.
    token_savings: int = Field(
        default=0,
        description="Estimated token savings (positive) or increase (negative)",
    )
    files_affected: int = Field(default=0, ge=0, description="Number of files affected")
    operations_completed: int = Field(
        default=0, ge=0, description="Number of operations completed"
    )
    # complexity_reduction may be negative when complexity increases.
    complexity_reduction: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Complexity reduction factor (negative means increase)",
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Risk level")
    maintainability_improvement: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Maintainability improvement factor",
    )


class RefactoringMetadata(RefactoringBaseModel):
    """Metadata for refactoring suggestions."""

    source: str | None = Field(default=None, description="Source of suggestion")
    analyzer_version: str | None = Field(default=None, description="Analyzer version")
    confidence_factors: list[str] = Field(
        default_factory=list, description="Factors affecting confidence"
    )
    related_suggestions: list[str] = Field(
        default_factory=list, description="Related suggestion IDs"
    )
    insight_category: str | None = Field(
        default=None, description="Insight category if from insight"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations from insight"
    )


class ActionDetails(RefactoringBaseModel):
    """Details for a refactoring action."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    source_file: str | None = Field(default=None, description="Source file path")
    source_files: list[str] | None = Field(
        default=None, description="List of source files for consolidation"
    )
    destination_file: str | None = Field(
        default=None, description="Destination file path"
    )
    content: str | None = Field(default=None, description="Content to add/modify")
    section: str | None = Field(default=None, description="Target section")
    sections: list[str] | None = Field(
        default=None, description="List of sections to operate on"
    )
    line_start: int | None = Field(default=None, ge=1, description="Start line number")
    line_end: int | None = Field(default=None, ge=1, description="End line number")
    heading1: str | None = Field(
        default=None, description="First heading for consolidation"
    )
    heading2: str | None = Field(
        default=None, description="Second heading for consolidation"
    )
    differences: list[str] | None = Field(
        default=None, description="Content differences"
    )
    size: int | None = Field(default=None, ge=0, description="Size in bytes")
    token_count: int | None = Field(default=None, ge=0, description="Token count")
    # Consolidation-specific fields
    extraction_method: str | None = Field(
        default=None, description="Method used for extraction"
    )
    transclusion_target: str | None = Field(
        default=None, description="Target file for transclusion"
    )
    replace_duplicates: bool | None = Field(
        default=None, description="Whether to replace duplicates"
    )
    # Split-specific fields
    split_strategy: str | None = Field(
        default=None, description="Strategy for splitting files"
    )
    add_links: bool | None = Field(
        default=None, description="Whether to add links to split files"
    )
    create_index: bool | None = Field(
        default=None, description="Whether to create an index file"
    )
    # Reorganization-specific fields
    affected_files: list[str] | None = Field(
        default=None, description="Files affected by reorganization"
    )
    new_structure: str | None = Field(
        default=None, description="New directory structure"
    )
    preserve_links: bool | None = Field(
        default=None, description="Whether to preserve existing links"
    )
    add_dependencies: bool | None = Field(
        default=None, description="Whether to add dependencies"
    )
