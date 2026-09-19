"""
Result building for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

from typing import cast

from cortex.core.models import ModelDict
from cortex.optimization.models import DroppedSection, SummarizationResultModel


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
    sections_kept: int = 0,
    sections_removed: int = 0,
    dropped_sections: list[DroppedSection] | None = None,
) -> SummarizationResultModel:
    """Build summary result model."""
    return SummarizationResultModel(
        original_tokens=original_tokens,
        summary_tokens=summarized_tokens,
        reduction=calculate_reduction(original_tokens, summarized_tokens),
        summary=summary,
        strategy=strategy,
        sections_kept=sections_kept,
        sections_removed=sections_removed,
        dropped_sections=dropped_sections or [],
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
    """Calculate the achieved reduction ratio.

    # AI: a strategy can emit MORE tokens than it consumed (markup overhead
    # on near-incompressible input, or omission-note overhead outweighing a
    # tiny dropped section). That is genuine negative reduction, not zero --
    # the caller's target check rejects it either way, and reporting the
    # real number keeps it consistent with the `original_tokens` /
    # `summary_tokens` evidence shown alongside it. The model's `reduction`
    # field has no lower bound, so this never raises on growth.
    """
    if original_tokens <= 0:
        return 0.0
    return (original_tokens - summarized_tokens) / original_tokens
