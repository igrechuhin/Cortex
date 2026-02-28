"""
Refactoring Operations Tools

This module contains refactoring suggestion tools for Memory Bank.

Total: 1 tool, 1 resource
- suggest_refactoring / suggest_refactoring_resource (cortex://analysis/suggest-refactoring/{type})
"""

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
from cortex.refactoring.models import RefactoringSuggestionType
from cortex.server import mcp
from cortex.tools.refactoring_operation_helpers import (
    format_suggest_refactoring_response,
    parse_refactoring_suggestion_type,
    process_refactoring_request,
    suggest_refactoring_error_json,
    validate_suggest_refactoring_type,
)
from cortex.tools.refactoring_operations_docs import SUGGEST_REFACTORING_DOCSTRING
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
    """Generate refactoring suggestions. See SUGGEST_REFACTORING_DOCSTRING for full docs."""
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


suggest_refactoring.__doc__ = SUGGEST_REFACTORING_DOCSTRING


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
