"""
Analysis Operations Tools

This module contains analysis tools for Memory Bank.

Total: 1 tool
- analyze: Usage patterns/structure/insights analysis
"""

import json
from pathlib import Path

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp


async def get_managers(root: Path) -> ManagersDict:
    """Runtime indirection for test patching.

    Some tests patch `cortex.tools.file_operations.get_managers`, others patch
    `cortex.tools.analysis_operations.get_managers`. This wrapper lets both work.
    """
    from cortex.tools import file_operations

    return await file_operations.get_managers(root)


def get_project_root(project_root: str | None) -> Path:
    """Runtime indirection for test patching (see `get_managers`)."""
    from cortex.tools import file_operations

    return file_operations.get_project_root(project_root)


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
        "organization": organization.model_dump(mode="json"),
        "anti_patterns": [p.model_dump(mode="json") for p in anti_patterns],
        "complexity_metrics": complexity.model_dump(mode="json"),
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
        exported = await insight_engine.export_insights(insights, format="markdown")
    elif export_format == "text":
        exported = await insight_engine.export_insights(insights, format="text")
    else:
        exported = insights.model_dump(mode="json")

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
    mgrs: ManagersDict,
) -> tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]:
    """Unwrap and return analysis managers."""
    pattern_analyzer = await get_manager(mgrs, "pattern_analyzer", PatternAnalyzer)
    structure_analyzer = await get_manager(
        mgrs, "structure_analyzer", StructureAnalyzer
    )
    insight_engine = await get_manager(mgrs, "insight_engine", InsightEngine)
    return pattern_analyzer, structure_analyzer, insight_engine


@mcp.tool()
async def analyze(
    target: str,
    project_root: str | None = None,
    time_window_days: int | None = None,
    export_format: str = "json",
    categories: list[str] | None = None,
) -> str:
    """Analyze Memory Bank usage patterns, file structure, and generate
    optimization insights.

    This consolidated tool provides three types of analysis to help
    understand and optimize your Memory Bank:

    1. **usage_patterns**: Analyzes file access frequency, co-access
       patterns, task patterns, and identifies unused files within a time
       window. Helps identify frequently accessed files, files that are
       always accessed together, and files that haven't been used recently.

    2. **structure**: Analyzes file organization, detects anti-patterns
       (deeply nested directories, oversized files, naming inconsistencies),
       and measures complexity metrics (directory depth, file count per
       directory, dependency complexity).

    3. **insights**: Generates AI-driven optimization insights with impact
       scoring. Analyzes patterns and structure to suggest specific
       improvements like consolidating related files, splitting large files,
       or reorganizing directory structure.

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
                        "description": (
                            "productContext.md and activeContext.md share "
                            "85% similar content"
                        ),
                        "impact_score": 0.92,
                        "recommendation": (
                            "Consolidate shared content using transclusion"
                        ),
                        "affected_files": ["productContext.md", "activeContext.md"]
                    }
                ],
                "medium_impact": [
                    {
                        "category": "complexity",
                        "description": (
                            "systemPatterns.md exceeds recommended size "
                            "(12000 tokens)"
                        ),
                        "impact_score": 0.68,
                        "recommendation": (
                            "Split into architecture.md and patterns.md"
                        ),
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
                            "recommendation": (
                                "Split into architecture.md and "
                                "design-patterns.md"
                            )
                        },
                        {
                            "type": "naming_inconsistency",
                            "path": "product_context.md",
                            "severity": "low",
                            "recommendation": (
                                "Rename to productContext.md for consistency"
                            )
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
                "insights": (
                    "# Memory Bank Optimization Insights\n\n"
                    "## High Impact Improvements\n\n"
                    "### Duplication: Consolidate Shared Content\n\n"
                    "**Impact Score:** 0.89\n\n"
                    "**Description:** activeContext.md and progress.md "
                    "contain 78% duplicate content regarding current sprint "
                    "goals and completed tasks.\n\n"
                    "**Recommendation:** Use transclusion to include shared "
                    "sprint information from a single source file.\n\n"
                    "**Affected Files:**\n"
                    "- activeContext.md\n"
                    "- progress.md\n\n"
                    "---\n\n"
                    "## Medium Impact Improvements\n\n"
                    "### Complexity: Split Large File\n\n"
                    "**Impact Score:** 0.65\n\n"
                    "**Description:** systemPatterns.md contains 11200 tokens "
                    "across multiple distinct topics.\n\n"
                    "**Recommendation:** Split into separate files: "
                    "architecture.md, design-patterns.md, and "
                    "coding-standards.md.\n\n"
                    "**Affected Files:**\n"
                    "- systemPatterns.md\n\n"
                )
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
