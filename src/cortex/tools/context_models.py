"""
Context loading, configuration, memory bank stats, and related result models.

Used by load_context, configure, get_memory_bank_stats, get_version_history,
get_dependency_graph, resolve_transclusions, load_progressive_context,
get_relevance_scores, summarize_content.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field

from cortex.core.models import IndexStats, JsonDict

from .models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)
from .session_models import TokenBudgetStatus


def _coerce_str_enum[E: Enum](v: str | Enum, enum_cls: type[E]) -> E:
    """Coerce string to enum for Pydantic (e.g. from JSON or dict input)."""
    if isinstance(v, enum_cls):
        return v
    return enum_cls(v)


class ConfigureComponent(str, Enum):
    """Configure tool component."""

    VALIDATION = "validation"
    OPTIMIZATION = "optimization"
    LEARNING = "learning"


class RefactoringHistoryEntryStatus(str, Enum):
    """Status of a refactoring history entry."""

    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DependencyGraphFormat(str, Enum):
    """Dependency graph output format."""

    JSON = "json"
    MERMAID = "mermaid"


_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]
_ConfigureComponentField = Annotated[
    ConfigureComponent,
    BeforeValidator(lambda x: _coerce_str_enum(x, ConfigureComponent)),
]
_TokenBudgetStatusField = Annotated[
    TokenBudgetStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, TokenBudgetStatus)),
]
_RefactoringHistoryStatusField = Annotated[
    RefactoringHistoryEntryStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, RefactoringHistoryEntryStatus)),
]
_DependencyGraphFormatField = Annotated[
    DependencyGraphFormat,
    BeforeValidator(lambda x: _coerce_str_enum(x, DependencyGraphFormat)),
]

# ============================================================================
# load_context
# ============================================================================


class LoadContextResult(ToolResultBase):
    """Result of load_context operation."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    task_description: str
    token_budget: int
    strategy: str
    selected_files: list[str] = Field(default_factory=list)
    selected_sections: dict[str, list[str]] = Field(default_factory=dict)
    total_tokens: int
    utilization: float
    excluded_files: list[str] = Field(default_factory=list)
    relevance_scores: dict[str, float] = Field(default_factory=dict)
    role: str | None = Field(
        default=None,
        description="Agent role used for this context load (e.g. feature, quality).",
    )


class LoadContextErrorResult(ErrorResultBase):
    """Error result for load_context operations."""

    task_description: str | None = None
    token_budget: int | None = None
    strategy: str | None = None
    role: str | None = None


LoadContextResultUnion = LoadContextResult | LoadContextErrorResult


class SectionSummary(StrictBaseModel):
    """Section metadata for file map entries (heading, tokens, level)."""

    heading: str = Field(default="", description="Section heading")
    tokens: int = Field(default=0, ge=0, description="Token count")
    level: int = Field(default=2, ge=1, le=6, description="Heading level")


def _empty_section_list() -> list[SectionSummary]:
    """Return empty list for FileMapEntry.sections default."""
    return []


class FileMapEntry(StrictBaseModel):
    """Single file entry in load_context files map (metadata-only response)."""

    name: str = Field(..., description="File name")
    total_tokens: int = Field(..., ge=0, description="Total tokens")
    last_modified: str = Field(default="", description="Last modified timestamp")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    sections: list[SectionSummary] = Field(
        default_factory=_empty_section_list, description="Section metadata list"
    )


# ============================================================================
# configure
# ============================================================================


class ConfigureViewResult(ToolResultBase):
    """Result of configure view action."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    component: _ConfigureComponentField
    configuration: JsonDict = Field(default_factory=lambda: JsonDict.from_dict({}))
    learned_patterns: JsonDict | None = None


class ConfigureUpdateResult(ToolResultBase):
    """Result of configure update action."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    component: _ConfigureComponentField
    message: str
    configuration: JsonDict = Field(default_factory=lambda: JsonDict.from_dict({}))
    action: str | None = None
    patterns: JsonDict | None = None


class ConfigureResetResult(ToolResultBase):
    """Result of configure reset action."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    message: str
    component: _ConfigureComponentField
    configuration: JsonDict = Field(default_factory=lambda: JsonDict.from_dict({}))


class ConfigureErrorResult(ErrorResultBase):
    """Error result for configure operations."""

    component: str | None = None
    valid_components: list[str] = Field(default_factory=list)
    valid_actions: list[str] = Field(default_factory=list)


ConfigureResult = (
    ConfigureViewResult
    | ConfigureUpdateResult
    | ConfigureResetResult
    | ConfigureErrorResult
)


# ============================================================================
# get_memory_bank_stats
# ============================================================================


class MemoryBankSummary(StrictBaseModel):
    """Memory Bank summary statistics."""

    total_files: int
    total_tokens: int
    total_size_bytes: int
    total_size_kb: float
    total_reads: int
    history_size_bytes: int
    history_size_kb: float


class TokenBudgetStatusInfo(StrictBaseModel):
    """Token budget status information (get_memory_bank_stats)."""

    status: _TokenBudgetStatusField
    total_tokens: int
    max_tokens: int
    remaining_tokens: int
    usage_percentage: float
    warn_threshold: float


class RefactoringHistoryEntry(StrictBaseModel):
    """Individual refactoring history entry."""

    type: str
    timestamp: str
    files_affected: list[str] = Field(default_factory=list)
    status: _RefactoringHistoryStatusField


class RefactoringHistory(StrictBaseModel):
    """Refactoring history data."""

    total_refactorings: int
    successful: int
    rolled_back: int
    recent: list[RefactoringHistoryEntry] = Field(
        default_factory=lambda: list[RefactoringHistoryEntry]()
    )


class GetMemoryBankStatsResult(ToolResultBase):
    """Result of get_memory_bank_stats operation."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    project_root: str
    summary: MemoryBankSummary
    last_updated: str | None = None
    index_stats: IndexStats | None = None
    token_budget: TokenBudgetStatusInfo | None = None
    refactoring_history: RefactoringHistory | None = None


class GetMemoryBankStatsErrorResult(ErrorResultBase):
    """Error result for get_memory_bank_stats operations."""

    project_root: str | None = None


GetMemoryBankStatsResultUnion = GetMemoryBankStatsResult | GetMemoryBankStatsErrorResult


# ============================================================================
# get_version_history
# ============================================================================


class VersionHistoryEntry(StrictBaseModel):
    """Version history entry."""

    version: int
    timestamp: str
    change_type: str | None = None
    change_description: str | None = None
    size_bytes: int | None = None
    token_count: int | None = None


class GetVersionHistoryResult(ToolResultBase):
    """Result of get_version_history operation."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    file_name: str
    total_versions: int
    versions: list[VersionHistoryEntry] = Field(
        default_factory=lambda: list[VersionHistoryEntry]()
    )


class GetVersionHistoryErrorResult(ErrorResultBase):
    """Error result for get_version_history operations."""

    file_name: str | None = None


GetVersionHistoryResultUnion = GetVersionHistoryResult | GetVersionHistoryErrorResult


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
