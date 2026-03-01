"""Phase 5: provide_feedback tool.

Extracted from phase5_execution to keep the main module under 400 lines.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.phase5_execution_planning import provide_feedback_impl


# Internalized for tool budget reduction (2026-02-26). Kept as callable for learning engine.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def provide_feedback(
    suggestion_id: str,
    feedback_type: str,
    comment: str | None = None,
    adjust_preferences: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Provide feedback on refactoring suggestions to improve future recommendations.

    USE WHEN: User wants to give feedback, user needs to rate suggestions,
    user requests feedback submission, user wants to improve learning.

    EXAMPLES: 'provide feedback on suggestion X', 'rate refactoring Y',
    'submit feedback for improvement'.

    RETURNS: JSON with feedback submission status and learning updates.

    This tool captures user feedback on refactoring suggestions to train the learning
    engine. The system analyzes patterns in feedback to adjust confidence thresholds,
    identify successful refactoring patterns, and learn user preferences. Feedback
    influences future suggestions by updating the internal pattern library and
    preference weights.

    The learning engine tracks approval rates, application success rates, and
    feedback patterns to continuously improve suggestion quality. All feedback
    is persisted in the learning database with full audit trail including
    timestamps, confidence scores, and suggestion details.

    Args:
        suggestion_id: ID of the refactoring suggestion to provide feedback on.
            Must match an existing suggestion from get_refactoring_suggestions().
            Example: "ref-consolidate-20240115123045"
        feedback_type: Type of feedback to provide. Must be one of:
            - "helpful": Suggestion was valuable and appropriate
            - "not_helpful": Suggestion was not useful but not wrong
            - "incorrect": Suggestion was wrong or would cause issues
        comment: Optional detailed comment explaining the feedback reason.
            Helps the learning engine understand specific context.
            Example: "Good consolidation but prefer different naming"
        adjust_preferences: If True, automatically update user preferences and
            confidence thresholds based on this feedback. If False, record
            feedback without adjusting learning parameters.
            Default: True

    Returns:
        JSON string with feedback confirmation and learning statistics.
    """
    await log_client(ctx, "info", "provide_feedback: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)
    try:
        return await provide_feedback_impl(
            suggestion_id, feedback_type, comment, adjust_preferences, str(root), ctx
        )
    except Exception as e:
        await log_client(ctx, "error", f"provide_feedback: {e!s}", logger_name=__name__)
        from cortex.tools.tool_error_formatters import format_tool_error

        return format_tool_error(
            e,
            suggestion=(
                "Review the error details. Ensure suggestion_id is valid and "
                "feedback_type is one of: 'helpful', 'not_helpful', or 'incorrect'. "
                "Check that the suggestion exists before providing feedback."
            ),
            example={
                "suggestion_id": "ref-consolidate-20240115123045",
                "feedback_type": "helpful",
                "comment": "Great consolidation suggestion",
            },
            available_options=["helpful", "not_helpful", "incorrect"],
        )
