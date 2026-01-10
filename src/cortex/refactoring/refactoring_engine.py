"""
Refactoring Engine for MCP Memory Bank

This module generates intelligent refactoring suggestions based on pattern analysis,
structure analysis, and quality metrics. It coordinates with specialized detectors
for consolidation, splitting, and reorganization opportunities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import cast


class RefactoringType(Enum):
    """Types of refactoring suggestions"""

    CONSOLIDATION = "consolidation"
    SPLIT = "split"
    REORGANIZATION = "reorganization"
    TRANSCLUSION = "transclusion"
    RENAME = "rename"
    MERGE = "merge"


class RefactoringPriority(Enum):
    """Priority levels for refactoring suggestions"""

    CRITICAL = "critical"  # Significant issues, high impact
    HIGH = "high"  # Important improvements
    MEDIUM = "medium"  # Moderate improvements
    LOW = "low"  # Nice to have
    OPTIONAL = "optional"  # Minor optimizations


@dataclass
class RefactoringAction:
    """Represents a specific action in a refactoring"""

    action_type: str  # "move", "create", "delete", "modify", "rename"
    target_file: str
    description: str
    details: dict[str, object] = field(default_factory=lambda: {})


@dataclass
class RefactoringSuggestion:
    """Represents a refactoring suggestion"""

    suggestion_id: str
    refactoring_type: RefactoringType
    priority: RefactoringPriority
    title: str
    description: str
    reasoning: str
    affected_files: list[str]
    actions: list[RefactoringAction]
    estimated_impact: dict[str, object]
    confidence_score: float  # 0-1
    metadata: dict[str, object] = field(default_factory=lambda: {})
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, object]:
        """Convert suggestion to dictionary"""
        return {
            "suggestion_id": self.suggestion_id,
            "refactoring_type": self.refactoring_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "affected_files": self.affected_files,
            "actions": [
                {
                    "action_type": a.action_type,
                    "target_file": a.target_file,
                    "description": a.description,
                    "details": a.details,
                }
                for a in self.actions
            ],
            "estimated_impact": self.estimated_impact,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class RefactoringEngine:
    """
    Generates and manages refactoring suggestions.

    Coordinates with:
    - ConsolidationDetector for finding consolidation opportunities
    - SplitRecommender for suggesting file splits
    - ReorganizationPlanner for structural improvements
    """

    def __init__(
        self,
        memory_bank_path: Path,
        min_confidence: float = 0.7,
        max_suggestions_per_run: int = 10,
    ):
        """
        Initialize the refactoring engine.

        Args:
            memory_bank_path: Path to Memory Bank directory
            min_confidence: Minimum confidence score for suggestions (0-1)
            max_suggestions_per_run: Maximum number of suggestions to generate
        """
        self.memory_bank_path: Path = Path(memory_bank_path)
        self.min_confidence: float = min_confidence
        self.max_suggestions_per_run: int = max_suggestions_per_run

        # Storage for suggestions
        self.suggestions: dict[str, RefactoringSuggestion] = {}
        self.suggestion_counter: int = 0

    def generate_suggestion_id(self, refactoring_type: RefactoringType) -> str:
        """Generate unique suggestion ID"""
        self.suggestion_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        type_prefix = refactoring_type.value[:3].upper()
        return f"REF-{type_prefix}-{timestamp}-{self.suggestion_counter:03d}"

    async def generate_suggestions(
        self,
        pattern_data: dict[str, object] | None = None,
        structure_data: dict[str, object] | None = None,
        insights: list[dict[str, object]] | None = None,
        categories: list[str] | None = None,
    ) -> list[RefactoringSuggestion]:
        """
        Generate refactoring suggestions based on analysis data.

        Args:
            pattern_data: Pattern analysis results
            structure_data: Structure analysis results
            insights: Pre-generated insights
            categories: Categories to generate suggestions for

        Returns:
            List of refactoring suggestions
        """
        suggestions: list[RefactoringSuggestion] = []

        # Default to all categories if none specified
        if not categories:
            categories = ["consolidation", "split", "reorganization"]

        # Generate suggestions from insights
        if insights:
            await self._process_insights_for_suggestions(
                insights, categories, suggestions
            )

        # Generate additional suggestions from structure data
        if structure_data and "reorganization" in categories:
            org_suggestions = await self.generate_organization_suggestions(
                structure_data
            )
            suggestions.extend(org_suggestions)

        # Sort, limit, and store suggestions
        self._finalize_suggestions(suggestions)

        return suggestions

    async def _process_insights_for_suggestions(
        self,
        insights: list[dict[str, object]],
        categories: list[str],
        suggestions: list[RefactoringSuggestion],
    ) -> None:
        """Process insights and generate suggestions.

        Args:
            insights: List of insights to process
            categories: Categories to generate suggestions for
            suggestions: List to append suggestions to
        """
        for insight in insights:
            refactoring_type = self._determine_refactoring_type_from_insight(
                insight, categories
            )

            if refactoring_type:
                suggestion = await self.generate_from_insight(insight, refactoring_type)
                if suggestion and suggestion.confidence_score >= self.min_confidence:
                    suggestions.append(suggestion)

    def _determine_refactoring_type_from_insight(
        self, insight: dict[str, object], categories: list[str]
    ) -> RefactoringType | None:
        """Determine refactoring type from insight data.

        Uses insight ID first (most specific), then falls back to category.

        Args:
            insight: Insight dictionary
            categories: Available categories

        Returns:
            Refactoring type or None if cannot be determined
        """
        insight_id_raw = insight.get("id", "")
        category_raw = insight.get("category", "")
        insight_id = str(insight_id_raw)
        category = str(category_raw)

        # Try ID-based mapping first (most specific)
        refactoring_type = self._map_by_insight_id(insight_id, categories)
        if refactoring_type:
            return refactoring_type

        # Fall back to category-based mapping
        return self._map_by_category(category, insight_id, categories)

    def _map_by_insight_id(
        self, insight_id: str, categories: list[str]
    ) -> RefactoringType | None:
        """Map insight ID to refactoring type.

        Args:
            insight_id: Insight identifier
            categories: Available categories

        Returns:
            Refactoring type or None
        """
        # Large files → split
        if insight_id == "large_files" and "split" in categories:
            return RefactoringType.SPLIT

        # Dependency complexity → reorganization
        dependency_insights = {
            "dependency_complexity",
            "orphaned_files",
            "excessive_dependencies",
            "deep_dependencies",
        }
        if insight_id in dependency_insights and "reorganization" in categories:
            return RefactoringType.REORGANIZATION

        return None

    def _map_by_category(
        self, category: str, insight_id: str, categories: list[str]
    ) -> RefactoringType | None:
        """Map category to refactoring type.

        Args:
            category: Insight category
            insight_id: Insight identifier (for additional context)
            categories: Available categories

        Returns:
            Refactoring type or None
        """
        # Redundancy → consolidation
        if category == "redundancy" and "consolidation" in categories:
            return RefactoringType.CONSOLIDATION

        # Organization → split (for large files)
        if category == "organization" and "split" in categories:
            if insight_id in ["large_files", "large_average_size"]:
                return RefactoringType.SPLIT

        # Dependencies → reorganization
        if category == "dependencies" and "reorganization" in categories:
            return RefactoringType.REORGANIZATION

        return None

    def _finalize_suggestions(self, suggestions: list[RefactoringSuggestion]) -> None:
        """Sort, limit, and store suggestions.

        Args:
            suggestions: List of suggestions to finalize
        """

        # Sort by priority and confidence
        def _sort_key(s: RefactoringSuggestion) -> tuple[int, float]:
            return (self.priority_to_number(s.priority), -s.confidence_score)

        suggestions.sort(key=_sort_key)

        # Limit number of suggestions
        suggestions[:] = suggestions[: self.max_suggestions_per_run]

        # Store suggestions
        for suggestion in suggestions:
            self.suggestions[suggestion.suggestion_id] = suggestion

    async def generate_from_insight(
        self, insight: dict[str, object], refactoring_type: RefactoringType
    ) -> RefactoringSuggestion | None:
        """Generate a refactoring suggestion from an insight"""
        insight_data = self._extract_insight_data(insight)
        if not insight_data["valid"]:
            return None

        priority = self._map_severity_to_priority(cast(str, insight_data["severity"]))
        actions = self.generate_actions(
            refactoring_type,
            cast(list[str], insight_data["affected_files"]),
            cast(list[str], insight_data["recommendations"]),
        )
        if not actions:
            return None

        estimated_impact = self._calculate_estimated_impact(
            cast(float, insight_data["impact_score"]),
            cast(list[str], insight_data["affected_files"]),
        )
        suggestion_id = self.generate_suggestion_id(refactoring_type)

        return self._build_suggestion_from_insight(
            suggestion_id,
            refactoring_type,
            priority,
            insight_data,
            actions,
            estimated_impact,
            insight,
        )

    def generate_actions(
        self,
        refactoring_type: RefactoringType,
        affected_files: list[str],
        recommendations: list[str],
    ) -> list[RefactoringAction]:
        """Generate specific actions for a refactoring"""
        if refactoring_type == RefactoringType.CONSOLIDATION:
            return self._generate_consolidation_actions(affected_files)
        elif refactoring_type == RefactoringType.SPLIT:
            return self._generate_split_actions(affected_files)
        elif refactoring_type == RefactoringType.REORGANIZATION:
            return self._generate_reorganization_actions(affected_files)
        return []

    def _generate_consolidation_actions(
        self, affected_files: list[str]
    ) -> list[RefactoringAction]:
        """Generate consolidation actions.

        Args:
            affected_files: List of affected files

        Returns:
            List of consolidation actions
        """
        actions: list[RefactoringAction] = []

        if len(affected_files) >= 2:
            actions.append(
                RefactoringAction(
                    action_type="create",
                    target_file="memory-bank/shared-content.md",
                    description="Create shared content file for common sections",
                    details={
                        "source_files": affected_files,
                        "extraction_method": "common_sections",
                    },
                )
            )

            for file in affected_files:
                actions.append(
                    RefactoringAction(
                        action_type="modify",
                        target_file=file,
                        description=f"Replace duplicated content with transclusion in {Path(file).name}",
                        details={
                            "transclusion_target": "shared-content.md",
                            "replace_duplicates": True,
                        },
                    )
                )

        return actions

    def _generate_split_actions(
        self, affected_files: list[str]
    ) -> list[RefactoringAction]:
        """Generate split actions.

        Args:
            affected_files: List of affected files

        Returns:
            List of split actions
        """
        actions: list[RefactoringAction] = []

        for file in affected_files:
            file_name = Path(file).stem
            actions.append(
                RefactoringAction(
                    action_type="create",
                    target_file=f"memory-bank/{file_name}-part1.md",
                    description=f"Split {Path(file).name} into logical sections",
                    details={"source_file": file, "split_strategy": "by_sections"},
                )
            )

            actions.append(
                RefactoringAction(
                    action_type="modify",
                    target_file=file,
                    description=f"Update {Path(file).name} to reference split files",
                    details={"add_links": True, "create_index": True},
                )
            )

        return actions

    def _generate_reorganization_actions(
        self, affected_files: list[str]
    ) -> list[RefactoringAction]:
        """Generate reorganization actions.

        Args:
            affected_files: List of affected files

        Returns:
            List of reorganization actions
        """
        return [
            RefactoringAction(
                action_type="move",
                target_file="memory-bank/",
                description="Reorganize files into better structure",
                details={
                    "affected_files": affected_files,
                    "new_structure": "category_based",
                    "preserve_links": True,
                },
            )
        ]

    def build_reasoning(
        self, insight: dict[str, object], refactoring_type: RefactoringType
    ) -> str:
        """Build reasoning explanation for a suggestion"""

        reasoning_parts: list[str] = []

        # Add insight description
        description = insight.get("description", "")
        if description:
            reasoning_parts.append(f"Analysis shows: {description}")

        # Add type-specific reasoning
        if refactoring_type == RefactoringType.CONSOLIDATION:
            reasoning_parts.append(
                "Consolidating duplicate content will reduce token usage and "
                + "improve maintainability by having a single source of truth."
            )
        elif refactoring_type == RefactoringType.SPLIT:
            reasoning_parts.append(
                "Splitting large files into focused components will improve "
                + "context loading efficiency and make content easier to navigate."
            )
        elif refactoring_type == RefactoringType.REORGANIZATION:
            reasoning_parts.append(
                "Reorganizing the structure will reduce dependency complexity "
                + "and make the Memory Bank easier to understand and maintain."
            )

        # Add impact information
        impact_score = cast(float, insight.get("impact_score", 0))
        if impact_score > 0.7:
            reasoning_parts.append("This change has high potential impact.")

        return " ".join(reasoning_parts)

    async def generate_organization_suggestions(
        self, structure_data: dict[str, object]
    ) -> list[RefactoringSuggestion]:
        """Generate suggestions based on structure analysis"""
        suggestions: list[RefactoringSuggestion] = []
        anti_patterns = cast(dict[str, object], structure_data.get("anti_patterns", {}))
        orphaned = cast(list[str], anti_patterns.get("orphaned_files", []))

        if len(orphaned) >= 3:
            suggestion = self._create_orphaned_files_suggestion(orphaned)
            suggestions.append(suggestion)

        return suggestions

    def _create_orphaned_files_suggestion(
        self, orphaned: list[str]
    ) -> RefactoringSuggestion:
        """Create suggestion for orphaned files."""
        return RefactoringSuggestion(
            suggestion_id=self.generate_suggestion_id(RefactoringType.REORGANIZATION),
            refactoring_type=RefactoringType.REORGANIZATION,
            priority=RefactoringPriority.MEDIUM,
            title="Integrate Orphaned Files",
            description=f"Found {len(orphaned)} files with no dependencies",
            reasoning="Orphaned files may indicate content that should be integrated or removed.",
            affected_files=orphaned,
            actions=self._create_orphaned_files_actions(orphaned),
            estimated_impact={
                "token_savings": len(orphaned) * 100,
                "files_affected": len(orphaned),
                "complexity_reduction": 0.3,
            },
            confidence_score=0.65,
        )

    def _create_orphaned_files_actions(
        self, orphaned: list[str]
    ) -> list[RefactoringAction]:
        """Create actions for orphaned files."""
        return [
            RefactoringAction(
                action_type="modify",
                target_file=f,
                description=f"Add links to integrate {Path(f).name}",
                details={"add_dependencies": True},
            )
            for f in orphaned[:3]  # Limit actions
        ]

    def priority_to_number(self, priority: RefactoringPriority) -> int:
        """Convert priority to number for sorting (lower is higher priority)"""
        return {
            RefactoringPriority.CRITICAL: 0,
            RefactoringPriority.HIGH: 1,
            RefactoringPriority.MEDIUM: 2,
            RefactoringPriority.LOW: 3,
            RefactoringPriority.OPTIONAL: 4,
        }[priority]

    async def get_suggestion(self, suggestion_id: str) -> RefactoringSuggestion | None:
        """Get a specific suggestion by ID"""
        return self.suggestions.get(suggestion_id)

    async def preview_refactoring(
        self, suggestion_id: str, show_diff: bool = True
    ) -> dict[str, object]:
        """
        Preview the impact of a refactoring suggestion.

        Args:
            suggestion_id: ID of the suggestion to preview
            show_diff: Whether to include diff preview

        Returns:
            Preview information including estimated changes
        """
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            return {"error": f"Suggestion {suggestion_id} not found"}

        actions_list: list[dict[str, object]] = []
        preview: dict[str, object] = {
            "suggestion_id": suggestion_id,
            "title": suggestion.title,
            "refactoring_type": suggestion.refactoring_type.value,
            "affected_files": suggestion.affected_files,
            "actions_count": len(suggestion.actions),
            "estimated_impact": suggestion.estimated_impact,
            "actions": actions_list,
        }

        # Add action details
        for action in suggestion.actions:
            action_preview: dict[str, object] = {
                "action_type": action.action_type,
                "target_file": action.target_file,
                "description": action.description,
            }

            if show_diff:
                # In a real implementation, this would generate actual diffs
                action_preview["preview"] = (
                    f"[Preview of changes for {action.target_file}]"
                )

            actions_list.append(action_preview)

        return preview

    async def get_all_suggestions(
        self,
        filter_by_type: RefactoringType | None = None,
        filter_by_priority: RefactoringPriority | None = None,
        min_confidence: float | None = None,
    ) -> list[RefactoringSuggestion]:
        """
        Get all suggestions with optional filtering.

        Args:
            filter_by_type: Filter by refactoring type
            filter_by_priority: Filter by priority level
            min_confidence: Minimum confidence score

        Returns:
            List of matching suggestions
        """
        suggestions = list(self.suggestions.values())

        if filter_by_type:
            suggestions = [
                s for s in suggestions if s.refactoring_type == filter_by_type
            ]

        if filter_by_priority:
            suggestions = [s for s in suggestions if s.priority == filter_by_priority]

        if min_confidence is not None:
            suggestions = [
                s for s in suggestions if s.confidence_score >= min_confidence
            ]

        return suggestions

    async def export_suggestions(self, output_format: str = "json") -> str:
        """
        Export all suggestions to a formatted string.

        Args:
            output_format: Format for export ("json", "markdown", "text")

        Returns:
            Formatted string of suggestions
        """
        suggestions = list(self.suggestions.values())

        if output_format == "json":
            return json.dumps([s.to_dict() for s in suggestions], indent=2)
        elif output_format == "markdown":
            return _format_suggestions_markdown(suggestions)
        else:  # text
            return _format_suggestions_text(suggestions)

    async def clear_suggestions(self):
        """Clear all stored suggestions"""
        self.suggestions.clear()
        self.suggestion_counter = 0

    def _extract_insight_data(self, insight: dict[str, object]) -> dict[str, object]:
        """Extract and validate insight data."""
        title = cast(str, insight.get("title", ""))
        affected_files = cast(list[str], insight.get("affected_files", []))
        return {
            "title": title,
            "description": cast(str, insight.get("description", "")),
            "impact_score": cast(float, insight.get("impact_score", 0.5)),
            "severity": cast(str, insight.get("severity", "medium")),
            "recommendations": cast(list[str], insight.get("recommendations", [])),
            "affected_files": affected_files,
            "valid": bool(title and affected_files),
        }

    def _map_severity_to_priority(self, severity: str) -> RefactoringPriority:
        """Map severity string to RefactoringPriority enum."""
        priority_map = {
            "high": RefactoringPriority.HIGH,
            "medium": RefactoringPriority.MEDIUM,
            "low": RefactoringPriority.LOW,
        }
        return priority_map.get(severity, RefactoringPriority.MEDIUM)

    def _calculate_estimated_impact(
        self, impact_score: float, affected_files: list[str]
    ) -> dict[str, object]:
        """Calculate estimated impact from insight data."""
        return cast(
            dict[str, object],
            {
                "token_savings": int(impact_score * 1000),
                "files_affected": len(affected_files),
                "complexity_reduction": impact_score * 0.5,
                "maintainability_improvement": impact_score * 0.7,
            },
        )

    def _build_suggestion_from_insight(
        self,
        suggestion_id: str,
        refactoring_type: RefactoringType,
        priority: RefactoringPriority,
        insight_data: dict[str, object],
        actions: list[RefactoringAction],
        estimated_impact: dict[str, object],
        insight: dict[str, object],
    ) -> RefactoringSuggestion:
        """Build RefactoringSuggestion from insight data."""
        return RefactoringSuggestion(
            suggestion_id=suggestion_id,
            refactoring_type=refactoring_type,
            priority=priority,
            title=cast(str, insight_data["title"]),
            description=cast(str, insight_data["description"]),
            reasoning=self.build_reasoning(insight, refactoring_type),
            affected_files=cast(list[str], insight_data["affected_files"]),
            actions=actions,
            estimated_impact=estimated_impact,
            confidence_score=cast(float, insight_data["impact_score"]),
            metadata={
                "source": "insight",
                "insight_category": insight.get("category", ""),
                "recommendations": cast(list[str], insight_data["recommendations"]),
            },
        )


def _format_suggestions_markdown(suggestions: list[RefactoringSuggestion]) -> str:
    """Format suggestions as markdown.

    Args:
        suggestions: List of suggestion objects

    Returns:
        Markdown formatted string
    """
    lines = ["# Refactoring Suggestions\n"]

    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"## {i}. {suggestion.title}")
        lines.append(f"**ID:** `{suggestion.suggestion_id}`")
        lines.append(f"**Type:** {suggestion.refactoring_type.value}")
        lines.append(f"**Priority:** {suggestion.priority.value}")
        lines.append(f"**Confidence:** {suggestion.confidence_score:.2f}")
        lines.append(f"\n{suggestion.description}\n")
        lines.append(f"**Reasoning:** {suggestion.reasoning}\n")
        lines.append(f"**Affected Files:** {len(suggestion.affected_files)}")
        lines.append(f"**Actions:** {len(suggestion.actions)}\n")

        impact = suggestion.estimated_impact
        lines.append("**Estimated Impact:**")
        lines.append(f"- Token Savings: ~{impact.get('token_savings', 0):,}")
        lines.append(f"- Files Affected: {impact.get('files_affected', 0)}")
        lines.append(
            f"- Complexity Reduction: {impact.get('complexity_reduction', 0):.2%}\n"
        )
        lines.append("---\n")

    return "\n".join(lines)


def _format_suggestions_text(suggestions: list[RefactoringSuggestion]) -> str:
    """Format suggestions as plain text.

    Args:
        suggestions: List of suggestion objects

    Returns:
        Plain text formatted string
    """
    lines = ["REFACTORING SUGGESTIONS", "=" * 50, ""]

    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"{i}. {suggestion.title}")
        lines.append(f"   ID: {suggestion.suggestion_id}")
        lines.append(f"   Type: {suggestion.refactoring_type.value}")
        lines.append(f"   Priority: {suggestion.priority.value}")
        lines.append(f"   Confidence: {suggestion.confidence_score:.2f}")
        lines.append(f"   Files: {len(suggestion.affected_files)}")
        lines.append(f"   Actions: {len(suggestion.actions)}")
        lines.append("")

    return "\n".join(lines)
