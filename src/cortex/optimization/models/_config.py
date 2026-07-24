"""Configuration models for optimization.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.constants import MemoryBankFile
from cortex.core.pydantic_extra import EXTRA_ALLOW

from ._base import OptimizationBaseModel


class TokenBudgetOptConfigModel(OptimizationBaseModel):
    """Token budget configuration for optimization."""

    default_budget: int = Field(default=80000, ge=1, description="Default token budget")
    max_budget: int = Field(default=100000, ge=1, description="Maximum token budget")
    reserve_for_response: int = Field(
        default=10000, ge=0, description="Tokens reserved for response"
    )


class LoadingStrategy(str, Enum):
    """Context loading strategy."""

    PRIORITY = "priority"
    DEPENDENCY_AWARE = "dependency_aware"
    SECTION_LEVEL = "section_level"
    HYBRID = "hybrid"


class LoadingStrategyConfigModel(OptimizationBaseModel):
    """Loading strategy configuration."""

    default: LoadingStrategy = Field(
        default=LoadingStrategy.DEPENDENCY_AWARE,
        description="Default loading strategy",
    )
    mandatory_files: list[str] = Field(
        default_factory=lambda: [MemoryBankFile.PROJECT_BRIEF],
        description="Files that must always be loaded",
    )
    priority_order: list[str] = Field(
        default_factory=lambda: [
            MemoryBankFile.PROJECT_BRIEF,
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.TECH_CONTEXT,
            MemoryBankFile.PRODUCT_CONTEXT,
            MemoryBankFile.PROGRESS,
        ],
        description="File loading priority order",
    )
    always_load_sections: dict[str, list[str]] = Field(
        default_factory=lambda: {
            MemoryBankFile.PROJECT_BRIEF: [],
            MemoryBankFile.ACTIVE_CONTEXT: ["## Current Focus", "## Next Steps"],
        },
        description=(
            "Sections that must always be loaded in full even when depth=metadata_only."
        ),
    )


class SummarizationStrategy(str, Enum):
    """Summarization strategy."""

    EXTRACT_KEY_SECTIONS = "extract_key_sections"
    COMPRESS_EXAMPLES = "compress_examples"
    REMOVE_VERBOSE = "remove_verbose"
    HYBRID = "hybrid"


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
        default=SummarizationStrategy.EXTRACT_KEY_SECTIONS,
        description="Summarization strategy",
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


class RulePriority(str, Enum):
    """Rule priority order (local vs shared)."""

    LOCAL_OVERRIDES_SHARED = "local_overrides_shared"
    SHARED_OVERRIDES_LOCAL = "shared_overrides_local"


class LanguageKeywordsModel(OptimizationBaseModel):
    """Language keywords for context detection."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

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
        default=".cortex/rules", description="Path to rules folder"
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
        default=RulePriority.LOCAL_OVERRIDES_SHARED,
        description="Rule priority strategy",
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


class ToolSearchConfigModel(OptimizationBaseModel):
    """Tool search (deferred loading) configuration."""

    enabled: bool = Field(
        default=False,
        description="Whether deferred tool loading / tool search is enabled",
    )
    always_loaded: list[str] = Field(
        default_factory=list,
        description="Tool names to load initially when tool search is enabled",
    )
    deferred_medium: list[str] = Field(
        default_factory=list,
        description="Deferred tool names (medium priority)",
    )
    deferred_low: list[str] = Field(
        default_factory=list,
        description="Deferred tool names (low priority)",
    )


class ToolCompatConfigModel(OptimizationBaseModel):
    """Compatibility toggles for tool-only clients."""

    expose_resources_as_tools: bool = Field(
        default=False,
        description="Expose resources through generated tool wrappers",
    )
    expose_prompts_as_tools: bool = Field(
        default=False,
        description="Expose prompts through generated tool wrappers",
    )


class OptimizationConfigModel(OptimizationBaseModel):
    """Complete optimization configuration model."""

    enabled: bool = Field(default=True, description="Whether optimization is enabled")
    max_response_tokens: int = Field(
        default=50000,
        ge=1,
        description="Maximum response budget for MCP response-limiting middleware.",
    )
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
    tool_search: ToolSearchConfigModel | None = Field(
        default=None,
        description="Tool search / deferred loading configuration",
    )
    tool_compat: ToolCompatConfigModel = Field(
        default_factory=ToolCompatConfigModel,
        description="Compatibility settings for tool-only clients",
    )
