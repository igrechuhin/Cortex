"""
Data models for consolidation detection.

Extracted from consolidation_detector.py for file size compliance.
"""

from dataclasses import dataclass, field
from typing import cast

from cortex.core.models import JsonValue, ModelDict


@dataclass
class ConsolidationOpportunity:
    """Represents an opportunity to consolidate content"""

    opportunity_id: str
    opportunity_type: str  # "exact_duplicate", "similar_content", "shared_section"
    affected_files: list[str]
    common_content: str
    similarity_score: float  # 0-1
    token_savings: int
    suggested_action: str
    extraction_target: str  # Where to extract the common content
    transclusion_syntax: list[str]  # Transclusion syntax for each file
    details: ModelDict = field(default_factory=lambda: {})

    def to_dict(self) -> ModelDict:
        """Convert to dictionary"""
        affected_files_json = cast(list[JsonValue], self.affected_files)
        transclusion_syntax_json = cast(list[JsonValue], self.transclusion_syntax)
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "affected_files": affected_files_json,
            "common_content_preview": (
                self.common_content[:200] + "..."
                if len(self.common_content) > 200
                else self.common_content
            ),
            "similarity_score": self.similarity_score,
            "token_savings": self.token_savings,
            "suggested_action": self.suggested_action,
            "extraction_target": self.extraction_target,
            "transclusion_syntax": transclusion_syntax_json,
            "details": self.details,
        }
