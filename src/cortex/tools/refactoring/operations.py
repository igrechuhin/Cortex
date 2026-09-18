"""
Refactoring Operations Tools

This module contains refactoring suggestion tools for Memory Bank.

Total: 1 tool, 1 resource
- suggest_refactoring / suggest_refactoring_resource (cortex://analysis/suggest-refactoring/{type})
"""

from urllib.parse import unquote

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.refactoring.models import RefactoringSuggestionType

from .operation_concise import format_suggest_refactoring_response
from .operation_helpers import (
    parse_refactoring_suggestion_type,
    process_refactoring_request,
    suggest_refactoring_error_json,
    validate_suggest_refactoring_type,
)


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


# MCP registration removed — unused tool
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def suggest_refactoring(
    type: RefactoringSuggestionType | str,
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
        JSON string. For type="consolidation": status, type, min_similarity,
        opportunities (id, files, similarity, recommendation, confidence).
        For type="splits": status, type, size_threshold, recommendations.
        For type="reorganization": status, type, goal, plan (current_state,
        proposed_state, moves, new_structure). On error: status "error",
        error message, error_type.

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
    type_str = type.value if isinstance(type, RefactoringSuggestionType) else type
    root = await resolve_project_root_async(None, ctx)
    return await _suggest_refactoring_run(
        type_str,
        str(root),
        min_similarity,
        size_threshold,
        goal,
        preview_suggestion_id,
        response_format,
        ctx,
    )


# MCP resource registration removed
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
