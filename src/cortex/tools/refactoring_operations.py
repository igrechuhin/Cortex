"""
Refactoring Operations Tools

This module contains refactoring suggestion tools for Memory Bank.

Total: 1 tool, 1 resource
- suggest_refactoring / suggest_refactoring_resource (cortex://analysis/suggest-refactoring/{type})
"""

from typing import Literal
from urllib.parse import unquote

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.refactoring_operation_helpers import (
    format_suggest_refactoring_response,
    parse_refactoring_suggestion_type,
    process_refactoring_request,
    suggest_refactoring_error_json,
    validate_suggest_refactoring_type,
)
from cortex.tools.tool_categories import ALLOWED_CALLERS_CODE_EXECUTION


async def _suggest_refactoring_impl(
    type_val: str,
    project_root: str | None,
    min_similarity: float | None,
    size_threshold: int | None,
    goal: str | None,
    preview_suggestion_id: str | None,
) -> tuple[str, bool]:
    """Validate and run process_refactoring_request. Returns (json_str, is_validation_error)."""
    err = validate_suggest_refactoring_type(type_val)
    if err is not None:
        return (err, True)
    type_parsed = parse_refactoring_suggestion_type(type_val)
    assert type_parsed is not None
    out = await process_refactoring_request(
        type_parsed,
        project_root,
        min_similarity,
        size_threshold,
        goal,
        preview_suggestion_id,
    )
    return (out, False)


async def _suggest_refactoring_run(
    type_val: str,
    project_root: str | None,
    min_similarity: float | None,
    size_threshold: int | None,
    goal: str | None,
    preview_suggestion_id: str | None,
    response_format: ResponseFormat,
    ctx: MCPContext | None,
) -> str:
    """Run suggest_refactoring with logging. Returns JSON string."""
    try:
        out, is_validation_error = await _suggest_refactoring_impl(
            type_val,
            project_root,
            min_similarity,
            size_threshold,
            goal,
            preview_suggestion_id,
        )
        level, msg = (
            ("warning", "suggest_refactoring: invalid type")
            if is_validation_error
            else ("info", "suggest_refactoring: completed")
        )
        await log_client(ctx, level, msg, logger_name=__name__)
        return format_suggest_refactoring_response(out, response_format)
    except Exception as e:
        await log_client(
            ctx, "error", f"suggest_refactoring: {e!s}", logger_name=__name__
        )
        return suggest_refactoring_error_json(e)


