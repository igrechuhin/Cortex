"""Result models for optimization operations.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

from enum import Enum

from pydantic import Field

from ._base import OptimizationBaseModel


class ProgressiveLoadResult(OptimizationBaseModel):
    """Result of progressive loading operation."""

    loaded_files: dict[str, str] = Field(
        default_factory=dict, description="Loaded file contents by name"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens loaded")
    files_count: int = Field(default=0, ge=0, description="Number of files loaded")
    budget_remaining: int | None = Field(
        default=None, description="Remaining token budget"
    )
    truncated: bool = Field(
        default=False, description="Whether loading was truncated due to budget"
    )
    loading_order: list[str] = Field(
        default_factory=list, description="Order in which files were loaded"
    )


class DropReason(str, Enum):
    """Why a section was excluded from a summary.

    # AI: one real value, not a speculative taxonomy -- BUDGET_EXCEEDED is
    # the only reason `select_sections_by_budget` can currently produce.
    # A future scorer-driven or validation-driven reason adds a member here
    # without needing a schema migration (the field type stays DropReason).
    """

    BUDGET_EXCEEDED = "budget_exceeded"


class DroppedSection(OptimizationBaseModel):
    """A section excluded from a summary, with its scoring provenance."""

    name: str = Field(..., description="Section name/heading")
    score: float = Field(..., ge=0.0, le=1.0, description="Importance score")
    tokens: int = Field(..., ge=0, description="Token count of the dropped section")
    reason: DropReason = Field(..., description="Why this section was excluded")


class SummarizationResultModel(OptimizationBaseModel):
    """Result of summarizing file content."""

    original_tokens: int = Field(..., ge=0, description="Original token count")
    summary_tokens: int = Field(..., ge=0, description="Summary token count")
    reduction: float = Field(
        ...,
        le=1.0,
        description="Reduction ratio achieved; negative means content grew",
    )
    summary: str = Field(..., description="Summarized content")
    strategy: str = Field(..., description="Strategy used for summarization")
    sections_kept: int = Field(default=0, ge=0, description="Number of sections kept")
    sections_removed: int = Field(
        default=0, ge=0, description="Number of sections removed"
    )
    file_name: str | None = Field(
        default=None, description="Name of the summarized file, if known"
    )
    met_target: bool = Field(
        default=False,
        description=(
            "Whether the achieved reduction met target_reduction (minus "
            "tolerance); not meaningful when skipped_reason is set. Defaults "
            "to False: the engine does not know the target, only the gating "
            "tool layer sets this, and an ungated result must never claim to "
            "have passed a check that never ran"
        ),
    )
    skipped_reason: str | None = Field(
        default=None, description="Why this file could not be summarized, if skipped"
    )
    rejected_reason: str | None = Field(
        default=None,
        description=(
            "Why `summary` was blanked; set whenever met_target is False so "
            "a caller ignoring `status` cannot consume a rejected summary"
        ),
    )
    dropped_sections: list[DroppedSection] = Field(
        default_factory=list[DroppedSection],
        description="Sections excluded from the summary, with score and size",
    )


class RulesIndexResultModel(OptimizationBaseModel):
    """Result of rules indexing operation."""

    status: str = Field(..., description="Indexing status: indexed, cached, error")
    rules_count: int = Field(default=0, ge=0, description="Number of rules indexed")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens in rules")
    cache_hit: bool = Field(default=False, description="Whether cache was used")
    index_time_seconds: float = Field(
        default=0.0, ge=0.0, description="Time taken to index"
    )
    rules_by_category: dict[str, int] = Field(
        default_factory=dict, description="Rules count by category"
    )


class IndexingResultModel(OptimizationBaseModel):
    """Result of indexing a single rule file."""

    status: str = Field(..., description="Status: indexed, updated, unchanged, error")
    file_key: str | None = Field(default=None, description="File key if successful")
    error: str | None = Field(default=None, description="Error message if failed")


class IndexingSkipResultModel(OptimizationBaseModel):
    """Result when indexing is skipped."""

    status: str = Field(default="skipped", description="Status")
    message: str = Field(..., description="Skip reason message")
    last_indexed: str | None = Field(
        default=None, description="ISO timestamp of last indexing"
    )
    next_index_in_seconds: int | None = Field(
        default=None, ge=0, description="Seconds until next indexing"
    )


class IndexingBatchResultModel(OptimizationBaseModel):
    """Result of indexing multiple rule files."""

    indexed_files: list[str] = Field(
        default_factory=list, description="Newly indexed files"
    )
    updated_files: list[str] = Field(default_factory=list, description="Updated files")
    unchanged_files: list[str] = Field(
        default_factory=list, description="Unchanged files"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")


class RulesIndexingResultModel(OptimizationBaseModel):
    """Result of rules indexing operation (file-level details)."""

    status: str = Field(..., description="Indexing status")
    rules_folder: str = Field(..., description="Rules folder path")
    total_files: int = Field(default=0, ge=0, description="Total files found")
    indexed_files: list[str] = Field(
        default_factory=list, description="Newly indexed files"
    )
    updated_files: list[str] = Field(default_factory=list, description="Updated files")
    unchanged_files: list[str] = Field(
        default_factory=list, description="Unchanged files"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")
    message: str | None = Field(default=None, description="Status message")
