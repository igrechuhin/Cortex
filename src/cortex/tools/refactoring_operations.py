"""
Refactoring Operations Tools

This module contains refactoring suggestion tools for Memory Bank.

Total: 1 tool
- suggest_refactoring: Consolidation/split/reorganization suggestions
"""

import json
from collections.abc import Sequence
from typing import Literal, cast

from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.models import ModelDict
from cortex.core.protocols.token import DependencyGraphProtocol
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.refactoring.consolidation_detector import (
    ConsolidationDetector,
    ConsolidationOpportunity,
)
from cortex.refactoring.models import DependencyGraphInput, MemoryBankStructureData
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import SplitRecommendation, SplitRecommender
from cortex.server import mcp


def validate_refactoring_type(type: str) -> str | None:
    """Validate refactoring type parameter."""
    valid_types = ["consolidation", "splits", "reorganization"]
    if type not in valid_types:
        return json.dumps(
            {
                "status": "error",
                "error": f"Invalid type: {type}. Valid types: consolidation, splits, reorganization",
                "valid_types": valid_types,
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


async def suggest_consolidation(
    consolidation_detector: ConsolidationDetector,
    min_similarity: float | None,
) -> str:
    """Generate consolidation suggestions."""
    similarity = min_similarity or 0.80
    consolidation_detector.min_similarity = similarity
    opportunities = await consolidation_detector.detect_opportunities()

    opportunities_list = convert_opportunities_to_dict(opportunities)

    return json.dumps(
        {
            "status": "success",
            "type": "consolidation",
            "min_similarity": similarity,
            "opportunities": opportunities_list,
        },
        indent=2,
    )


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


async def suggest_splits(
    split_recommender: SplitRecommender,
    size_threshold: int | None,
) -> str:
    """Generate file split recommendations."""
    threshold = size_threshold or 10000  # 10KB default
    split_recommender.max_file_size = threshold // 4  # 1 token ≈ 4 chars
    recommendations = await split_recommender.suggest_file_splits()

    recommendations_list = convert_recommendations_to_dict(recommendations)

    return json.dumps(
        {
            "status": "success",
            "type": "splits",
            "recommendations": recommendations_list,
            "size_threshold": threshold,
        },
        indent=2,
    )


async def get_structure_data(
    mgrs: ManagersDict,
) -> ModelDict:
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


async def suggest_reorganization(
    reorganization_planner: ReorganizationPlanner,
    mgrs: ManagersDict,
    goal: str | None,
) -> str:
    """Generate reorganization plan."""
    reorg_goal = goal or "dependency_depth"
    structure_data = await get_structure_data(mgrs)
    dependency_graph_instance = cast(DependencyGraphProtocol, mgrs.graph)
    graph_data = dependency_graph_instance.to_dict()

    structure_model = MemoryBankStructureData.model_validate(structure_data)
    graph_model = DependencyGraphInput.model_validate(
        graph_data.model_dump(mode="json")
    )

    plan = await reorganization_planner.create_reorganization_plan(
        optimize_for=reorg_goal,
        structure_data=structure_model,
        dependency_graph=graph_model,
    )

    return json.dumps(
        {
            "status": "success",
            "type": "reorganization",
            "goal": reorg_goal,
            "plan": plan.model_dump(mode="json") if plan else None,
        },
        indent=2,
    )


async def process_refactoring_request(
    type: str,
    project_root: str | None,
    min_similarity: float | None,
    size_threshold: int | None,
    goal: str | None,
    preview_suggestion_id: str | None,
) -> str:
    """Process refactoring suggestion request."""
    # Get managers
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    (
        consolidation_detector,
        split_recommender,
        reorganization_planner,
    ) = await get_refactoring_managers(mgrs)

    # Handle preview mode
    if preview_suggestion_id:
        return handle_preview_mode(preview_suggestion_id)

    # Generate suggestions based on type
    if type == "consolidation":
        return await suggest_consolidation(consolidation_detector, min_similarity)
    elif type == "splits":
        return await suggest_splits(split_recommender, size_threshold)
    elif type == "reorganization":
        return await suggest_reorganization(reorganization_planner, mgrs, goal)

    return json.dumps({"status": "error", "error": "Unknown error"}, indent=2)


@mcp.tool()
async def suggest_refactoring(
    type: Literal["consolidation", "splits", "reorganization"],
    project_root: str | None = None,
    min_similarity: float | None = None,
    size_threshold: int | None = None,
    goal: str | None = None,
    preview_suggestion_id: str | None = None,
    show_diff: bool = True,
    estimate_impact: bool = True,
) -> str:
    """Generate intelligent refactoring suggestions to improve Memory Bank structure and efficiency.

    This consolidated tool provides three types of refactoring suggestions to help optimize
    your Memory Bank:

    1. **consolidation**: Identifies opportunities to consolidate duplicate or highly similar
       content across multiple files. Uses similarity analysis to find files sharing common
       content that could be extracted into shared files and referenced via transclusion.

    2. **splits**: Identifies oversized files that should be split into smaller, more focused
       files. Analyzes file size in tokens and suggests logical split points based on content
       structure (headings, sections, topics).

    3. **reorganization**: Generates comprehensive reorganization plans to improve overall
       structure. Can optimize for reducing dependency depth, grouping by category/functionality,
       or reducing complexity.

    Args:
        type: Type of refactoring suggestions to generate.
            - "consolidation": Find duplicate content to consolidate
            - "splits": Find large files to split
            - "reorganization": Generate structure reorganization plan

        project_root: Absolute path to project root directory.
            Example: "/Users/username/projects/my-project"
            If None, uses current working directory.

        min_similarity: Minimum similarity threshold for consolidation suggestions (0.0-1.0).
            Example: 0.75 (75% similarity required)
            Default: 0.80 (80% similarity)
            Higher values = stricter matching, fewer suggestions.
            Lower values = more lenient matching, more suggestions.
            Only applies to type="consolidation".

        size_threshold: Maximum file size in bytes before suggesting split.
            Example: 8000 (suggest split for files over 8KB)
            Default: 10000 (10KB, approximately 2500 tokens)
            Only applies to type="splits".

        goal: Optimization goal for reorganization.
            - "dependency_depth": Minimize dependency chain depth (default)
            - "category": Group files by functionality/category
            - "complexity": Reduce overall structural complexity
            Only applies to type="reorganization".

        preview_suggestion_id: ID of a specific suggestion to preview.
            Example: "consolidation_001"
            If provided, returns detailed preview instead of generating suggestions.
            Currently requires suggestion caching (future feature).

        show_diff: Whether to include file diff in preview.
            Default: True
            Only applies when preview_suggestion_id is provided.

        estimate_impact: Whether to estimate impact metrics in preview.
            Default: True
            Only applies when preview_suggestion_id is provided.

    Returns:
        JSON string containing refactoring suggestions with the following structure:

        For type="consolidation":
        {
            "status": "success",
            "type": "consolidation",
            "min_similarity": 0.80,
            "opportunities": [
                {
                    "id": "consolidation_001",
                    "files": ["productContext.md", "activeContext.md"],
                    "similarity": 0.87,
                    "shared_content_tokens": 450,
                    "potential_savings_tokens": 420,
                    "recommendation": "Extract shared product requirements into product-requirements.md",
                    "suggested_transclusion": "{{include:product-requirements.md}}",
                    "confidence": "high"
                }
            ]
        }

        For type="splits":
        {
            "status": "success",
            "type": "splits",
            "size_threshold": 10000,
            "recommendations": [
                {
                    "id": "split_001",
                    "file": "systemPatterns.md",
                    "current_size_tokens": 12500,
                    "current_size_bytes": 50000,
                    "reason": "File exceeds recommended size for context loading",
                    "suggested_splits": [
                        {
                            "name": "architecture.md",
                            "sections": ["System Architecture", "Component Design"],
                            "estimated_tokens": 6000
                        },
                        {
                            "name": "design-patterns.md",
                            "sections": ["Design Patterns", "Code Conventions"],
                            "estimated_tokens": 6500
                        }
                    ],
                    "confidence": "high",
                    "impact": {
                        "improved_context_loading": true,
                        "reduced_cognitive_load": true,
                        "better_organization": true
                    }
                }
            ]
        }

        For type="reorganization":
        {
            "status": "success",
            "type": "reorganization",
            "goal": "dependency_depth",
            "plan": {
                "current_state": {
                    "max_depth": 4,
                    "total_files": 12,
                    "total_directories": 5
                },
                "proposed_state": {
                    "max_depth": 2,
                    "total_files": 12,
                    "total_directories": 3
                },
                "moves": [
                    {
                        "from": "context/product/requirements.md",
                        "to": "product-requirements.md",
                        "reason": "Reduce nesting, frequently accessed file"
                    },
                    {
                        "from": "architecture/system/core.md",
                        "to": "system-architecture.md",
                        "reason": "Flatten deeply nested structure"
                    }
                ],
                "new_structure": {
                    "root": [
                        "projectBrief.md",
                        "productContext.md",
                        "activeContext.md"
                    ],
                    "architecture": [
                        "systemPatterns.md",
                        "techContext.md"
                    ],
                    "tracking": [
                        "progress.md",
                        "roadmap.md"
                    ]
                },
                "estimated_improvement": {
                    "dependency_depth_reduction": "50%",
                    "access_time_improvement": "30%",
                    "cognitive_load_reduction": "high"
                }
            }
        }

        For preview_suggestion_id (future feature):
        {
            "status": "success",
            "preview_mode": true,
            "suggestion_id": "consolidation_001",
            "message": "Preview functionality requires suggestion caching",
            "note": "Call suggest_refactoring first to generate suggestions"
        }

        On error:
        {
            "status": "error",
            "error": "Error message",
            "error_type": "ExceptionClassName"
        }

    Examples:
        Example 1: Find consolidation opportunities with high similarity threshold

        Input:
            type="consolidation"
            min_similarity=0.85

        Output:
            {
                "status": "success",
                "type": "consolidation",
                "min_similarity": 0.85,
                "opportunities": [
                    {
                        "id": "consolidation_001",
                        "files": ["systemPatterns.md", "techContext.md"],
                        "similarity": 0.89,
                        "shared_content_tokens": 780,
                        "potential_savings_tokens": 730,
                        "recommendation": "Extract shared technology stack information into tech-stack.md",
                        "suggested_transclusion": "{{include:tech-stack.md}}",
                        "confidence": "high"
                    },
                    {
                        "id": "consolidation_002",
                        "files": ["activeContext.md", "progress.md"],
                        "similarity": 0.87,
                        "shared_content_tokens": 520,
                        "potential_savings_tokens": 485,
                        "recommendation": "Extract current sprint goals into sprint-current.md",
                        "suggested_transclusion": "{{include:sprint-current.md}}",
                        "confidence": "high"
                    }
                ]
            }

        Example 2: Find files that should be split (smaller threshold for more suggestions)

        Input:
            type="splits"
            size_threshold=8000

        Output:
            {
                "status": "success",
                "type": "splits",
                "size_threshold": 8000,
                "recommendations": [
                    {
                        "id": "split_001",
                        "file": "systemPatterns.md",
                        "current_size_tokens": 11200,
                        "current_size_bytes": 44800,
                        "reason": "File exceeds size threshold and contains multiple distinct topics",
                        "suggested_splits": [
                            {
                                "name": "architecture-overview.md",
                                "sections": ["System Architecture", "High-Level Design"],
                                "estimated_tokens": 4500
                            },
                            {
                                "name": "design-patterns.md",
                                "sections": ["Design Patterns", "Pattern Implementations"],
                                "estimated_tokens": 3800
                            },
                            {
                                "name": "coding-standards.md",
                                "sections": ["Coding Standards", "Best Practices", "Code Review Guidelines"],
                                "estimated_tokens": 2900
                            }
                        ],
                        "confidence": "high",
                        "impact": {
                            "improved_context_loading": true,
                            "reduced_cognitive_load": true,
                            "better_organization": true
                        }
                    },
                    {
                        "id": "split_002",
                        "file": "productContext.md",
                        "current_size_tokens": 9100,
                        "current_size_bytes": 36400,
                        "reason": "File size approaching threshold with separable content sections",
                        "suggested_splits": [
                            {
                                "name": "product-vision.md",
                                "sections": ["Vision", "Goals", "Target Users"],
                                "estimated_tokens": 4200
                            },
                            {
                                "name": "product-requirements.md",
                                "sections": ["Requirements", "Features", "User Stories"],
                                "estimated_tokens": 4900
                            }
                        ],
                        "confidence": "medium",
                        "impact": {
                            "improved_context_loading": true,
                            "reduced_cognitive_load": false,
                            "better_organization": true
                        }
                    }
                ]
            }

        Example 3: Generate reorganization plan optimized for categories

        Input:
            type="reorganization"
            goal="category"

        Output:
            {
                "status": "success",
                "type": "reorganization",
                "goal": "category",
                "plan": {
                    "current_state": {
                        "max_depth": 3,
                        "total_files": 14,
                        "total_directories": 6
                    },
                    "proposed_state": {
                        "max_depth": 2,
                        "total_files": 14,
                        "total_directories": 4
                    },
                    "moves": [
                        {
                            "from": "docs/product/vision.md",
                            "to": "product/vision.md",
                            "reason": "Group product-related files together"
                        },
                        {
                            "from": "docs/product/requirements.md",
                            "to": "product/requirements.md",
                            "reason": "Group product-related files together"
                        },
                        {
                            "from": "tech/architecture.md",
                            "to": "technical/architecture.md",
                            "reason": "Standardize technical documentation location"
                        }
                    ],
                    "new_structure": {
                        "root": [
                            "projectBrief.md",
                            "activeContext.md"
                        ],
                        "product": [
                            "productContext.md",
                            "vision.md",
                            "requirements.md"
                        ],
                        "technical": [
                            "systemPatterns.md",
                            "techContext.md",
                            "architecture.md"
                        ],
                        "tracking": [
                            "progress.md",
                            "roadmap.md"
                        ]
                    },
                    "estimated_improvement": {
                        "category_cohesion": "85%",
                        "file_discoverability": "high",
                        "logical_grouping": "high"
                    }
                }
            }

    Note:
        - Consolidation analysis uses content similarity algorithms and may take several
          seconds for large Memory Banks. Results are cached per session.
        - Split recommendations consider both file size and logical content boundaries
          (sections, headings). Files just under the threshold may not get suggestions.
        - Reorganization plans preserve all file content and dependencies. The tool only
          suggests moves, it does not execute them automatically.
        - The min_similarity threshold significantly affects results: 0.80-0.90 is typical,
          0.70-0.79 is lenient (more suggestions), 0.91-1.0 is strict (fewer suggestions).
        - Size threshold is in bytes. Typical values: 8000-12000 bytes. Remember that
          1 token ≈ 4 characters, so 10000 bytes ≈ 2500 tokens.
        - Preview functionality (preview_suggestion_id) requires suggestion caching which
          is planned for a future release. Currently returns informational message.
        - All suggestions include confidence scores (high/medium/low) based on analysis
          quality and the certainty of the recommendation.
        - Refactoring suggestions do not modify files. Use execute_refactoring tool
          to apply changes after reviewing suggestions.
    """
    try:
        error_response = validate_refactoring_type(type)
        if error_response:
            return error_response

        return await process_refactoring_request(
            type,
            project_root,
            min_similarity,
            size_threshold,
            goal,
            preview_suggestion_id,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": e.__class__.__name__},
            indent=2,
        )