@mcp.tool(
    annotations=read_only_annotations("Suggest Refactoring"),
    meta={"allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION)},
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def suggest_refactoring(
    type: Literal["consolidation", "splits", "reorganization"],
    min_similarity: float | None = None,
    size_threshold: int | None = None,
    goal: str | None = None,
    preview_suggestion_id: str | None = None,
    show_diff: bool = True,
    estimate_impact: bool = True,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    ctx: MCPContext | None = None,
) -> str:
    """Generate intelligent refactoring suggestions to improve Memory Bank
    structure and efficiency.

    USE WHEN: User wants refactoring suggestions, user needs consolidation
    ideas, user requests reorganization suggestions, user wants to improve
    structure.

    EXAMPLES: 'suggest refactoring for consolidation', 'find files to split',
    'suggest reorganization', 'get refactoring opportunities'.

    RETURNS: JSON with refactoring suggestions, similarity scores, and
    recommendations.

    This consolidated tool provides three types of refactoring suggestions to
    help optimize your Memory Bank:

    1. **consolidation**: Identifies opportunities to consolidate duplicate or
       highly similar content across multiple files. Uses similarity analysis
       to find files sharing common content that could be extracted into
       shared files and referenced via transclusion.

    2. **splits**: Identifies oversized files that should be split into
       smaller, more focused files. Analyzes file size in tokens and suggests
       logical split points based on content structure (headings, sections,
       topics).

    3. **reorganization**: Generates comprehensive reorganization plans to
       improve overall structure. Can optimize for reducing dependency depth,
       grouping by category/functionality, or reducing complexity.

    Args:
        type: Type of refactoring suggestions to generate.
            - "consolidation": Find duplicate content to consolidate
            - "splits": Find large files to split
            - "reorganization": Generate structure reorganization plan

        min_similarity: Minimum similarity threshold for consolidation
            suggestions (0.0-1.0).
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
                    "files": [MemoryBankFile.PRODUCT_CONTEXT, MemoryBankFile.ACTIVE_CONTEXT],
                    "similarity": 0.87,
                    "shared_content_tokens": 450,
                    "potential_savings_tokens": 420,
                    "recommendation": (
                        "Extract shared product requirements into "
                        "product-requirements.md"
                    ),
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
                    "file": MemoryBankFile.SYSTEM_PATTERNS,
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
                        MemoryBankFile.PROJECT_BRIEF,
                        MemoryBankFile.PRODUCT_CONTEXT,
                        MemoryBankFile.ACTIVE_CONTEXT
                    ],
                    "architecture": [
                        MemoryBankFile.SYSTEM_PATTERNS,
                        MemoryBankFile.TECH_CONTEXT
                    ],
                    "tracking": [
                        MemoryBankFile.PROGRESS,
                        MemoryBankFile.ROADMAP
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
                        "files": [MemoryBankFile.SYSTEM_PATTERNS, MemoryBankFile.TECH_CONTEXT],
                        "similarity": 0.89,
                        "shared_content_tokens": 780,
                        "potential_savings_tokens": 730,
                        "recommendation": (
                            "Extract shared technology stack information "
                            "into tech-stack.md"
                        ),
                        "suggested_transclusion": "{{include:tech-stack.md}}",
                        "confidence": "high"
                    },
                    {
                        "id": "consolidation_002",
                        "files": [MemoryBankFile.ACTIVE_CONTEXT, MemoryBankFile.PROGRESS],
                        "similarity": 0.87,
                        "shared_content_tokens": 520,
                        "potential_savings_tokens": 485,
                        "recommendation": (
                            "Extract current sprint goals into "
                            "sprint-current.md"
                        ),
                        "suggested_transclusion": "{{include:sprint-current.md}}",
                        "confidence": "high"
                    }
                ]
            }

        Example 2: Find files that should be split (smaller threshold for
            more suggestions)

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
                        "file": MemoryBankFile.SYSTEM_PATTERNS,
                        "current_size_tokens": 11200,
                        "current_size_bytes": 44800,
                        "reason": (
                            "File exceeds size threshold and contains "
                            "multiple distinct topics"
                        ),
                        "suggested_splits": [
                            {
                                "name": "architecture-overview.md",
                                "sections": [
                                    "System Architecture",
                                    "High-Level Design",
                                ],
                                "estimated_tokens": 4500
                            },
                            {
                                "name": "design-patterns.md",
                                "sections": [
                                    "Design Patterns",
                                    "Pattern Implementations",
                                ],
                                "estimated_tokens": 3800
                            },
                            {
                                "name": "coding-standards.md",
                                "sections": [
                                    "Coding Standards",
                                    "Best Practices",
                                    "Code Review Guidelines",
                                ],
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
                        "file": MemoryBankFile.PRODUCT_CONTEXT,
                        "current_size_tokens": 9100,
                        "current_size_bytes": 36400,
                        "reason": (
                            "File size approaching threshold with separable "
                            "content sections"
                        ),
                        "suggested_splits": [
                            {
                                "name": "product-vision.md",
                                "sections": ["Vision", "Goals", "Target Users"],
                                "estimated_tokens": 4200
                            },
                            {
                                "name": "product-requirements.md",
                                "sections": [
                                    "Requirements",
                                    "Features",
                                    "User Stories",
                                ],
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
                            MemoryBankFile.PROJECT_BRIEF,
                            MemoryBankFile.ACTIVE_CONTEXT
                        ],
                        "product": [
                            MemoryBankFile.PRODUCT_CONTEXT,
                            "vision.md",
                            "requirements.md"
                        ],
                        "technical": [
                            MemoryBankFile.SYSTEM_PATTERNS,
                            MemoryBankFile.TECH_CONTEXT,
                            "architecture.md"
                        ],
                        "tracking": [
                            MemoryBankFile.PROGRESS,
                            MemoryBankFile.ROADMAP
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
        - Consolidation analysis uses content similarity algorithms and may
          take several seconds for large Memory Banks. Results are cached per
          session.
        - Split recommendations consider both file size and logical content
          boundaries (sections, headings). Files just under the threshold may
          not get suggestions.
        - Reorganization plans preserve all file content and dependencies.
          The tool only suggests moves, it does not execute them automatically.
        - The min_similarity threshold significantly affects results:
          0.80-0.90 is typical, 0.70-0.79 is lenient (more suggestions),
          0.91-1.0 is strict (fewer suggestions).
        - Size threshold is in bytes. Typical values: 8000-12000 bytes.
          Remember that 1 token ≈ 4 characters, so 10000 bytes ≈ 2500 tokens.
        - Preview functionality (preview_suggestion_id) requires suggestion
          caching which is planned for a future release. Currently returns
          informational message.
        - All suggestions include confidence scores (high/medium/low) based on analysis
          quality and the certainty of the recommendation.
        - Refactoring suggestions do not modify files. Use execute_refactoring tool
          to apply changes after reviewing suggestions.
    """
    await log_client(ctx, "info", "suggest_refactoring: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)
    return await _suggest_refactoring_run(
        type,
        str(root),
        min_similarity,
        size_threshold,
        goal,
        preview_suggestion_id,
        response_format,
        ctx,
    )


@mcp.resource(uri="cortex://analysis/suggest-refactoring/{type}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def suggest_refactoring_resource(type: str) -> str:
    """Resource: Get refactoring suggestions by type. Read via cortex://analysis/suggest-refactoring/{type}.

    type may be URL-encoded. Must be one of: consolidation, splits,
    reorganization. Uses default parameters (min_similarity=None,
    size_threshold=None, goal=None, preview_suggestion_id=None, show_diff=True,
    estimate_impact=True).
    """
    decoded = unquote(type)
    return await suggest_refactoring(
        type=decoded,
        min_similarity=None,
        size_threshold=None,
        goal=None,
        preview_suggestion_id=None,
        show_diff=True,
        estimate_impact=True,
    )
