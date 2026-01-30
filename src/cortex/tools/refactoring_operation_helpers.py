"""Helper functions for refactoring operations.

Extracted to keep refactoring_operations.py under 400 lines.
"""

import json
from collections.abc import Sequence
from typing import cast

from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.models import ModelDict
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.refactoring.consolidation_detector import (
    ConsolidationDetector,
    ConsolidationOpportunity,
)
from cortex.refactoring.models import RefactoringSuggestionType
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import SplitRecommendation, SplitRecommender


def parse_refactoring_suggestion_type(
    value: str | None,
) -> RefactoringSuggestionType | None:
    """Parse string to RefactoringSuggestionType. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return RefactoringSuggestionType(value)
    except ValueError:
        return None


def validate_refactoring_type(type_val: str) -> str | None:
    """Validate refactoring type parameter. Returns JSON error string or None."""
    if parse_refactoring_suggestion_type(type_val) is None:
        return json.dumps(
            {
                "status": "error",
                "error": (
                    f"Invalid type: {type_val}. Valid types: consolidation, "
                    "splits, reorganization"
                ),
                "valid_types": [t.value for t in RefactoringSuggestionType],
            },
            indent=2,
        )
    return None


async def get_refactoring_managers(
    mgrs: ManagersDict,
) -> tuple[ConsolidationDetector, SplitRecommender, ReorganizationPlanner]:
    """Unwrap and return refactoring managers."""
    consolidation_detector = await get_manager(
        mgrs, "consolidation_detector", ConsolidationDetector
    )
    split_recommender = await get_manager(mgrs, "split_recommender", SplitRecommender)
    reorganization_planner = await get_manager(
        mgrs, "reorganization_planner", ReorganizationPlanner
    )
    return consolidation_detector, split_recommender, reorganization_planner


def handle_preview_mode(preview_suggestion_id: str) -> str:
    """Handle preview mode for refactoring suggestions."""
    return json.dumps(
        {
            "status": "success",
            "preview_mode": True,
            "suggestion_id": preview_suggestion_id,
            "message": "Preview functionality requires suggestion caching",
            "note": "Call suggest_refactoring first to generate suggestions",
        },
        indent=2,
    )


def convert_opportunities_to_dict(
    opportunities: Sequence[ConsolidationOpportunity],
) -> list[ModelDict]:
    """Convert consolidation opportunities to serializable dicts.

    Args:
        opportunities: Sequence of opportunity dataclasses

    Returns:
        List of dicts
    """
    items: list[ModelDict] = []
    for opp in opportunities:
        if hasattr(opp, "to_dict"):
            items.append(opp.to_dict())
        else:
            items.append(cast(ModelDict, opp.__dict__))
    return items


def convert_recommendations_to_dict(
    recommendations: Sequence[SplitRecommendation],
) -> list[ModelDict]:
    """Convert split recommendations to serializable dicts.

    Args:
        recommendations: Sequence of recommendation dataclasses

    Returns:
        List of dicts
    """
    items: list[ModelDict] = []
    for rec in recommendations:
        if hasattr(rec, "to_dict"):
            items.append(rec.to_dict())
        else:
            items.append(cast(ModelDict, rec.__dict__))
    return items


def validate_suggest_refactoring_type(type_val: str) -> str | None:
    """Validate type for suggest_refactoring. Returns error JSON or None."""
    if parse_refactoring_suggestion_type(type_val) is None:
        err = validate_refactoring_type(type_val)
        return (
            err
            if err
            else json.dumps({"status": "error", "error": "type is required"}, indent=2)
        )
    return None


async def get_structure_data(mgrs: ManagersDict) -> ModelDict:
    """Get structure analysis data."""
    structure_analyzer = await get_manager(
        mgrs, "structure_analyzer", StructureAnalyzer
    )
    organization = await structure_analyzer.analyze_file_organization()
    anti_patterns = await structure_analyzer.detect_anti_patterns()
    complexity = await structure_analyzer.measure_complexity_metrics()

    analysis: ModelDict = {
        "file_organization": organization.model_dump(mode="json"),
        "anti_patterns": [p.model_dump(mode="json") for p in anti_patterns],
        "complexity_metrics": complexity.model_dump(mode="json"),
    }

    total_files = int(getattr(organization, "file_count", 0))
    return {
        "total_files": total_files,
        "files": [],
        "organization": "flat",
        "categories": {},
        "dependency_depth": 0,
        "dependency_order": [],
        "hub_files": [],
        "orphaned_files": [],
        "complexity_score": 0.0,
        "analysis": analysis,
    }
