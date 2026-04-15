"""Rules indexing and loading models.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.pydantic_extra import EXTRA_FORBID

from ._base import OptimizationBaseModel


class RuleSectionModel(OptimizationBaseModel):
    """Section within a rule file."""

    name: str = Field(..., description="Section name/heading")
    content: str = Field(..., description="Section content")
    line_count: int = Field(..., ge=0, description="Number of lines")


class OptimizationRuleCategory(str, Enum):
    """Rule category for optimization scoring payloads."""

    UNKNOWN = ""
    GENERIC = "generic"
    GENERAL = "general"
    PYTHON = "python"
    SWIFT = "swift"
    MARKDOWN = "markdown"


class RelevantRuleModel(OptimizationBaseModel):
    """A relevant rule selected for context."""

    name: str = Field(..., description="Rule name/file path")
    content: str = Field(..., description="Rule content")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    tokens: int = Field(..., ge=0, description="Token count")
    source: str = Field(default="local", description="Rule source: local or shared")
    category: str | None = Field(default=None, description="Rule category")


class RelevantRulesResultModel(OptimizationBaseModel):
    """Result of getting relevant rules."""

    rules: list[RelevantRuleModel] = Field(
        default_factory=lambda: list[RelevantRuleModel](),
        description="Selected rules",
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens in selection")
    context: dict[str, str | list[str]] = Field(
        default_factory=dict, description="Detected context"
    )


class IndexedRuleModel(OptimizationBaseModel):
    """Indexed rule file data."""

    path: str = Field(..., description="Absolute path to rule file")
    relative_path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="Rule file content")
    content_hash: str = Field(..., description="SHA-256 hash prefix (16 chars)")
    token_count: int = Field(..., ge=0, description="Token count")
    sections: list[RuleSectionModel] = Field(
        default_factory=lambda: list[RuleSectionModel](),
        description="Parsed sections",
    )
    indexed_at: str = Field(..., description="ISO timestamp of indexing")
    file_size: int = Field(..., ge=0, description="File size in bytes")


class ScoredRuleModel(OptimizationBaseModel):
    """Rule with relevance scoring."""

    file: str = Field(default="", description="File key/path")
    name: str = Field(default="", description="Rule name")
    content: str = Field(..., description="Rule content")
    tokens: int = Field(default=0, ge=0, description="Token count")
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Relevance score"
    )
    sections: list[RuleSectionModel] = Field(
        default_factory=lambda: list[RuleSectionModel](),
        description="Parsed sections",
    )
    source: str = Field(default="local", description="Rule source: local or shared")
    priority: int = Field(default=50, ge=0, description="Rule priority")
    category: OptimizationRuleCategory = Field(
        default=OptimizationRuleCategory.UNKNOWN,
        description="Rule category",
    )


class DetectedContextModel(OptimizationBaseModel):
    """Detected context for rule selection."""

    detected_languages: list[str] = Field(
        default_factory=list, description="Detected programming languages"
    )
    detected_frameworks: list[str] = Field(
        default_factory=list, description="Detected frameworks"
    )
    task_type: str | None = Field(default=None, description="Detected task type")
    categories_to_load: list[str] = Field(
        default_factory=list,
        description="Rule categories to load",
    )


class RulesResultModel(OptimizationBaseModel):
    """Result of getting rules (hybrid or local-only)."""

    generic_rules: list[ScoredRuleModel] = Field(
        default_factory=lambda: list[ScoredRuleModel](),
        description="Generic rules",
    )
    language_rules: list[ScoredRuleModel] = Field(
        default_factory=lambda: list[ScoredRuleModel](),
        description="Language-specific rules",
    )
    local_rules: list[ScoredRuleModel] = Field(
        default_factory=lambda: list[ScoredRuleModel](),
        description="Local project rules",
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens")
    context: DetectedContextModel = Field(
        default_factory=DetectedContextModel, description="Detected context"
    )
    source: str = Field(
        default="local_only", description="Rules source: hybrid or local_only"
    )


class RulesManagerStatusModel(DictLikeModel):
    """Status information for rules manager."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )

    enabled: bool = Field(..., description="Whether rules manager is enabled")
    rules_folder: str | None = Field(
        default=None, description="Configured rules folder"
    )
    indexed_files: int = Field(default=0, ge=0, description="Number of indexed files")
    last_indexed: str | None = Field(
        default=None, description="ISO timestamp of last indexing"
    )
    auto_reindex_enabled: bool = Field(
        default=False, description="Whether auto-reindexing is enabled"
    )
    reindex_interval_minutes: float = Field(
        default=30.0, ge=0.0, description="Reindex interval in minutes"
    )
    total_tokens: int = Field(
        default=0, ge=0, description="Total tokens in indexed rules"
    )
