"""
Refactoring Engine for MCP Memory Bank.

This module generates and stores refactoring suggestions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.refactoring.models import (
    ActionDetails,
    RefactoringActionModel,
    RefactoringImpactMetrics,
    RefactoringMetadata,
    RefactoringPriority,
    RefactoringSuggestionModel,
    RefactoringType,
)

InsightDict = ModelDict


class RefactoringEngine:
    """Generate and manage refactoring suggestions."""

    def __init__(
        self,
        memory_bank_path: Path,
        min_confidence: float = 0.7,
        max_suggestions_per_run: int = 10,
    ) -> None:
        self.memory_bank_path = Path(memory_bank_path)
        self.min_confidence = min_confidence
        self.max_suggestions_per_run = max_suggestions_per_run

        self._suggestions: dict[str, RefactoringSuggestionModel] = {}
        self._suggestion_counter = 0

    @property
    def suggestions(self) -> dict[str, RefactoringSuggestionModel]:
        return self._suggestions

    @property
    def suggestion_counter(self) -> int:
        return self._suggestion_counter

    def generate_suggestion_id(self, refactoring_type: RefactoringType) -> str:
        self._suggestion_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        type_prefix = refactoring_type.value[:3].upper()
        return f"REF-{type_prefix}-{timestamp}-{self._suggestion_counter:03d}"

    def priority_to_number(self, priority: RefactoringPriority) -> int:
        return _priority_to_number(priority)

    def build_reasoning(
        self, insight: InsightDict, refactoring_type: RefactoringType
    ) -> str:
        return _build_reasoning(insight, refactoring_type)

    def generate_actions(
        self,
        refactoring_type: RefactoringType,
        affected_files: list[str],
        _dependencies: list[str],
    ) -> list[RefactoringActionModel]:
        """Generate actions for a refactoring type and affected files."""
        return _generate_actions(refactoring_type, affected_files)

    async def generate_from_insight(
        self, insight: InsightDict, refactoring_type: RefactoringType
    ) -> RefactoringSuggestionModel | None:
        """Generate a single suggestion from an insight dict.

        Returns None if the insight does not contain enough information.
        """
        title = insight.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        model = _build_suggestion_from_insight(self, insight, refactoring_type)
        if model.confidence_score < self.min_confidence:
            return None
        return model

    async def generate_organization_suggestions(
        self, structure_data: ModelDict
    ) -> list[RefactoringSuggestionModel]:
        """Generate organization suggestions from structure analysis results."""
        anti_patterns_raw: JsonValue = structure_data.get("anti_patterns", {})
        anti_patterns = (
            cast(ModelDict, anti_patterns_raw)
            if isinstance(anti_patterns_raw, dict)
            else {}
        )
        orphaned_raw = anti_patterns.get("orphaned_files", [])
        orphaned_files = self._extract_orphaned_files(orphaned_raw)
        if len(orphaned_files) < 3:
            return []
        return self._build_organization_suggestion(orphaned_files)

    def _extract_orphaned_files(self, orphaned_raw: JsonValue) -> list[str]:
        """Extract orphaned files from raw data."""
        orphaned_files: list[str] = []
        if isinstance(orphaned_raw, list):
            for file_item in cast(list[JsonValue], orphaned_raw):
                if file_item is not None:
                    orphaned_files.append(str(file_item))
        return orphaned_files

    def _build_organization_suggestion(
        self, orphaned_files: list[str]
    ) -> list[RefactoringSuggestionModel]:
        """Build organization suggestion from orphaned files."""
        suggestion_id = self.generate_suggestion_id(RefactoringType.REORGANIZATION)
        actions = self._build_organization_actions(orphaned_files)
        impact = RefactoringImpactMetrics(
            files_affected=len(orphaned_files),
            token_savings=0,
            complexity_reduction=0.0,
        )
        metadata = RefactoringMetadata(source="structure")
        return [
            RefactoringSuggestionModel(
                suggestion_id=suggestion_id,
                refactoring_type=RefactoringType.REORGANIZATION,
                priority=RefactoringPriority.MEDIUM,
                title=f"Orphaned files detected ({len(orphaned_files)})",
                description="Several files are not referenced by others. Consider reorganizing to improve discoverability.",
                reasoning="Orphaned files are hard to discover and can indicate missing links or poor structure.",
                affected_files=orphaned_files,
                actions=actions,
                estimated_impact=impact,
                confidence_score=0.75,
                metadata=metadata,
            )
        ]

    def _build_organization_actions(
        self, orphaned_files: list[str]
    ) -> list[RefactoringActionModel]:
        """Build actions for organization suggestion."""
        return [
            RefactoringActionModel(
                action_type="move",
                target_file=str(f),
                description="Integrate orphaned file into a suitable category",
            )
            for f in orphaned_files[:3]
        ]

    async def get_suggestion(
        self, suggestion_id: str
    ) -> RefactoringSuggestionModel | None:
        return self._suggestions.get(suggestion_id)

    async def get_all_suggestions(
        self,
        filter_by_type: RefactoringType | None = None,
        filter_by_priority: RefactoringPriority | None = None,
        min_confidence: float | None = None,
    ) -> list[RefactoringSuggestionModel]:
        suggestions = list(self._suggestions.values())
        if filter_by_type is not None:
            suggestions = [
                s for s in suggestions if s.refactoring_type == filter_by_type
            ]
        if filter_by_priority is not None:
            suggestions = [s for s in suggestions if s.priority == filter_by_priority]
        if min_confidence is not None:
            suggestions = [
                s for s in suggestions if s.confidence_score >= min_confidence
            ]
        return suggestions

    async def clear_suggestions(self) -> None:
        self._suggestions.clear()
        self._suggestion_counter = 0

    async def export_suggestions(self, output_format: str = "json") -> str:
        suggestions = list(self._suggestions.values())
        if output_format == "json":
            return json.dumps(
                [s.model_dump(mode="json") for s in suggestions], indent=2
            )
        if output_format == "markdown":
            return _format_suggestions_markdown(suggestions)
        return _format_suggestions_text(suggestions)

    async def preview_refactoring(
        self, suggestion_id: str, show_diff: bool = True
    ) -> ModelDict:
        suggestion = await self.get_suggestion(suggestion_id)
        if suggestion is None:
            return {"error": f"Suggestion {suggestion_id} not found"}

        actions: list[ModelDict] = []
        for a in suggestion.actions:
            action_dict: ModelDict = {
                "action_type": a.action_type,
                "target_file": a.target_file,
                "description": a.description,
            }
            if show_diff:
                action_dict["preview"] = f"[Preview of changes for {a.target_file}]"
            actions.append(action_dict)

        affected_files_json = cast(list[JsonValue], list(suggestion.affected_files))
        actions_json: list[JsonValue] = [cast(JsonValue, item) for item in actions]
        estimated_impact = cast(ModelDict, dict(suggestion.estimated_impact))
        return {
            "suggestion_id": suggestion.suggestion_id,
            "title": suggestion.title,
            "refactoring_type": suggestion.refactoring_type.value,
            "affected_files": affected_files_json,
            "actions_count": len(suggestion.actions),
            "estimated_impact": estimated_impact,
            "actions": actions_json,
        }

    async def generate_suggestions(
        self,
        insights: list[InsightDict] | None = None,
        categories: list[str] | None = None,
        structure_data: ModelDict | None = None,
        dependency_graph: ModelDict | None = None,
    ) -> list[RefactoringSuggestionModel]:
        """Generate suggestions from pre-generated insight dictionaries."""
        _ = dependency_graph
        if not categories:
            categories = ["consolidation", "split", "reorganization"]

        suggestion_models = self._build_suggestions_from_insights(insights, categories)
        suggestions = await self._merge_and_sort_suggestions(
            suggestion_models, structure_data
        )

        return suggestions

    def _build_suggestions_from_insights(
        self,
        insights: list[InsightDict] | None,
        categories: list[str],
    ) -> list[RefactoringSuggestionModel]:
        """Build suggestions from insights."""
        suggestion_models: list[RefactoringSuggestionModel] = []
        if insights:
            for insight in insights:
                ref_type = _determine_refactoring_type(insight, categories)
                if ref_type is None:
                    continue
                suggestion = _build_suggestion_from_insight(self, insight, ref_type)
                if suggestion.confidence_score >= self.min_confidence:
                    suggestion_models.append(suggestion)
        suggestion_models.sort(
            key=lambda s: (_priority_to_number(s.priority), -s.confidence_score)
        )
        return suggestion_models[: self.max_suggestions_per_run]

    async def _merge_and_sort_suggestions(
        self,
        suggestion_models: list[RefactoringSuggestionModel],
        structure_data: ModelDict | None,
    ) -> list[RefactoringSuggestionModel]:
        """Merge and sort all suggestions."""
        suggestions: list[RefactoringSuggestionModel] = list(suggestion_models)
        if structure_data is not None:
            suggestions.extend(
                await self.generate_organization_suggestions(structure_data)
            )
        suggestions.sort(
            key=lambda s: (_priority_to_number(s.priority), -s.confidence_score)
        )
        suggestions = suggestions[: self.max_suggestions_per_run]
        for s in suggestions:
            self._suggestions[s.suggestion_id] = s
        return suggestions


def _priority_to_number(priority: RefactoringPriority) -> int:
    return {
        RefactoringPriority.CRITICAL: 0,
        RefactoringPriority.HIGH: 1,
        RefactoringPriority.MEDIUM: 2,
        RefactoringPriority.LOW: 3,
        RefactoringPriority.OPTIONAL: 4,
    }[priority]


def _determine_refactoring_type(
    insight: InsightDict, categories: list[str]
) -> RefactoringType | None:
    insight_id = str(insight.get("id", "") or "")
    category = str(insight.get("category", "") or "")

    if insight_id == "large_files" and "split" in categories:
        return RefactoringType.SPLIT

    dependency_insights = {
        "dependency_complexity",
        "orphaned_files",
        "excessive_dependencies",
        "deep_dependencies",
    }
    if insight_id in dependency_insights and "reorganization" in categories:
        return RefactoringType.REORGANIZATION

    if category == "redundancy" and "consolidation" in categories:
        return RefactoringType.CONSOLIDATION
    if category == "organization" and "split" in categories:
        return RefactoringType.SPLIT
    if category == "dependencies" and "reorganization" in categories:
        return RefactoringType.REORGANIZATION

    return None


def _build_suggestion_from_insight(
    engine: RefactoringEngine, insight: InsightDict, refactoring_type: RefactoringType
) -> RefactoringSuggestionModel:
    title = str(insight.get("title", "") or "")
    affected_files = _extract_affected_files(insight)
    recommendations = _extract_recommendations(insight)
    impact_score = _extract_impact_score(insight)
    priority = _determine_priority_from_severity(insight)
    suggestion_id = engine.generate_suggestion_id(refactoring_type)
    actions = _generate_actions(refactoring_type, affected_files)
    estimated_impact = _build_estimated_impact(impact_score, affected_files)
    metadata = _build_refactoring_metadata(insight, recommendations)
    reasoning = _build_reasoning(insight, refactoring_type)

    return RefactoringSuggestionModel(
        suggestion_id=suggestion_id,
        refactoring_type=refactoring_type,
        priority=priority,
        title=title,
        description=str(insight.get("description", "") or ""),
        reasoning=reasoning,
        affected_files=affected_files,
        actions=actions,
        estimated_impact=estimated_impact,
        confidence_score=impact_score,
        metadata=metadata,
    )


def _extract_affected_files(insight: InsightDict) -> list[str]:
    """Extract affected files from insight."""
    affected_files: list[str] = []
    affected_files_raw: JsonValue = insight.get("affected_files", [])
    if isinstance(affected_files_raw, list):
        for file_item in cast(list[JsonValue], affected_files_raw):
            if file_item is not None:
                affected_files.append(str(file_item))
    return affected_files


def _extract_recommendations(insight: InsightDict) -> list[str]:
    """Extract recommendations from insight."""
    recommendations: list[str] = []
    recommendations_raw: JsonValue = insight.get("recommendations", [])
    if isinstance(recommendations_raw, list):
        for rec_item in cast(list[JsonValue], recommendations_raw):
            if rec_item is not None:
                recommendations.append(str(rec_item))
    return recommendations


def _extract_impact_score(insight: InsightDict) -> float:
    """Extract impact score from insight."""
    impact_score_raw = insight.get("impact_score", 0.5)
    return (
        float(impact_score_raw) if isinstance(impact_score_raw, (int, float)) else 0.5
    )


def _determine_priority_from_severity(insight: InsightDict) -> RefactoringPriority:
    """Determine priority from severity."""
    severity = str(insight.get("severity", "medium") or "medium")
    return {
        "high": RefactoringPriority.HIGH,
        "medium": RefactoringPriority.MEDIUM,
        "low": RefactoringPriority.LOW,
    }.get(severity, RefactoringPriority.MEDIUM)


def _build_estimated_impact(
    impact_score: float, affected_files: list[str]
) -> RefactoringImpactMetrics:
    """Build estimated impact metrics."""
    return RefactoringImpactMetrics(
        token_savings=int(impact_score * 1000),
        files_affected=len(affected_files),
        complexity_reduction=impact_score * 0.5,
        maintainability_improvement=impact_score * 0.7,
        risk_level="low",
    )


def _build_refactoring_metadata(
    insight: InsightDict, recommendations: list[str]
) -> RefactoringMetadata:
    """Build refactoring metadata."""
    return RefactoringMetadata(
        source="insight",
        insight_category=str(insight.get("category", "") or ""),
        recommendations=recommendations,
    )


def _generate_actions(
    refactoring_type: RefactoringType, affected_files: list[str]
) -> list[RefactoringActionModel]:
    if refactoring_type == RefactoringType.CONSOLIDATION:
        return _generate_consolidation_actions(affected_files)
    if refactoring_type == RefactoringType.SPLIT:
        return _generate_split_actions(affected_files)
    if refactoring_type == RefactoringType.REORGANIZATION:
        return _generate_reorganization_actions(affected_files)
    return []


def _generate_consolidation_actions(
    affected_files: list[str],
) -> list[RefactoringActionModel]:
    """Generate consolidation actions."""
    if len(affected_files) < 2:
        return []
    return [
        RefactoringActionModel(
            action_type="create",
            target_file="memory-bank/shared-content.md",
            description="Create shared content file for common sections",
            details=ActionDetails(source_files=affected_files),
        ),
        *[
            RefactoringActionModel(
                action_type="modify",
                target_file=f,
                description=f"Replace duplicated content with transclusion in {Path(f).name}",
                details=ActionDetails(source_file=f),
            )
            for f in affected_files
        ],
    ]


def _generate_split_actions(
    affected_files: list[str],
) -> list[RefactoringActionModel]:
    """Generate split actions."""
    actions: list[RefactoringActionModel] = []
    for f in affected_files:
        actions.append(
            RefactoringActionModel(
                action_type="create",
                target_file=f"memory-bank/{Path(f).stem}-part1.md",
                description=f"Split {Path(f).name} into logical sections",
                details=ActionDetails(source_file=f),
            )
        )
        actions.append(
            RefactoringActionModel(
                action_type="modify",
                target_file=f,
                description=f"Update {Path(f).name} to reference split files",
                details=ActionDetails(source_file=f),
            )
        )
    return actions


def _generate_reorganization_actions(
    affected_files: list[str],
) -> list[RefactoringActionModel]:
    """Generate reorganization actions."""
    return [
        RefactoringActionModel(
            action_type="move",
            target_file="memory-bank/",
            description="Reorganize files into better structure",
            details=ActionDetails(source_files=affected_files),
        )
    ]


def _build_reasoning(insight: InsightDict, refactoring_type: RefactoringType) -> str:
    reasoning_parts: list[str] = []
    description = insight.get("description", "")
    if description:
        reasoning_parts.append(f"Analysis shows: {description}")

    if refactoring_type == RefactoringType.CONSOLIDATION:
        reasoning_parts.append(
            "Consolidating duplicate content reduces token usage and improves maintainability."
        )
    elif refactoring_type == RefactoringType.SPLIT:
        reasoning_parts.append(
            "Splitting large files improves context loading efficiency and navigation."
        )
    elif refactoring_type == RefactoringType.REORGANIZATION:
        reasoning_parts.append(
            "Reorganizing structure reduces dependency complexity and improves discoverability."
        )

    impact_score_raw = insight.get("impact_score", 0.0)
    impact_score = (
        float(impact_score_raw) if isinstance(impact_score_raw, (int, float)) else 0.0
    )
    if impact_score > 0.7:
        reasoning_parts.append("This change has high potential impact.")

    return " ".join(reasoning_parts)


def _format_suggestions_markdown(suggestions: list[RefactoringSuggestionModel]) -> str:
    lines = ["# Refactoring Suggestions\n"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"## {i}. {s.title}")
        lines.append(f"**ID:** `{s.suggestion_id}`")
        lines.append(f"**Type:** {s.refactoring_type.value}")
        lines.append(f"**Priority:** {s.priority.value}")
        lines.append(f"**Confidence:** {s.confidence_score:.2f}\n")
        lines.append(s.description)
        lines.append("")
    return "\n".join(lines)


def _format_suggestions_text(suggestions: list[RefactoringSuggestionModel]) -> str:
    lines = ["REFACTORING SUGGESTIONS", "=" * 50, ""]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s.title}")
        lines.append(f"ID: {s.suggestion_id}")
        lines.append(f"Type: {s.refactoring_type.value} | Priority: {s.priority.value}")
    return "\n".join(lines)
