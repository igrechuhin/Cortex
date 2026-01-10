#!/usr/bin/env python3
"""Refactoring protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for refactoring suggestion
generation and analysis operations.
"""

from typing import Protocol


class RefactoringEngineProtocol(Protocol):
    """Protocol for refactoring operations using structural subtyping (PEP 544).

    This protocol defines the interface for generating and exporting refactoring
    suggestions based on pattern analysis and structural insights. Refactoring
    suggestions help improve Memory Bank organization and maintainability. Any
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
                insight_data: dict[str, object],
                analysis_data: dict[str, object],
                max_suggestions: int | None = None,
            ) -> list[dict[str, object]]:
                suggestions = []

                # Consolidation suggestions
                if "duplicated_content" in insight_data:
                    for dup in insight_data["duplicated_content"]:
                        suggestions.append({
                            "type": "consolidate",
                            "files": dup["files"],
                            "reason": "Duplicated content",
                            "confidence": 0.8,
                        })

                # Split suggestions
                if "large_files" in analysis_data:
                    for large_file in analysis_data["large_files"]:
                        suggestions.append({
                            "type": "split",
                            "file": large_file["name"],
                            "reason": f"File too large",
                            "confidence": 0.7,
                        })

                return suggestions[:max_suggestions] if max_suggestions else suggestions

            async def export_suggestions(
                self, suggestions: list[dict[str, object]], format: str = "json"
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
        insight_data: dict[str, object],
        analysis_data: dict[str, object],
        max_suggestions: int | None = None,
    ) -> list[dict[str, object]]:
        """Generate refactoring suggestions.

        Args:
            insight_data: Insights from pattern analysis
            analysis_data: Structural analysis data
            max_suggestions: Maximum suggestions to generate

        Returns:
            List of refactoring suggestions
        """
        ...

    async def export_suggestions(
        self, suggestions: list[dict[str, object]], format: str = "json"
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
    duplication and maintenance burden. Any class implementing these methods
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
            ) -> list[dict[str, object]]:
                opportunities = []
                # Find duplicated content
                for file1, file2 in itertools.combinations(files or [], 2):
                    common = self._find_common_content(file1, file2)
                    if len(common) > 50:
                        opportunities.append({
                            "files": [file1, file2],
                            "duplicated_content": common,
                            "suggestion": "Use transclusion" if suggest_transclusion else None,
                        })
                return opportunities

            async def analyze_consolidation_impact(
                self, opportunity: dict[str, object]
            ) -> dict[str, object]:
                files = opportunity["files"]
                content_length = len(opportunity["duplicated_content"])
                return {
                    "files_affected": len(files),
                    "estimated_savings": content_length * (len(files) - 1),
                    "maintenance_improvement": "High" if len(files) > 2 else "Medium",
                }

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
    ) -> list[dict[str, object]]:
        """Detect consolidation opportunities across files.

        Args:
            files: List of file paths to analyze (all if None)
            suggest_transclusion: Whether to suggest transclusion syntax

        Returns:
            List of consolidation opportunity dictionaries
        """
        ...

    async def analyze_consolidation_impact(
        self, opportunity: dict[str, object]
    ) -> dict[str, object]:
        """Analyze impact of a consolidation opportunity.

        Args:
            opportunity: Consolidation opportunity dictionary

        Returns:
            Impact analysis dictionary
        """
        ...


class SplitRecommenderProtocol(Protocol):
    """Protocol for file splitting recommendations using structural subtyping (PEP 544).

    This protocol defines the interface for suggesting file splitting opportunities
    based on size, complexity, and cohesion metrics. File splitting improves
    maintainability and navigability. Any class implementing these methods
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
            ) -> list[dict[str, object]]:
                suggestions = []
                for file_path in (files or []):
                    analysis = await self.analyze_file(file_path)
                    if analysis["should_split"]:
                        suggestions.append({
                            "file": file_path,
                            "reason": analysis["reason"],
                            "suggested_splits": analysis["split_points"],
                        })
                return suggestions

            async def analyze_file(self, file_path: str) -> dict[str, object]:
                size = await self._get_file_size(file_path)
                sections = await self._parse_sections(file_path)
                should_split = size > 10000 or len(sections) > 10
                return {
                    "file": file_path,
                    "size": size,
                    "should_split": should_split,
                    "reason": "File too large" if size > 10000 else "Too many sections",
                    "split_points": sections[len(sections)//2:] if should_split else [],
                }

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
    ) -> list[dict[str, object]]:
        """Suggest file splitting opportunities.

        Args:
            files: List of file paths to analyze (all if None)
            strategies: List of strategies to use (all if None)

        Returns:
            List of split suggestion dictionaries
        """
        ...

    async def analyze_file(self, file_path: str) -> dict[str, object]:
        """Analyze a single file for splitting opportunities.

        Args:
            file_path: Path to file to analyze

        Returns:
            File analysis dictionary
        """
        ...


class ReorganizationPlannerProtocol(Protocol):
    """Protocol for reorganization planning operations using structural subtyping (PEP 544).

    This protocol defines the interface for creating comprehensive reorganization
    plans that optimize Memory Bank structure based on dependencies, access
    patterns, and other metrics. Any class implementing these methods automatically
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
            ) -> dict[str, object]:
                # Analyze current structure
                current_structure = await self._analyze_current_structure()

                # Generate reorganization plan
                moves = []
                if optimization_goal == "dependency_depth":
                    # Flatten dependency hierarchy
                    for file, depth in current_structure["file_depths"].items():
                        if max_depth and depth > max_depth:
                            new_path = self._calculate_optimal_path(file, max_depth)
                            moves.append({"from": file, "to": new_path})

                return {
                    "goal": optimization_goal,
                    "moves": moves,
                    "estimated_improvement": len(moves) * 0.1,
                }

            async def preview_reorganization(
                self, plan: dict[str, object]
            ) -> dict[str, object]:
                return {
                    "files_to_move": len(plan["moves"]),
                    "estimated_improvement": plan["estimated_improvement"],
                    "risks": self._assess_risks(plan),
                }

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
    ) -> dict[str, object]:
        """Create a reorganization plan.

        Args:
            optimization_goal: Goal for reorganization
            max_depth: Maximum dependency depth (None = no limit)

        Returns:
            Reorganization plan dictionary
        """
        ...

    async def preview_reorganization(
        self, plan: dict[str, object]
    ) -> dict[str, object]:
        """Preview impact of reorganization plan.

        Args:
            plan: Reorganization plan

        Returns:
            Preview results dictionary
        """
        ...


__all__ = [
    "RefactoringEngineProtocol",
    "ConsolidationDetectorProtocol",
    "SplitRecommenderProtocol",
    "ReorganizationPlannerProtocol",
]
