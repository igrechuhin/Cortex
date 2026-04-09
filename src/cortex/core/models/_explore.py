"""Explore workflow models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ._enums import RiskLevel


class ExploreComplexity(str, Enum):
    """Estimated implementation complexity for an explore option."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExploreOption(BaseModel):
    """Single approach captured during /cortex/explore brainstorming."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    complexity: ExploreComplexity
    risk: RiskLevel


def _empty_explore_options() -> list[ExploreOption]:
    return []


class ExploreSession(BaseModel):
    """Explore brainstorming payload persisted in decision logs."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    topic: str = Field(..., min_length=1)
    options: list[ExploreOption] = Field(default_factory=_empty_explore_options)
    recommendation: str | None = None
    created: datetime
    decision: str | None = None
