#!/usr/bin/env python3
"""Refactoring protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for refactoring suggestion
generation and analysis operations.
"""

from typing import Protocol

from cortex.refactoring.models import (
    SplitFileAnalysisResult,
    SplitRecommendationModel,
)


class SplitRecommenderProtocol(Protocol):
    """Protocol for file splitting recommendations using structural subtyping (PEP 544).

    This protocol defines the interface for suggesting file splitting opportunities
    based on size, complexity, and cohesion metrics. File splitting improves
    maintainability and navigability. A class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - SplitRecommender: Analyzes files and suggests splits
        - RefactoringEngine: For generating split suggestions
        - StructureAnalyzer: For identifying oversized files
        - MCP Tools: For analyze_splits operations

    Example implementation:
        ```python
        class SimpleSplitRecommender:
            async def suggest_file_splits(
                self,
                files: list[str] | None = None,
                strategies: list[str] | None = None,
            ) -> list[SplitRecommendationModel]:
                suggestions = []
                for file_path in (files or []):
                    analysis = await self.analyze_file(file_path)
                    if analysis.should_split:
                        from cortex.refactoring.models import SplitPointModel
                        suggestions.append(SplitRecommendationModel(
                            recommendation_id=f"split-{len(suggestions)}",
                            file_path=file_path,
                            reason=analysis.reason,
                            split_strategy="by_sections",
                            split_points=[
                                SplitPointModel(
                                    split_id=f"sp-{i}",
                                    section_title=sp.get("title", ""),
                                    line_number=sp.get("line", 0),
                                )
                                for i, sp in enumerate(analysis.split_points)
                            ],
                        ))
                return suggestions

            async def analyze_file(self, file_path: str) -> SplitFileAnalysisResult:
                size = await self._get_file_size(file_path)
                sections = await self._parse_sections(file_path)
                should_split = size > 10000 or len(sections) > 10
                return SplitFileAnalysisResult(
                    file=file_path,
                    size=size,
                    should_split=should_split,
                    reason="File too large" if size > 10000 else "Too many sections",
                    split_points=[
                        SplitPointModel(
                            section_heading=s.get("title", ""),
                            start_line=s.get("line", 0),
                            end_line=s.get("line", 0),
                            token_count=0,
                            independence_score=0.5,
                            suggested_filename=f"{file_path}.part{i}",
                            split_id=f"sp-{i}",
                            section_title=s.get("title", ""),
                            line_number=s.get("line", 0),
                        )
                        for i, s in enumerate(
                            sections[len(sections)//2:] if should_split else []
                        )
                    ],
                )

        # SimpleSplitRecommender automatically satisfies SplitRecommenderProtocol
        ```

    Note:
        - Multiple splitting strategies supported
        - Analyzes size, complexity, cohesion
        - Suggests logical split points
    """

    async def suggest_file_splits(
        self,
        files: list[str] | None = None,
        strategies: list[str] | None = None,
    ) -> list[SplitRecommendationModel]:
        """Suggest file splitting opportunities.

        Args:
            files: List of file paths to analyze (all if None)
            strategies: List of strategies to use (all if None)

        Returns:
            List of split recommendation models
        """
        ...

    async def analyze_file(self, file_path: str) -> SplitFileAnalysisResult:
        """Analyze a single file for splitting opportunities.

        Args:
            file_path: Path to file to analyze

        Returns:
            File analysis result model
        """
        ...


__all__ = [
    "SplitRecommenderProtocol",
]
