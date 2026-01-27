"""
Pydantic models for optimization module.

This module contains Pydantic models for optimization operations,
migrated from dataclass and legacy dict-based shapes for better validation.
"""

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from cortex.core.models import DictLikeModel

# ============================================================================
# Base Model
# ============================================================================


class OptimizationBaseModel(DictLikeModel):
    """Base model for optimization types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Optimization Types (from optimization_types.py)
# ============================================================================


class OptimizationMetadata(OptimizationBaseModel):
    """Metadata for optimization result."""

    # Using extra="allow" to allow arbitrary metadata fields
    # since production code dynamically adds strategy_info and other fields
    model_config = ConfigDict(extra="allow", validate_assignment=True)

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
    # Hybrid strategy metadata
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


# ============================================================================
# File Metadata for Scoring/Optimization Operations
# ============================================================================


class FileMetadataForScoring(OptimizationBaseModel):
    """Metadata for a file used in scoring and optimization operations.

    This model is used as the value type for files_metadata parameter
    in scoring and optimization functions. It allows extra fields since
    metadata may come from various sources (MetadataIndex, DetailedFileMetadata, etc.)
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    path: str | None = Field(default=None, description="File path")
    size: int | None = Field(default=None, ge=0, description="File size in bytes")
    size_bytes: int | None = Field(
        default=None, ge=0, description="File size in bytes (alias)"
    )
    token_count: int | None = Field(default=None, ge=0, description="Token count")
    content_hash: str | None = Field(default=None, description="Content hash")
    last_modified: str | None = Field(
        default=None, description="ISO timestamp of last modification"
    )
    sections: list[str] = Field(default_factory=list, description="Section headings")
    priority: int | None = Field(default=None, ge=0, description="Loading priority")


# ============================================================================
# Progressive Loader Types (from progressive_loader.py)
# ============================================================================


class FileContentMetadata(OptimizationBaseModel):
    """Metadata for loaded file content."""

    # Allow extra fields since various sources may add different metadata
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    content_hash: str | None = Field(default=None, description="Content hash")
    last_modified: str | None = Field(
        default=None, description="ISO timestamp of last modification"
    )
    sections: list[str] = Field(default_factory=list, description="Section headings")
    priority: int | None = Field(default=None, ge=0, description="Loading priority")
    tokens: int | None = Field(default=None, ge=0, description="Token count")


class LoadedFileContentModel(OptimizationBaseModel):
    """Type definition for loaded file content."""

    content: str = Field(..., description="File content")
    tokens: int = Field(..., ge=0, description="Token count")
    cumulative_tokens: int = Field(..., ge=0, description="Cumulative token count")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


class LoadedContentModel(OptimizationBaseModel):
    """Represents a loaded piece of content."""

    file_name: str = Field(..., description="File name")
    content: str = Field(..., description="File content")
    tokens: int = Field(..., ge=0, description="Token count")
    cumulative_tokens: int = Field(..., ge=0, description="Cumulative token count")
    priority: int = Field(..., ge=0, description="Loading priority")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Relevance score 0-1"
    )
    more_available: bool = Field(..., description="Whether more content is available")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


# ============================================================================
# Protocol Return Type Models (for RelevanceScorerProtocol)
# ============================================================================


class FileRelevanceScoreModel(OptimizationBaseModel):
    """Relevance score breakdown for a file."""

    # Core identification
    file_name: str | None = Field(default=None, description="File name (optional)")

    # Overall score - can be called relevance_score or total_score
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall relevance score (alias: total_score)",
    )
    total_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Total weighted score (alias: relevance_score)",
    )

    # Component scores
    keyword_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Keyword match score"
    )
    dependency_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Dependency relevance score"
    )
    recency_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Recency score"
    )

    # Quality can be called quality_boost or quality_score
    quality_boost: float = Field(default=1.0, ge=0.0, description="Quality multiplier")
    quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality score"
    )

    # Explanation
    reason: str | None = Field(default=None, description="Explanation of score")

    @model_validator(mode="after")
    def sync_score_aliases(self) -> "FileRelevanceScoreModel":
        """Sync relevance_score and total_score aliases.

        If only one is set, copy its value to the other.
        This ensures backward compatibility with code using either name.
        """
        # If total_score is set but relevance_score is default, copy total_score
        if self.total_score > 0.0 and self.relevance_score == 0.0:
            object.__setattr__(self, "relevance_score", self.total_score)
        # If relevance_score is set but total_score is default, copy relevance_score
        elif self.relevance_score > 0.0 and self.total_score == 0.0:
            object.__setattr__(self, "total_score", self.relevance_score)
        return self


