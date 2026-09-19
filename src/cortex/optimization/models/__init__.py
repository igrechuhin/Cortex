"""
Pydantic models for optimization module.

Phase 9.1.5: Split into submodules for file size compliance (each file <400 lines).
External imports remain: from cortex.optimization.models import X
"""

from ._base import (
    OptimizationBaseModel,
    OptimizationMetadata,
    OptimizationResultModel,
)
from ._results import (
    DroppedSection,
    DropReason,
    IndexingBatchResultModel,
    IndexingResultModel,
    IndexingSkipResultModel,
    ProgressiveLoadResult,
    RulesIndexingResultModel,
    RulesIndexResultModel,
    SummarizationResultModel,
)
from ._rules import (
    DetectedContextModel,
    IndexedRuleModel,
    OptimizationRuleCategory,
    RelevantRuleModel,
    RelevantRulesResultModel,
    RuleSectionModel,
    RulesManagerStatusModel,
    RulesResultModel,
    ScoredRuleModel,
)
from ._scoring import (
    FileContentMetadata,
    FileMetadataForScoring,
    FileRelevanceScoreModel,
    LoadedContentModel,
    LoadedFileContentModel,
    ParsedSectionModel,
    ScoredSectionModel,
    SectionScoreModel,
    SummarizationState,
)

__all__ = [
    "DetectedContextModel",
    "DroppedSection",
    "DropReason",
    "FileContentMetadata",
    "FileMetadataForScoring",
    "FileRelevanceScoreModel",
    "IndexedRuleModel",
    "IndexingBatchResultModel",
    "IndexingResultModel",
    "IndexingSkipResultModel",
    "LoadedContentModel",
    "LoadedFileContentModel",
    "OptimizationBaseModel",
    "OptimizationRuleCategory",
    "OptimizationMetadata",
    "OptimizationResultModel",
    "ParsedSectionModel",
    "ProgressiveLoadResult",
    "RelevantRuleModel",
    "RelevantRulesResultModel",
    "RuleSectionModel",
    "RulesIndexingResultModel",
    "RulesIndexResultModel",
    "RulesManagerStatusModel",
    "RulesResultModel",
    "ScoredRuleModel",
    "ScoredSectionModel",
    "SectionScoreModel",
    "SummarizationResultModel",
    "SummarizationState",
]
