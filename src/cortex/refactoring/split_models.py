"""
Split Recommender Data Models

Dataclasses for split points and recommendations used by the split recommender.
"""

from __future__ import annotations

from dataclasses import dataclass

from cortex.core.models import ModelDict


@dataclass
class SplitPoint:
    """Represents a potential point to split a file"""

    section_heading: str
    start_line: int
    end_line: int
    token_count: int
    independence_score: float  # How independent this section is (0-1)
    suggested_filename: str


@dataclass
class SplitRecommendation:
    """Represents a recommendation to split a file"""

    recommendation_id: str
    file_path: str
    reason: str
    split_strategy: str  # "by_size", "by_sections", "by_topics", "by_dependencies"
    split_points: list[SplitPoint]
    estimated_impact: ModelDict
    new_structure: ModelDict  # Proposed new file structure
    maintain_dependencies: bool = True

    def to_dict(self) -> ModelDict:
        """Convert to dictionary"""
        return {
            "recommendation_id": self.recommendation_id,
            "file_path": self.file_path,
            "reason": self.reason,
            "split_strategy": self.split_strategy,
            "split_points": [
                {
                    "heading": sp.section_heading,
                    "lines": f"{sp.start_line}-{sp.end_line}",
                    "tokens": sp.token_count,
                    "independence": sp.independence_score,
                    "target_file": sp.suggested_filename,
                }
                for sp in self.split_points
            ],
            "estimated_impact": self.estimated_impact,
            "new_structure": self.new_structure,
            "maintain_dependencies": self.maintain_dependencies,
        }