class SectionScoreModel(OptimizationBaseModel):
    """Relevance score for a section within a file."""

    # Section name - supports both 'title' and 'section' for flexibility
    title: str | None = Field(default=None, description="Section title")
    section: str | None = Field(
        default=None, description="Section name (alias for title)"
    )

    # Score
    score: float = Field(..., ge=0.0, le=1.0, description="Section relevance score")

    # Line numbers (optional - not always available)
    start_line: int | None = Field(default=None, ge=1, description="Section start line")
    end_line: int | None = Field(default=None, ge=1, description="Section end line")

    # Explanation
    reason: str | None = Field(default=None, description="Explanation of score")

    @model_validator(mode="after")
    def sync_title_section(self) -> "SectionScoreModel":
        """Sync title and section aliases.

        If only one is set, copy its value to the other.
        """
        if self.section is not None and self.title is None:
            object.__setattr__(self, "title", self.section)
        elif self.title is not None and self.section is None:
            object.__setattr__(self, "section", self.title)
        return self


# ============================================================================
# Protocol Return Type Models (for ProgressiveLoaderProtocol)
# ============================================================================


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


# ============================================================================
# Protocol Return Type Models (for SummarizationEngineProtocol)
# ============================================================================


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


# ============================================================================
# Protocol Return Type Models (for RulesManagerProtocol)
# ============================================================================


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


# ============================================================================
# Rules Indexer Models (from rules_indexer.py, rules_manager.py)
# ============================================================================


class RuleSectionModel(OptimizationBaseModel):
    """Section within a rule file."""

    name: str = Field(..., description="Section name/heading")
    content: str = Field(..., description="Section content")
    line_count: int = Field(..., ge=0, description="Number of lines")


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
    category: str = Field(default="", description="Rule category")


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
        description="Rule categories to load (including generic/language/task_type)",
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
        extra="forbid",
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


# ============================================================================
# Summarization Internal Models
# ============================================================================


class ScoredSectionModel(OptimizationBaseModel):
    """Section with relevance scoring for summarization."""

    name: str = Field(..., description="Section name/heading")
    content: str = Field(..., description="Section content")
    score: float = Field(..., ge=0.0, le=1.0, description="Importance score")
    tokens: int = Field(..., ge=0, description="Token count")


class SummarizationState(OptimizationBaseModel):
    """State for tracking parsing during summarization."""

    in_code_block: bool = Field(default=False, description="Currently in code block")
    in_example: bool = Field(default=False, description="Currently in example section")
    code_block_lines: list[str] = Field(
        default_factory=list, description="Accumulated code block lines"
    )


# ============================================================================
# Configuration Models (from optimization_config.py)
# ============================================================================


class TokenBudgetOptConfigModel(OptimizationBaseModel):
    """Token budget configuration for optimization."""

    default_budget: int = Field(default=80000, ge=1, description="Default token budget")
    max_budget: int = Field(default=100000, ge=1, description="Maximum token budget")
    reserve_for_response: int = Field(
        default=10000, ge=0, description="Tokens reserved for response"
    )


LoadingStrategy = Literal["priority", "dependency_aware", "section_level", "hybrid"]


class LoadingStrategyConfigModel(OptimizationBaseModel):
    """Loading strategy configuration."""

    default: LoadingStrategy = Field(
        default="dependency_aware", description="Default loading strategy"
    )
    mandatory_files: list[str] = Field(
        default_factory=lambda: ["memorybankinstructions.md"],
        description="Files that must always be loaded",
    )
    priority_order: list[str] = Field(
        default_factory=lambda: [
            "memorybankinstructions.md",
            "projectBrief.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
            "progress.md",
        ],
        description="File loading priority order",
    )


