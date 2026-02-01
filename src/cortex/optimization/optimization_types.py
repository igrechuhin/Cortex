"""
Types for optimization strategies.

This module contains shared types used across optimization strategy modules.
"""

from dataclasses import dataclass

from cortex.core.models import ModelDict
from cortex.optimization.models import OptimizationResultModel


@dataclass
class OptimizationResult:
    """Result of context optimization (dataclass for strategy orchestration)."""

    selected_files: list[str]
    selected_sections: dict[str, list[str]]
    total_tokens: int
    utilization: float
    excluded_files: list[str]
    strategy_used: str
    metadata: ModelDict


__all__ = ["OptimizationResult", "OptimizationResultModel"]
