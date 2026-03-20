"""MCP tool failure detection logic.

Provides async functions that classify exceptions as MCP tool failures
(JSON parsing, connection, unexpected-behavior, protocol errors) vs
expected application errors that should propagate normally.
"""

from __future__ import annotations

import json
import logging

from cortex.core.context_logging import MCPContext, log_client

logger = logging.getLogger(__name__)


def _is_json_value_error(error_str: str) -> bool:
    """Check if a ValueError is JSON-related."""
    json_keywords = ["json", "decode", "parse", "malformed", "invalid", "encoding"]
    return any(kw in error_str for kw in json_keywords)


async def _log_json_error(
    ctx: MCPContext | None,
    tool_name: str,
    step_name: str,
    error: Exception,
    error_type: str,
) -> None:
    """Log JSON error to client and server."""
    msg = f"Detected {error_type} in {tool_name} during {step_name}: {error}"
    await log_client(ctx, "error", msg)
    logger.debug(f"{error_type} details: {error}")


async def check_json_error(
    error: Exception,
    error_str: str,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Check for JSON parsing errors."""
    if isinstance(error, json.JSONDecodeError):
        await _log_json_error(ctx, tool_name, step_name, error, "JSON parsing error")
        return True
    if isinstance(error, ValueError) and _is_json_value_error(error_str):
        await _log_json_error(
            ctx, tool_name, step_name, error, "JSON-related ValueError"
        )
        return True
    return False


async def check_connection_error(
    error: Exception,
    error_str: str,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Check for connection-related errors."""
    if not isinstance(error, (ConnectionError, BrokenPipeError, OSError)):
        return False
    connection_keywords = [
        "connection closed",
        "connection reset",
        "broken pipe",
        "-32000",
        "stdio",
        "resource",
        "broken resource",
    ]
    if any(kw in error_str for kw in connection_keywords):
        msg = (
            f"Detected connection error in {tool_name} during " f"{step_name}: {error}"
        )
        await log_client(ctx, "error", msg)
        logger.debug(f"Connection error details: {error}")
        return True
    return False


async def check_type_attribute_key_error(
    error: Exception,
    error_str: str,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Check for TypeError, AttributeError, or KeyError with unexpected behavior."""
    if not isinstance(error, (TypeError, AttributeError, KeyError)):
        return False
    unexpected_keywords = [
        "unexpected",
        "missing",
        "invalid",
        "wrong type",
        "not found",
        "cannot access",
        "has no attribute",
        "keyerror",
    ]
    if any(kw in error_str for kw in unexpected_keywords):
        msg = (
            f"Detected unexpected behavior in {tool_name} during "
            f"{step_name}: {error}"
        )
        await log_client(ctx, "error", msg)
        logger.debug(f"Unexpected behavior details: {error}")
        return True
    return False


async def check_runtime_error(
    error: Exception,
    error_str: str,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Check for RuntimeError with tool-related keywords."""
    if not isinstance(error, RuntimeError):
        return False
    tool_keywords = [
        "mcp",
        "tool",
        "protocol",
        "serialization",
        "deserialization",
        "double-encoding",
        "json string instead of dict",
    ]
    if any(kw in error_str for kw in tool_keywords):
        msg = f"Detected runtime error in {tool_name} during {step_name}: {error}"
        await log_client(ctx, "error", msg)
        logger.debug(f"Runtime error details: {error}")
        return True
    return False


async def check_unexpected_behavior(
    error: Exception,
    error_str: str,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Check for unexpected behavior errors (type/attribute/key or runtime)."""
    if await check_type_attribute_key_error(
        error, error_str, tool_name, step_name, ctx
    ):
        return True
    return await check_runtime_error(error, error_str, tool_name, step_name, ctx)


async def detect_failure(
    error: Exception,
    tool_name: str,
    step_name: str,
    ctx: MCPContext | None = None,
) -> bool:
    """Detect if an error is an MCP tool failure.

    Distinguishes between actual tool failures and expected errors.

    Args:
        error: Exception to classify.
        tool_name: Name of the tool that failed.
        step_name: Commit procedure step where the failure occurred.
        ctx: Optional MCP context for client-visible logging.

    Returns:
        True if the error is an MCP tool failure, False otherwise.
    """
    error_str = str(error).lower()
    if await check_json_error(error, error_str, tool_name, step_name, ctx):
        return True
    if await check_connection_error(error, error_str, tool_name, step_name, ctx):
        return True
    if await check_unexpected_behavior(error, error_str, tool_name, step_name, ctx):
        return True
    if "fastmcp" in error_str or "mcp error" in error_str:
        msg = (
            f"Detected MCP protocol error in {tool_name} during "
            f"{step_name}: {error}"
        )
        await log_client(ctx, "error", msg)
        logger.debug(f"MCP protocol error details: {error}")
        return True
    return False