SummarizationStrategy = Literal[
    "extract_key_sections", "compress_examples", "remove_verbose", "hybrid"
]


class SummarizationConfigModel(OptimizationBaseModel):
    """Summarization configuration."""

    enabled: bool = Field(default=True, description="Whether summarization is enabled")
    auto_summarize_old_files: bool = Field(
        default=False, description="Auto-summarize files older than threshold"
    )
    age_threshold_days: int = Field(
        default=90, ge=1, description="Age threshold for auto-summarization in days"
    )
    target_reduction: float = Field(
        default=0.5, gt=0.0, lt=1.0, description="Target reduction ratio (0-1)"
    )
    strategy: SummarizationStrategy = Field(
        default="extract_key_sections", description="Summarization strategy"
    )
    cache_summaries: bool = Field(
        default=True, description="Whether to cache generated summaries"
    )


class RelevanceWeightsConfigModel(OptimizationBaseModel):
    """Relevance scoring weights configuration."""

    keyword_weight: float = Field(
        default=0.4, ge=0.0, le=1.0, description="Weight for keyword matching"
    )
    dependency_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Weight for dependency relevance"
    )
    recency_weight: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Weight for recent modifications"
    )
    quality_weight: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Weight for quality score"
    )


class PerformanceConfigModel(OptimizationBaseModel):
    """Performance and caching configuration."""

    cache_enabled: bool = Field(default=True, description="Whether caching is enabled")
    cache_ttl_seconds: int = Field(
        default=3600, ge=0, description="Cache TTL in seconds"
    )
    max_cache_size_mb: int = Field(
        default=50, ge=1, description="Maximum cache size in MB"
    )


RulePriority = Literal["local_overrides_shared", "shared_overrides_local"]


class LanguageKeywordsModel(OptimizationBaseModel):
    """Language keywords for context detection."""

    model_config = ConfigDict(extra="allow")

    python: list[str] = Field(
        default_factory=lambda: ["python", "django", "flask", "fastapi", "pytest", "py"]
    )
    swift: list[str] = Field(
        default_factory=lambda: ["swift", "swiftui", "ios", "uikit", "combine", "cocoa"]
    )
    javascript: list[str] = Field(
        default_factory=lambda: [
            "javascript",
            "js",
            "react",
            "vue",
            "node",
            "typescript",
            "ts",
        ]
    )
    rust: list[str] = Field(default_factory=lambda: ["rust", "cargo", "rustc"])
    go: list[str] = Field(default_factory=lambda: ["golang", "go"])
    java: list[str] = Field(
        default_factory=lambda: ["java", "spring", "maven", "gradle"]
    )
    csharp: list[str] = Field(
        default_factory=lambda: ["c#", "csharp", "dotnet", ".net"]
    )
    cpp: list[str] = Field(default_factory=lambda: ["c++", "cpp", "cmake"])


class ContextDetectionConfigModel(OptimizationBaseModel):
    """Context detection configuration."""

    enabled: bool = Field(
        default=True, description="Whether context detection is enabled"
    )
    detect_from_task: bool = Field(
        default=True, description="Detect context from task description"
    )
    detect_from_files: bool = Field(
        default=True, description="Detect context from project files"
    )
    language_keywords: LanguageKeywordsModel = Field(
        default_factory=LanguageKeywordsModel,
        description="Language detection keywords",
    )


