"""
Result building for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

from typing import cast

from cortex.core.models import ModelDict
from cortex.optimization.models import SummarizationResultModel


def build_empty_summary_result(strategy: str) -> SummarizationResultModel:
    """Build result model for empty content."""
    return SummarizationResultModel(
        original_tokens=0,
        summary_tokens=0,
        reduction=0.0,
        summary="",
        strategy=strategy,
        sections_kept=0,
        sections_removed=0,
    )


def build_summary_result(
    original_tokens: int,
    summarized_tokens: int,
    summary: str,
    strategy: str,
) -> SummarizationResultModel:
    """Build summary result model."""
    return SummarizationResultModel(
        original_tokens=original_tokens,
        summary_tokens=summarized_tokens,
        reduction=calculate_reduction(original_tokens, summarized_tokens),
        summary=summary,
        strategy=strategy,
        sections_kept=0,
        sections_removed=0,
    )


def result_to_legacy_dict(
    result: SummarizationResultModel,
    cached: bool,
    strategy_used: str,
) -> ModelDict:
    """Convert typed model to legacy dict shape expected by tools/tests."""
    data = cast(ModelDict, result.model_dump(mode="json"))
    data["summarized_tokens"] = data["summary_tokens"]
    data["strategy_used"] = strategy_used
    data["cached"] = cached
    return data


def calculate_reduction(original_tokens: int, summarized_tokens: int) -> float:
    """Calculate reduction percentage."""
    if original_tokens > 0:
        return (original_tokens - summarized_tokens) / original_tokens
    return 0.0
