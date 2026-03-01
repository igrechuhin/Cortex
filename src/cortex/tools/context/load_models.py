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
from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)
from cortex.tools.session_models import TokenBudgetStatus


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


# Re-export auxiliary models for backward compatibility
