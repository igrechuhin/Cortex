"""Script analysis for captured session scripts.

This module supports Phase 27: analyzing captured scripts for patterns,
gaps vs existing tooling, use cases, and promotion potential.
"""

from cortex.script_analysis.gap_analyzer import analyze_gap
from cortex.script_analysis.models import (
    GapAnalysis,
    ScriptAnalysisResult,
    SimilarityPair,
    UseCaseExtraction,
)
from cortex.script_analysis.script_analyzer import analyze_script
from cortex.script_analysis.similarity_detector import (
    compute_similarity,
    find_similar_pairs,
)
from cortex.script_analysis.use_case_extractor import extract_use_case

__all__ = [
    "GapAnalysis",
    "ScriptAnalysisResult",
    "SimilarityPair",
    "UseCaseExtraction",
    "analyze_gap",
    "analyze_script",
    "compute_similarity",
    "extract_use_case",
    "find_similar_pairs",
]
