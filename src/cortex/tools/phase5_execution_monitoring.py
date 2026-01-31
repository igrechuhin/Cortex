"""Logging and monitoring helpers for Phase 5 execution tools.

Extracted to keep phase5_execution.py under 400 lines.
"""

from cortex.core.context_logging import MCPContext, log_client
from cortex.tools.phase5_execution_errors import (
    create_execution_error_response,
    create_invalid_action_error,
)


async def log_apply_result(
    ctx: MCPContext | None, out: str | None, exc: Exception | None
) -> str:
    """Log apply_refactoring result and return output or error response."""
    if exc is not None:
        await log_client(
            ctx, "error", f"apply_refactoring: {exc!s}", logger_name=__name__
        )
        return create_execution_error_response(exc)
    await log_client(ctx, "info", "apply_refactoring: completed", logger_name=__name__)
    return out or ""


async def log_invalid_action_and_return(ctx: MCPContext | None, action: str) -> str:
    """Log invalid action and return error JSON."""
    await log_client(
        ctx, "warning", "apply_refactoring: invalid action", logger_name=__name__
    )
    return create_invalid_action_error(action)


async def warn_suggestion_not_found_and_return(
    ctx: MCPContext | None, suggestion: str
) -> str:
    """Log suggestion-not-found warning and return error JSON."""
    await log_client(
        ctx,
        "warning",
        "provide_feedback: suggestion not found",
        logger_name=__name__,
    )
    return suggestion
