"""
Models for rules tool (index, get_relevant) results.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
)

from .rules_operation_helpers import RulesOperation


class RulesResultStatus(str, Enum):
    """Status for rules tool results."""

    SUCCESS = "success"
    DISABLED = "disabled"


class RulesIndexResult(StrictBaseModel):
    """Result of rules index operation."""

    indexed: int
    total_tokens: int
    cache_hit: bool
    index_time_seconds: float
    rules_folder: str
    rules_by_category: dict[str, int] = Field(default_factory=dict)


class RulesIndexOperationResult(ToolResultBase):
    """Result of rules index operation (success)."""

    status: RulesResultStatus = Field(default=RulesResultStatus.SUCCESS)
    operation: RulesOperation = Field(default=RulesOperation.INDEX)
    result: RulesIndexResult


class RuleMetadata(StrictBaseModel):
    """Metadata for a single rule."""

    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuleInfo(StrictBaseModel):
    """Information about a single rule."""

    file: str
    category: str
    relevance_score: float
    tokens: int
    title: str | None = None
    content: str | None = None
    metadata: RuleMetadata | None = None


class RulesManagerStatus(StrictBaseModel):
    """Rules manager status information."""

    indexed_count: int
    last_indexed: str
    rules_folder: str


class RulesContext(StrictBaseModel):
    """Rules context information."""

    filtered_count: int
    truncated_count: int


class RulesGetRelevantResult(ToolResultBase):
    """Result of rules get_relevant operation (success)."""

    status: RulesResultStatus = Field(default=RulesResultStatus.SUCCESS)
    operation: RulesOperation = Field(default=RulesOperation.GET_RELEVANT)
    task_description: str
    max_tokens: int
    min_relevance_score: float
    rules_count: int
    total_tokens: int
    rules: list[RuleInfo] = Field(default_factory=lambda: list[RuleInfo]())
    rules_manager_status: RulesManagerStatus | None = None
    rules_context: RulesContext | None = None
    rules_source: str | None = None


class RulesDisabledResult(ToolResultBase):
    """Result when rules indexing is disabled."""

    status: RulesResultStatus = Field(default=RulesResultStatus.DISABLED)
    message: str


class RulesErrorResult(ErrorResultBase):
    """Error result for rules operations."""

    operation: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


RulesResultUnion = (
    RulesIndexOperationResult
    | RulesGetRelevantResult
    | RulesDisabledResult
    | RulesErrorResult
)
