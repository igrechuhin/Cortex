"""Data contracts for layered context loading."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ContextLayer(str, Enum):
    IDENTITY = "l0"
    ESSENTIAL = "l1"
    ON_DEMAND = "l2"
    DEEP_SEARCH = "l3"


class LayerResult(BaseModel):
    layer: ContextLayer
    tokens_estimate: int
    content: str
    sources: list[str] = Field(default_factory=list)


class ContextConfig(BaseModel):
    max_l0_tokens: int = 150
    max_l1_tokens: int = 800
    max_l2_tokens: int = 500
    l1_source_limit: int = 5
