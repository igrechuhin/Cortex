"""
Auxiliary context models: dependency graph, transclusions, progressive loading,
relevance scores, summarize content.

Used by get_dependency_graph, resolve_transclusions, load_progressive_context,
get_relevance_scores, summarize_content. Extracted from context_models to keep
files under 400 lines.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


def _coerce_str_enum[E: Enum](v: str | Enum, enum_cls: type[E]) -> E:
    """Coerce string to enum for Pydantic (e.g. from JSON or dict input)."""
    if isinstance(v, enum_cls):
        return v
    return enum_cls(v)


class DependencyGraphFormat(str, Enum):
    """Dependency graph output format."""

    JSON = "json"
    MERMAID = "mermaid"


_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]
_DependencyGraphFormatField = Annotated[
    DependencyGraphFormat,
    BeforeValidator(lambda x: _coerce_str_enum(x, DependencyGraphFormat)),
]

# ============================================================================
# get_dependency_graph
# ============================================================================


class FileDependencyInfoModel(StrictBaseModel):
    """File dependency information in graph."""

    priority: int
    dependencies: list[str] = Field(default_factory=list)


class DependencyGraphData(StrictBaseModel):
    """Dependency graph data structure."""

    files: dict[str, FileDependencyInfoModel] = Field(default_factory=dict)


class GetDependencyGraphJsonResult(ToolResultBase):
    """Result of get_dependency_graph operation (JSON format)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    format: _DependencyGraphFormatField = Field(default=DependencyGraphFormat.JSON)
    graph: DependencyGraphData
    loading_order: list[str] = Field(default_factory=list)


class GetDependencyGraphMermaidResult(ToolResultBase):
    """Result of get_dependency_graph operation (Mermaid format)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    format: _DependencyGraphFormatField = Field(default=DependencyGraphFormat.MERMAID)
    diagram: str


class GetDependencyGraphErrorResult(ErrorResultBase):
    """Error result for get_dependency_graph operations."""

    format: str | None = None


GetDependencyGraphResult = (
    GetDependencyGraphJsonResult
    | GetDependencyGraphMermaidResult
    | GetDependencyGraphErrorResult
)

# ============================================================================
# resolve_transclusions
# ============================================================================


class CacheStats(StrictBaseModel):
    """Cache statistics for transclusion resolution."""

    hits: int
    misses: int
    size: int


class ResolveTransclusionsResult(ToolResultBase):
    """Result of resolve_transclusions operation (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    file: str
    original_content: str
    resolved_content: str
    has_transclusions: bool
    cache_stats: CacheStats | None = None
    message: str | None = None


class ResolveTransclusionsErrorResult(ErrorResultBase):
    """Error result for resolve_transclusions operations."""

    file: str | None = None
    message: str | None = None


ResolveTransclusionsResultUnion = (
    ResolveTransclusionsResult | ResolveTransclusionsErrorResult
)

# ============================================================================
# load_progressive_context
# ============================================================================


class LoadedFileInfo(StrictBaseModel):
    """Information about a loaded file in progressive context."""

    file_name: str
    tokens: int
    cumulative_tokens: int
    priority: int | None = None
    relevance_score: float | None = None
    more_available: bool = False


class LoadProgressiveContextResult(ToolResultBase):
    """Result of load_progressive_context operation (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    task_description: str
    loading_strategy: str
    token_budget: int
    files_loaded: int
    total_tokens: int
    loaded_files: list[LoadedFileInfo]


class LoadProgressiveContextErrorResult(ErrorResultBase):
    """Error result for load_progressive_context operations."""

    loading_strategy: str | None = None
    token_budget: int | None = None


LoadProgressiveContextResultUnion = (
    LoadProgressiveContextResult | LoadProgressiveContextErrorResult
)

# ============================================================================
# get_relevance_scores
# ============================================================================


class FileRelevanceScore(StrictBaseModel):
    """Relevance score information for a file."""

    total_score: float
    keyword_score: float | None = None
    dependency_score: float | None = None
    recency_score: float | None = None
    quality_score: float | None = None
    reason: str | None = None


class SectionRelevanceScore(StrictBaseModel):
    """Relevance score information for a section."""

    section: str
    score: float
    reason: str | None = None


class GetRelevanceScoresResult(ToolResultBase):
    """Result of get_relevance_scores operation (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    task_description: str
    files_scored: int
    file_scores: dict[str, FileRelevanceScore]
    section_scores: dict[str, list[SectionRelevanceScore]] | None = None


class GetRelevanceScoresErrorResult(ErrorResultBase):
    """Error result for get_relevance_scores operations."""

    task_description: str | None = None


GetRelevanceScoresResultUnion = GetRelevanceScoresResult | GetRelevanceScoresErrorResult

# ============================================================================
# summarize_content
# ============================================================================


class SummarizationResult(StrictBaseModel):
    """Result of summarizing a single file."""

    file_name: str
    original_tokens: int
    summarized_tokens: int
    reduction: float
    cached: bool = False
    summary: str


class SummarizeContentResult(ToolResultBase):
    """Result of summarize_content operation (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    strategy: str
    target_reduction: float
    files_summarized: int
    total_original_tokens: int
    total_summarized_tokens: int
    total_reduction: float
    results: list[SummarizationResult]


class SummarizeContentErrorResult(ErrorResultBase):
    """Error result for summarize_content operations."""

    strategy: str | None = None
    target_reduction: float | None = None


SummarizeContentResultUnion = SummarizeContentResult | SummarizeContentErrorResult
