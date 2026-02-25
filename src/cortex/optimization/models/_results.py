"""Result models for optimization operations.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

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


class SummarizationResultModel(OptimizationBaseModel):
    """Result of summarizing file content."""

    original_tokens: int = Field(..., ge=0, description="Original token count")
    summary_tokens: int = Field(..., ge=0, description="Summary token count")
    reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Reduction percentage achieved"
    )
    summary: str = Field(..., description="Summarized content")
    strategy: str = Field(..., description="Strategy used for summarization")
    sections_kept: int = Field(default=0, ge=0, description="Number of sections kept")
    sections_removed: int = Field(
        default=0, ge=0, description="Number of sections removed"
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