class RulesConfigModel(OptimizationBaseModel):
    """Rules indexing and loading configuration."""

    enabled: bool = Field(
        default=False, description="Whether rules indexing is enabled"
    )
    rules_folder: str = Field(
        default=".cursorrules", description="Path to rules folder"
    )
    reindex_interval_minutes: int = Field(
        default=30, ge=1, description="Rules reindex interval in minutes"
    )
    auto_include_in_context: bool = Field(
        default=True, description="Auto-include relevant rules in context"
    )
    max_rules_tokens: int = Field(
        default=5000, ge=0, description="Maximum tokens for rules"
    )
    min_relevance_score: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum relevance score for rules"
    )
    rule_priority: RulePriority = Field(
        default="local_overrides_shared", description="Rule priority strategy"
    )
    context_aware_loading: bool = Field(
        default=True, description="Use context-aware rule loading"
    )
    always_include_generic: bool = Field(
        default=True, description="Always include generic rules"
    )
    context_detection: ContextDetectionConfigModel = Field(
        default_factory=ContextDetectionConfigModel,
        description="Context detection settings",
    )


class SynapseConfigModel(OptimizationBaseModel):
    """Synapse shared rules configuration."""

    enabled: bool = Field(default=False, description="Whether Synapse is enabled")
    synapse_folder: str = Field(
        default=".cortex/synapse", description="Path to Synapse folder"
    )
    synapse_repo: str = Field(default="", description="Synapse repository URL")
    auto_sync: bool = Field(default=True, description="Auto-sync with Synapse repo")
    sync_interval_minutes: int = Field(
        default=60, ge=1, description="Sync interval in minutes"
    )


class EvolutionAnalysisConfigModel(OptimizationBaseModel):
    """Self-evolution analysis configuration."""

    track_usage_patterns: bool = Field(
        default=True, description="Track file usage patterns"
    )
    pattern_window_days: int = Field(
        default=30, ge=1, description="Days to analyze for patterns"
    )
    min_access_count: int = Field(
        default=5, ge=1, description="Minimum accesses for pattern detection"
    )
    track_task_patterns: bool = Field(
        default=True, description="Track task-related patterns"
    )


class EvolutionInsightsConfigModel(OptimizationBaseModel):
    """Self-evolution insights configuration."""

    auto_generate: bool = Field(
        default=False, description="Auto-generate optimization insights"
    )
    min_impact_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum impact score for insights"
    )
    categories: list[str] = Field(
        default_factory=lambda: [
            "usage",
            "organization",
            "redundancy",
            "dependencies",
            "quality",
        ],
        description="Insight categories to analyze",
    )


class SelfEvolutionConfigModel(OptimizationBaseModel):
    """Self-evolution and adaptive learning configuration."""

    enabled: bool = Field(default=True, description="Whether self-evolution is enabled")
    analysis: EvolutionAnalysisConfigModel = Field(
        default_factory=EvolutionAnalysisConfigModel,
        description="Analysis configuration",
    )
    insights: EvolutionInsightsConfigModel = Field(
        default_factory=EvolutionInsightsConfigModel,
        description="Insights configuration",
    )


class OptimizationConfigModel(OptimizationBaseModel):
    """Complete optimization configuration model."""

    enabled: bool = Field(default=True, description="Whether optimization is enabled")
    token_budget: TokenBudgetOptConfigModel = Field(
        default_factory=TokenBudgetOptConfigModel,
        description="Token budget configuration",
    )
    loading_strategy: LoadingStrategyConfigModel = Field(
        default_factory=LoadingStrategyConfigModel,
        description="Loading strategy configuration",
    )
    summarization: SummarizationConfigModel = Field(
        default_factory=SummarizationConfigModel,
        description="Summarization configuration",
    )
    relevance: RelevanceWeightsConfigModel = Field(
        default_factory=RelevanceWeightsConfigModel,
        description="Relevance weights configuration",
    )
    performance: PerformanceConfigModel = Field(
        default_factory=PerformanceConfigModel,
        description="Performance configuration",
    )
    rules: RulesConfigModel = Field(
        default_factory=RulesConfigModel,
        description="Rules configuration",
    )
    synapse: SynapseConfigModel = Field(
        default_factory=SynapseConfigModel,
        description="Synapse configuration",
    )
    self_evolution: SelfEvolutionConfigModel = Field(
        default_factory=SelfEvolutionConfigModel,
        description="Self-evolution configuration",
    )
