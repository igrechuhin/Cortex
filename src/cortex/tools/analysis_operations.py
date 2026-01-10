"""
Analysis Operations Tools

This module contains consolidated analysis and refactoring suggestion tools for Memory Bank.

Total: 2 tools
- analyze: Usage patterns/structure/insights analysis
- suggest_refactoring: Consolidation/split/reorganization suggestions
"""

import json
from collections.abc import Sequence
from typing import Literal, cast

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.lazy_manager import LazyManager
from cortex.refactoring.consolidation_detector import (
    ConsolidationDetector,
    ConsolidationOpportunity,
)
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import (
    SplitRecommendation,
    SplitRecommender,
)
from cortex.server import mcp


async def analyze_usage_patterns(
    pattern_analyzer: PatternAnalyzer, time_window_days: int
) -> str:
    """Analyze usage patterns and return JSON response."""
    access_frequency = await pattern_analyzer.get_access_frequency(
        time_range_days=time_window_days
    )
    co_access = await pattern_analyzer.get_co_access_patterns(
        time_range_days=time_window_days
    )
    task_patterns = await pattern_analyzer.get_task_patterns(
        time_range_days=time_window_days
    )
    unused_files = await pattern_analyzer.get_unused_files(
        time_range_days=time_window_days
    )

    patterns = {
        "access_frequency": access_frequency,
        "co_access_patterns": co_access,
        "task_patterns": task_patterns,
        "unused_files": unused_files,
    }

    return json.dumps(
        {
            "status": "success",
            "target": "usage_patterns",
            "time_window_days": time_window_days,
            "patterns": patterns,
        },
        indent=2,
    )


async def analyze_structure(structure_analyzer: StructureAnalyzer) -> str:
    """Analyze structure and return JSON response."""
    organization = await structure_analyzer.analyze_file_organization()
    anti_patterns = await structure_analyzer.detect_anti_patterns()
    complexity = await structure_analyzer.measure_complexity_metrics()

    analysis = {
        "organization": organization,
        "anti_patterns": anti_patterns,
        "complexity_metrics": complexity,
    }

    return json.dumps(
        {"status": "success", "target": "structure", "analysis": analysis}, indent=2
    )


async def analyze_insights(
    insight_engine: InsightEngine, export_format: str, categories: list[str] | None
) -> str:
    """Analyze insights and return JSON response."""
    insights = await insight_engine.generate_insights(
        min_impact_score=0.5, categories=categories
    )

    # Export in requested format
    if export_format == "markdown":
        exported = await insight_engine.export_insights(
            cast(dict[str, object], insights), format="markdown"
        )
    elif export_format == "text":
        exported = await insight_engine.export_insights(
            cast(dict[str, object], insights), format="text"
        )
    else:
        exported = cast(dict[str, object], insights)

    return json.dumps(
        {
            "status": "success",
            "target": "insights",
            "format": export_format,
            "insights": exported,
        },
        indent=2,
    )


async def get_analysis_managers(
    mgrs: dict[str, object],
) -> tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]:
    """Unwrap and return analysis managers."""
    pattern_analyzer_mgr = cast(LazyManager[PatternAnalyzer], mgrs["pattern_analyzer"])
    structure_analyzer_mgr = cast(
        LazyManager[StructureAnalyzer], mgrs["structure_analyzer"]
    )
    insight_engine_mgr = cast(LazyManager[InsightEngine], mgrs["insight_engine"])

    pattern_analyzer = await pattern_analyzer_mgr.get()
    structure_analyzer = await structure_analyzer_mgr.get()
    insight_engine = await insight_engine_mgr.get()

    return pattern_analyzer, structure_analyzer, insight_engine


