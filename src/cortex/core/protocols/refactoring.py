#!/usr/bin/env python3
"""Refactoring protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for refactoring suggestion
generation and analysis operations.
"""

from typing import Protocol

from cortex.refactoring.models import (
    AnalysisDataModel,
    ConsolidationOpportunityModel,
    InsightDataModel,
    RefactoringImpactMetrics,
    RefactoringSuggestionModel,
    ReorganizationPlanModel,
    ReorganizationPreviewResult,
    SplitFileAnalysisResult,
    SplitRecommendationModel,
)


class RefactoringEngineProtocol(Protocol):
    """Protocol for refactoring operations using structural subtyping (PEP 544).

    This protocol defines the interface for generating and exporting refactoring
    suggestions based on pattern analysis and structural insights. Refactoring
    suggestions help improve Memory Bank organization and maintainability. A
    class implementing these methods automatically satisfies this protocol.

    Used by:
        - RefactoringEngine: Generates consolidation, split, and reorganization suggestions
        - MCP Tools: For get_refactoring_suggestions operations
        - InsightEngine: For actionable refactoring insights
        - Client Applications: For presenting refactoring options

    Example implementation:
        ```python
        class SimpleRefactoringEngine:
            async def generate_suggestions(
                self,
                insight_data: InsightDataModel,
                analysis_data: AnalysisDataModel,
                max_suggestions: int | None = None,
            ) -> list[RefactoringSuggestionModel]:
                suggestions = []

                # Consolidation suggestions
                if insight_data.duplicated_content:
                    for dup in insight_data.duplicated_content:
                        suggestions.append(RefactoringSuggestionModel(
                            suggestion_id=f"consolidate-{len(suggestions)}",
                            refactoring_type="consolidation",
                            priority="medium",
                            title="Consolidate duplicated content",
                            description="Duplicated content",
                            reasoning="Duplicated content",
                            affected_files=dup["files"],
                            confidence_score=0.8,
                        ))

                # Split suggestions
                if analysis_data.file_sizes:
                    for file_name, size in analysis_data.file_sizes.items():
                        if size > 10000:  # Large file threshold
                        suggestions.append(RefactoringSuggestionModel(
                            suggestion_id=f"split-{len(suggestions)}",
                            refactoring_type="split",
                            priority="medium",
                            title="Split large file",
                            description=f"File too large: {file_name}",
                            reasoning="File too large",
                            affected_files=[file_name],
                            confidence_score=0.7,
                        ))

                return suggestions[:max_suggestions] if max_suggestions else suggestions

            async def export_suggestions(
                self, suggestions: list[RefactoringSuggestionModel], format: str = "json"
            ) -> str:
                if format == "json":
                    return json.dumps(suggestions, indent=2)
                elif format == "markdown":
                    return "\\n".join([f"## {s['type']}: {s['reason']}" for s in suggestions])
                return str(suggestions)

        # SimpleRefactoringEngine automatically satisfies RefactoringEngineProtocol
        ```

    Note:
        - Generates multiple suggestion types
        - Confidence scores guide prioritization
        - Multiple export formats supported
    """

    async def generate_suggestions(
        self,
        insight_data: InsightDataModel,
        analysis_data: AnalysisDataModel,
        max_suggestions: int | None = None,
    ) -> list[RefactoringSuggestionModel]:
        """Generate refactoring suggestions.

        Args:
            insight_data: Insights from pattern analysis
            analysis_data: Structural analysis data
            max_suggestions: Maximum suggestions to generate

        Returns:
            List of refactoring suggestion models
        """
        ...

    async def export_suggestions(
        self, suggestions: list[RefactoringSuggestionModel], format: str = "json"
    ) -> str:
        """Export suggestions in specified format.

        Args:
            suggestions: List of suggestions
            format: Export format (json, markdown, text)

        Returns:
            Formatted suggestions string
        """
        ...


