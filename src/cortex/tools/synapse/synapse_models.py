"""
Models for Synapse tools: get_synapse_prompts, update_synapse_prompt,
fix_roadmap_corruption, sync_synapse, get_synapse_rules, update_synapse_rule.
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class SynapseUpdateType(str, Enum):
    """Type of Synapse entity updated (prompt or rule)."""

    PROMPT = "prompt"
    RULE = "rule"


class SynapseCategory(str, Enum):
    """Supported Synapse category names for rules/prompts."""

    PYTHON = "python"
    GENERAL = "general"
    GENERIC = "generic"


class PromptInfo(StrictBaseModel):
    """Information about a prompt."""

    file: str
    name: str
    category: SynapseCategory
    description: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapsePromptsResult(ToolResultBase):
    """Result of get_synapse_prompts operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    category: SynapseCategory | None = None
    categories: list[SynapseCategory] = Field(
        default_factory=lambda: list[SynapseCategory]()
    )
    prompts: list[PromptInfo] = Field(default_factory=lambda: list[PromptInfo]())
    total_count: int


class GetSynapsePromptsErrorResult(ErrorResultBase):
    """Error result for get_synapse_prompts operations."""


GetSynapsePromptsResultUnion = GetSynapsePromptsResult | GetSynapsePromptsErrorResult


class UpdateSynapsePromptResult(ToolResultBase):
    """Result of update_synapse_prompt operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    category: SynapseCategory
    file: str
    message: str
    type: SynapseUpdateType = Field(default=SynapseUpdateType.PROMPT)
    commit_hash: str | None = None


class UpdateSynapsePromptErrorResult(ErrorResultBase):
    """Error result for update_synapse_prompt operations."""


UpdateSynapsePromptResultUnion = (
    UpdateSynapsePromptResult | UpdateSynapsePromptErrorResult
)


class CorruptionMatch(StrictBaseModel):
    """A detected corruption match."""

    line_num: int = Field(
        ..., ge=1, description="Line number where corruption was found"
    )
    original: str = Field(..., min_length=1, description="Original corrupted content")
    fixed: str = Field(..., description="Fixed content")
    pattern: str = Field(
        ..., min_length=1, description="Pattern that matched the corruption"
    )

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
    )


class FixRoadmapCorruptionResult(ToolResultBase):
    """Result of fix_roadmap_corruption operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    file_name: str
    corruption_count: int
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


class FixRoadmapCorruptionErrorResult(ErrorResultBase):
    """Error result for fix_roadmap_corruption operations."""

    file_name: str
    corruption_count: int = 0
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


FixRoadmapCorruptionResultUnion = (
    FixRoadmapCorruptionResult | FixRoadmapCorruptionErrorResult
)


class SynapseChanges(StrictBaseModel):
    """Changes detected during sync."""

    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class SyncSynapseResult(ToolResultBase):
    """Result of sync_synapse operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    pulled: bool
    pushed: bool
    changes: SynapseChanges
    reindex_triggered: bool
    last_sync: str


class SyncSynapseErrorResult(ErrorResultBase):
    """Error result for sync_synapse operations."""


SyncSynapseResultUnion = SyncSynapseResult | SyncSynapseErrorResult


class RuleInfoModel(StrictBaseModel):
    """Information about a rule."""

    file: str
    tokens: int
    priority: str | None = None
    relevance_score: float | None = None
    category: SynapseCategory | None = None


class ContextInfo(StrictBaseModel):
    """Context information for rules."""

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    task_type: str | None = None


class RulesLoaded(StrictBaseModel):
    """Loaded rules by category."""

    generic: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    language: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    local: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())


class GetSynapseRulesResult(ToolResultBase):
    """Result of get_synapse_rules operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    task_description: str
    context: ContextInfo
    rules_loaded: RulesLoaded
    total_tokens: int
    token_budget: int
    source: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapseRulesErrorResult(ErrorResultBase):
    """Error result for get_synapse_rules operations."""


GetSynapseRulesResultUnion = GetSynapseRulesResult | GetSynapseRulesErrorResult


class UpdateSynapseRuleResult(ToolResultBase):
    """Result of update_synapse_rule operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    category: SynapseCategory
    file: str
    message: str
    commit_hash: str | None = None


class UpdateSynapseRuleErrorResult(ErrorResultBase):
    """Error result for update_synapse_rule operations."""


UpdateSynapseRuleResultUnion = UpdateSynapseRuleResult | UpdateSynapseRuleErrorResult