@mcp.tool()
async def analyze(
    target: Literal["usage_patterns", "structure", "insights"],
    project_root: str | None = None,
    time_window_days: int | None = None,
    export_format: str = "json",
    categories: list[str] | None = None,
) -> str:
    """Analyze Memory Bank usage patterns, file structure, and generate optimization insights.

    This consolidated tool provides three types of analysis to help understand and optimize
    your Memory Bank:

    1. **usage_patterns**: Analyzes file access frequency, co-access patterns, task patterns,
       and identifies unused files within a time window. Helps identify frequently accessed
       files, files that are always accessed together, and files that haven't been used recently.

    2. **structure**: Analyzes file organization, detects anti-patterns (deeply nested directories,
       oversized files, naming inconsistencies), and measures complexity metrics (directory depth,
       file count per directory, dependency complexity).

    3. **insights**: Generates AI-driven optimization insights with impact scoring. Analyzes patterns
       and structure to suggest specific improvements like consolidating related files, splitting
       large files, or reorganizing directory structure.

    Args:
        target: Analysis target to perform.
            - "usage_patterns": Analyze file access and usage patterns
            - "structure": Analyze file organization and detect issues
            - "insights": Generate actionable optimization recommendations

        project_root: Absolute path to project root directory.
            Example: "/Users/username/projects/my-project"
            If None, uses current working directory.

        time_window_days: Number of days to analyze for usage_patterns.
            Example: 30 (analyzes last 30 days)
            Default: 30
            Only applies to target="usage_patterns".

        export_format: Output format for insights.
            - "json": Structured JSON data (default)
            - "markdown": Human-readable Markdown format
            - "text": Plain text format
            Only applies to target="insights".

        categories: Specific insight categories to analyze.
            Example: ["duplication", "complexity", "organization"]
            If None, analyzes all categories.
            Only applies to target="insights".

    Returns:
        JSON string containing analysis results with the following structure:

        For target="usage_patterns":
        {
            "status": "success",
            "target": "usage_patterns",
            "time_window_days": 30,
            "patterns": {
                "access_frequency": {
                    "path/to/file.md": 45,
                    "path/to/other.md": 23
                },
                "co_access_patterns": [
                    {
                        "files": ["file1.md", "file2.md"],
                        "co_access_count": 12,
                        "confidence": 0.85
                    }
                ],
                "task_patterns": {
                    "refactoring": ["systemPatterns.md", "techContext.md"],
                    "feature_development": ["activeContext.md", "progress.md"]
                },
                "unused_files": ["old_file.md", "deprecated.md"]
            }
        }

        For target="structure":
        {
            "status": "success",
            "target": "structure",
            "analysis": {
                "organization": {
                    "total_files": 12,
                    "total_directories": 3,
                    "max_depth": 2,
                    "avg_files_per_directory": 4.0
                },
                "anti_patterns": [
                    {
                        "type": "deeply_nested",
                        "path": "a/b/c/d/e/file.md",
                        "severity": "high",
                        "recommendation": "Move file closer to root"
                    },
                    {
                        "type": "oversized_file",
                        "path": "large_file.md",
                        "size_tokens": 15000,
                        "severity": "medium",
                        "recommendation": "Split into smaller files"
                    }
                ],
                "complexity_metrics": {
                    "avg_directory_depth": 1.8,
                    "max_dependencies": 5,
                    "circular_dependencies": []
                }
            }
        }

        For target="insights":
        {
            "status": "success",
            "target": "insights",
            "format": "json",
            "insights": {
                "high_impact": [
                    {
                        "category": "duplication",
                        "description": "productContext.md and activeContext.md share 85% similar content",
                        "impact_score": 0.92,
                        "recommendation": "Consolidate shared content using transclusion",
                        "affected_files": ["productContext.md", "activeContext.md"]
                    }
                ],
                "medium_impact": [
                    {
                        "category": "complexity",
                        "description": "systemPatterns.md exceeds recommended size (12000 tokens)",
                        "impact_score": 0.68,
                        "recommendation": "Split into architecture.md and patterns.md",
                        "affected_files": ["systemPatterns.md"]
                    }
                ],
                "low_impact": []
            }
        }

        On error:
        {
            "status": "error",
            "error": "Error message",
            "error_type": "ExceptionClassName"
        }

    Examples:
        Example 1: Analyze file access patterns over the last 60 days

        Input:
            target="usage_patterns"
            time_window_days=60

        Output:
            {
                "status": "success",
                "target": "usage_patterns",
                "time_window_days": 60,
                "patterns": {
                    "access_frequency": {
                        "projectBrief.md": 124,
                        "activeContext.md": 98,
                        "systemPatterns.md": 67,
                        "techContext.md": 45,
                        "productContext.md": 23,
                        "progress.md": 12
                    },
                    "co_access_patterns": [
                        {
                            "files": ["activeContext.md", "progress.md"],
                            "co_access_count": 34,
                            "confidence": 0.92
                        },
                        {
                            "files": ["systemPatterns.md", "techContext.md"],
                            "co_access_count": 28,
                            "confidence": 0.87
                        }
                    ],
                    "task_patterns": {
                        "feature_planning": ["productContext.md", "activeContext.md"],
                        "architecture_review": ["systemPatterns.md", "techContext.md"],
                        "progress_tracking": ["progress.md", "activeContext.md"]
                    },
                    "unused_files": ["old_design.md", "deprecated_api.md"]
                }
            }

        Example 2: Analyze project structure for issues

        Input:
            target="structure"

        Output:
            {
                "status": "success",
                "target": "structure",
                "analysis": {
                    "organization": {
                        "total_files": 8,
                        "total_directories": 2,
                        "max_depth": 1,
                        "avg_files_per_directory": 4.0
                    },
                    "anti_patterns": [
                        {
                            "type": "oversized_file",
                            "path": "systemPatterns.md",
                            "size_tokens": 14500,
                            "severity": "high",
                            "recommendation": "Split into architecture.md and design-patterns.md"
                        },
                        {
                            "type": "naming_inconsistency",
                            "path": "product_context.md",
                            "severity": "low",
                            "recommendation": "Rename to productContext.md for consistency"
                        }
                    ],
                    "complexity_metrics": {
                        "avg_directory_depth": 1.2,
                        "max_dependencies": 4,
                        "circular_dependencies": []
                    }
                }
            }

        Example 3: Generate optimization insights in markdown format

        Input:
            target="insights"
            export_format="markdown"
            categories=["duplication", "complexity"]

        Output:
            {
                "status": "success",
                "target": "insights",
                "format": "markdown",
                "insights": "# Memory Bank Optimization Insights\n\n## High Impact Improvements\n\n### Duplication: Consolidate Shared Content\n\n**Impact Score:** 0.89\n\n**Description:** activeContext.md and progress.md contain 78% duplicate content regarding current sprint goals and completed tasks.\n\n**Recommendation:** Use transclusion to include shared sprint information from a single source file.\n\n**Affected Files:**\n- activeContext.md\n- progress.md\n\n---\n\n## Medium Impact Improvements\n\n### Complexity: Split Large File\n\n**Impact Score:** 0.65\n\n**Description:** systemPatterns.md contains 11200 tokens across multiple distinct topics.\n\n**Recommendation:** Split into separate files: architecture.md, design-patterns.md, and coding-standards.md.\n\n**Affected Files:**\n- systemPatterns.md\n\n"
            }

    Note:
        - Usage patterns analysis requires file access history. If no history exists,
          access_frequency and co_access_patterns will be empty.
        - Structure analysis always runs on the current state of the Memory Bank.
        - Insights generation may take longer as it performs comprehensive analysis
          and uses pattern matching algorithms.
        - The time_window_days parameter only affects usage_patterns analysis. For
          structure and insights, this parameter is ignored.
        - Insight categories include: "duplication", "complexity", "organization",
          "dependencies", "naming", "size". If categories is None, all are analyzed.
        - Export formats for insights: "json" provides structured data, "markdown"
          provides formatted documentation, "text" provides plain text summary.
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        analyzers = await get_analysis_managers(mgrs)

        return await dispatch_analysis_target(
            target, analyzers, time_window_days, export_format, categories
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def dispatch_analysis_target(
    target: str,
    analyzers: tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine],
    time_window_days: int | None,
    export_format: str,
    categories: list[str] | None,
) -> str:
    """Dispatch analysis to appropriate handler based on target."""
    pattern_analyzer, structure_analyzer, insight_engine = analyzers

    if target == "usage_patterns":
        window = time_window_days or 30
        return await analyze_usage_patterns(pattern_analyzer, window)
    elif target == "structure":
        return await analyze_structure(structure_analyzer)
    elif target == "insights":
        return await analyze_insights(insight_engine, export_format, categories)
    else:
        return json.dumps(
            {
                "status": "error",
                "error": f"Invalid target: {target}",
                "valid_targets": ["usage_patterns", "structure", "insights"],
            },
            indent=2,
        )


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
    mgrs: dict[str, object],
) -> tuple[ConsolidationDetector, SplitRecommender, ReorganizationPlanner]:
    """Unwrap and return refactoring managers."""
    consolidation_detector_mgr = cast(
        LazyManager[ConsolidationDetector], mgrs["consolidation_detector"]
    )
    split_recommender_mgr = cast(
        LazyManager[SplitRecommender], mgrs["split_recommender"]
    )
    reorganization_planner_mgr = cast(
        LazyManager[ReorganizationPlanner], mgrs["reorganization_planner"]
    )

    consolidation_detector = await consolidation_detector_mgr.get()
    split_recommender = await split_recommender_mgr.get()
    reorganization_planner = await reorganization_planner_mgr.get()

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
    opportunities: Sequence[ConsolidationOpportunity | dict[str, object]],
) -> list[dict[str, object]]:
    """Convert opportunities to dictionaries.

    Args:
        opportunities: Sequence of opportunity objects or dictionaries

    Returns:
        List of opportunity dictionaries
    """
    opportunities_dict: list[dict[str, object]] = []
    for opp in opportunities:
        if isinstance(opp, dict):
            opportunities_dict.append(opp)
        elif hasattr(opp, "to_dict"):
            opportunities_dict.append(opp.to_dict())
        else:
            opportunities_dict.append(cast(dict[str, object], opp))
    return opportunities_dict


async def suggest_consolidation(
    consolidation_detector: ConsolidationDetector,
    min_similarity: float | None,
) -> str:
    """Generate consolidation suggestions."""
    similarity = min_similarity or 0.80
    consolidation_detector.min_similarity = similarity
    opportunities = await consolidation_detector.detect_opportunities()

    # Convert opportunities to dictionaries (handles both objects and dicts)
    opportunities_dict = convert_opportunities_to_dict(opportunities)

    return json.dumps(
        {
            "status": "success",
            "type": "consolidation",
            "min_similarity": similarity,
            "opportunities": opportunities_dict,
        },
        indent=2,
    )


def convert_recommendations_to_dict(
    recommendations: Sequence[SplitRecommendation | dict[str, object]],
) -> list[dict[str, object]]:
    """Convert recommendations to dictionaries.

    Args:
        recommendations: Sequence of recommendation objects or dictionaries

    Returns:
        List of recommendation dictionaries
    """
    recommendations_dict: list[dict[str, object]] = []
    for rec in recommendations:
        if isinstance(rec, dict):
            recommendations_dict.append(rec)
        elif hasattr(rec, "to_dict"):
            recommendations_dict.append(rec.to_dict())
        else:
            recommendations_dict.append(cast(dict[str, object], rec))
    return recommendations_dict


async def suggest_splits(
    split_recommender: SplitRecommender,
    size_threshold: int | None,
) -> str:
    """Generate file split recommendations."""
    threshold = size_threshold or 10000  # 10KB default
    split_recommender.max_file_size = threshold // 4  # 1 token ≈ 4 chars
    recommendations = await split_recommender.suggest_file_splits()

    recommendations_dict = convert_recommendations_to_dict(recommendations)

    return json.dumps(
        {
            "status": "success",
            "type": "splits",
            "size_threshold": threshold,
            "recommendations": recommendations_dict,
        },
        indent=2,
    )


async def get_structure_data(
    mgrs: dict[str, object],
) -> dict[str, object]:
    """Get structure analysis data."""
    structure_analyzer_mgr = cast(
        LazyManager[StructureAnalyzer], mgrs["structure_analyzer"]
    )
    structure_analyzer = await structure_analyzer_mgr.get()
    organization = await structure_analyzer.analyze_file_organization()
    anti_patterns = await structure_analyzer.detect_anti_patterns()
    complexity = await structure_analyzer.measure_complexity_metrics()

    return {
        "organization": organization,
        "anti_patterns": anti_patterns,
        "complexity_metrics": complexity,
    }


async def suggest_reorganization(
    reorganization_planner: ReorganizationPlanner,
    mgrs: dict[str, object],
    goal: str | None,
) -> str:
    """Generate reorganization plan."""
    reorg_goal = goal or "dependency_depth"
    structure_data = await get_structure_data(mgrs)
    dependency_graph = cast(DependencyGraph, mgrs["graph"])
    graph_data = dependency_graph.to_dict()

    # Cast to satisfy type checker
    structure_data_typed: dict[str, object] = {k: v for k, v in structure_data.items()}
    graph_data_typed: dict[str, object] = {k: v for k, v in graph_data.items()}

    plan = await reorganization_planner.create_reorganization_plan(
        optimize_for=reorg_goal,
        structure_data=structure_data_typed,
        dependency_graph=graph_data_typed,
    )

    return json.dumps(
        {
            "status": "success",
            "type": "reorganization",
            "goal": reorg_goal,
            "plan": plan,
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