class ConsolidationDetectorProtocol(Protocol):
    """Protocol for consolidation detection operations using structural subtyping (PEP 544).

    This protocol defines the interface for detecting opportunities to consolidate
    duplicated content across files using transclusion. Consolidation reduces
    duplication and maintenance burden. A class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - ConsolidationDetector: Detects duplicate content and suggests transclusion
        - RefactoringEngine: For generating consolidation suggestions
        - DuplicationDetector: For identifying duplication patterns
        - MCP Tools: For analyze_consolidation operations

    Example implementation:
        ```python
        class SimpleConsolidationDetector:
            async def detect_opportunities(
                self,
                files: list[str] | None = None,
                suggest_transclusion: bool = True,
            ) -> list[ConsolidationOpportunityModel]:
                opportunities = []
                # Find duplicated content
                for file1, file2 in itertools.combinations(files or [], 2):
                    common = self._find_common_content(file1, file2)
                    if len(common) > 50:
                        opportunities.append(ConsolidationOpportunityModel(
                            opportunity_id=f"opp-{len(opportunities)}",
                            opportunity_type="similar_content",
                            affected_files=[file1, file2],
                            common_content=common,
                            similarity_score=0.85,
                            token_savings=len(common) * (2 - 1),
                            suggested_action="Use transclusion" if suggest_transclusion else "Extract to shared file",
                            extraction_target="shared-content.md",
                            transclusion_syntax=[
                                f"{{{{include:shared-content.md}}}}" if suggest_transclusion else ""
                            ],
                        ))
                return opportunities

            async def analyze_consolidation_impact(
                self, opportunity: ConsolidationOpportunityModel
            ) -> RefactoringImpactMetrics:
                from cortex.refactoring.models import RefactoringImpactMetrics
                files = opportunity.affected_files
                content_length = len(opportunity.common_content)
                return RefactoringImpactMetrics(
                    token_savings=content_length * (len(files) - 1),
                    files_affected=len(files),
                    maintainability_improvement=0.8 if len(files) > 2 else 0.5,
                )

        # SimpleConsolidationDetector automatically satisfies ConsolidationDetectorProtocol
        ```

    Note:
        - Identifies duplicated content across files
        - Suggests transclusion for DRY principle
        - Estimates maintenance savings
    """

    async def detect_opportunities(
        self,
        files: list[str] | None = None,
        suggest_transclusion: bool = True,
    ) -> list[ConsolidationOpportunityModel]:
        """Detect consolidation opportunities across files.

        Args:
            files: List of file paths to analyze (all if None)
            suggest_transclusion: Whether to suggest transclusion syntax

        Returns:
            List of consolidation opportunity models
        """
        ...

    async def analyze_consolidation_impact(
        self, opportunity: ConsolidationOpportunityModel
    ) -> RefactoringImpactMetrics:
        """Analyze impact of a consolidation opportunity.

        Args:
            opportunity: Consolidation opportunity model

        Returns:
            Impact analysis metrics model
        """
        ...


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
                        for i, s in enumerate(sections[len(sections)//2:] if should_split else [])
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


class ReorganizationPlannerProtocol(Protocol):
    """Protocol for reorganization planning operations using structural subtyping (PEP 544).

    This protocol defines the interface for creating comprehensive reorganization
    plans that optimize Memory Bank structure based on dependencies, access
    patterns, and other metrics. A class implementing these methods automatically
    satisfies this protocol.

    Used by:
        - ReorganizationPlanner: Creates and previews reorganization plans
        - RefactoringEngine: For generating reorganization suggestions
        - StructureAnalyzer: For optimizing file organization
        - MCP Tools: For plan_reorganization operations

    Example implementation:
        ```python
        class SimpleReorganizationPlanner:
            async def create_reorganization_plan(
                self,
                optimization_goal: str = "dependency_depth",
                max_depth: int | None = None,
            ) -> ReorganizationPlanModel:
                # Analyze current structure
                current_structure = await self._analyze_current_structure()

                # Generate reorganization plan
                moves = []
                if optimization_goal == "dependency_depth":
                    # Flatten dependency hierarchy
                    for file, depth in current_structure["file_depths"].items():
                        if max_depth and depth > max_depth:
                            new_path = self._calculate_optimal_path(file, max_depth)
                            moves.append(ReorganizationActionModel(
                                action_type="move",
                                from_path=file,
                                to_path=new_path,
                                reason=f"Reduce depth from {depth} to {max_depth}",
                            ))

                return ReorganizationPlanModel(
                    plan_id=f"plan-{optimization_goal}",
                    optimization_goal=optimization_goal,
                    current_structure=MemoryBankStructureData(),
                    proposed_structure=MemoryBankStructureData(),
                    actions=moves,
                )

            async def preview_reorganization(
                self, plan: ReorganizationPlanModel
            ) -> ReorganizationPreviewResult:
                return ReorganizationPreviewResult(
                    files_to_move=len(plan.actions),
                    estimated_improvement=plan.estimated_impact.complexity_reduction,
                    risks=self._assess_risks(plan),
                )

        # SimpleReorganizationPlanner automatically satisfies ReorganizationPlannerProtocol
        ```

    Note:
        - Multiple optimization goals supported
        - Preview before execution
        - Risk assessment included
    """

    async def create_reorganization_plan(
        self,
        optimization_goal: str = "dependency_depth",
        max_depth: int | None = None,
    ) -> ReorganizationPlanModel:
        """Create a reorganization plan.

        Args:
            optimization_goal: Goal for reorganization
            max_depth: Maximum dependency depth (None = no limit)

        Returns:
            Reorganization plan model
        """
        ...

    async def preview_reorganization(
        self, plan: ReorganizationPlanModel
    ) -> ReorganizationPreviewResult:
        """Preview impact of reorganization plan.

        Args:
            plan: Reorganization plan model

        Returns:
            Preview results model
        """
        ...


__all__ = [
    "RefactoringEngineProtocol",
    "ConsolidationDetectorProtocol",
    "SplitRecommenderProtocol",
    "ReorganizationPlannerProtocol",
]
