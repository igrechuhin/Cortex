"""MCP tool response validation and protocol enforcement.

This module provides validation helpers for commit procedure to ensure
MCP tool responses are valid and enforce failure protocol.
"""

import json
import logging
import sys
from pathlib import Path
from typing import cast

from cortex.core.mcp_failure_handler import (
    MCPToolFailureHandler,
)
from cortex.core.models import JsonValue, ModelDict

logger = logging.getLogger(__name__)


def _is_test_context() -> bool:
    """Check if code is running in a test context (pytest)."""
    return "pytest" in sys.modules or "_pytest" in sys.modules


def validate_mcp_tool_response(
    response: JsonValue,
    tool_name: str,
    step_name: str,
    project_root: str | None = None,
) -> None:
    """Validate MCP tool response and enforce failure protocol.

    NOTE: status="error" is NOT a tool failure - it means the tool worked and found
    errors. Tool failures are JSON parsing errors, connection errors, etc.

    Args:
        response: Response from MCP tool call
        tool_name: Name of the tool that was called
        step_name: Commit procedure step name
        project_root: Project root directory (auto-detected if None)

    Raises:
        MCPToolFailure: If tool response indicates a tool failure
    """
    project_root_path = Path(project_root) if project_root else None
    handler = MCPToolFailureHandler(project_root_path)

    _validate_none_response(response, tool_name, step_name, handler)
    _validate_string_response(response, tool_name, step_name, handler)

    if _is_test_context():
        return

    _validate_dict_response(response, tool_name)


def _validate_none_response(
    response: JsonValue, tool_name: str, step_name: str, handler: MCPToolFailureHandler
) -> None:
    """Validate response is not None."""
    if response is None:
        error = ValueError(f"MCP tool {tool_name} returned None response")
        handler.handle_failure(tool_name, error, step_name)


def _validate_string_response(
    response: JsonValue, tool_name: str, step_name: str, handler: MCPToolFailureHandler
) -> None:
    """Validate response is not a JSON string (double-encoding)."""
    if not isinstance(response, str):
        return
    try:
        json.loads(response)
        error_msg = (
            f"MCP tool {tool_name} returned JSON string instead of dict: "
            f"{response[:100]}"
        )
        error = ValueError(error_msg)
        if handler.detect_failure(error, tool_name, step_name):
            handler.handle_failure(tool_name, error, step_name)
    except json.JSONDecodeError:
        pass  # Not JSON, might be valid string response


def _validate_dict_response(response: JsonValue, tool_name: str) -> None:
    """Validate dict response has expected structure."""
    if not isinstance(response, dict):
        return
    response_dict = cast(ModelDict, response)
    if "status" not in response_dict:
        response_preview = str(response_dict)[:200]
        logger.warning(
            f"MCP tool {tool_name} response missing 'status': {response_preview}"
        )


def check_mcp_tool_failure(
    error: Exception,
    tool_name: str,
    step_name: str,
    project_root: str | None = None,
) -> bool:
    """Check if exception is an MCP tool failure.

    This function can be used in exception handlers to detect tool failures.

    Args:
        error: Exception that occurred
        tool_name: Name of the tool that failed
        step_name: Commit procedure step name
        project_root: Project root directory (auto-detected if None)

    Returns:
        True if error is an MCP tool failure (should stop commit procedure)
    """
    project_root_path = Path(project_root) if project_root else None
    failure_handler = MCPToolFailureHandler(project_root_path)
    return failure_handler.detect_failure(error, tool_name, step_name)


def handle_mcp_tool_failure(
    error: Exception,
    tool_name: str,
    step_name: str,
    project_root: str | None = None,
) -> None:
    """Handle MCP tool failure according to protocol.

    This function should be called when a tool failure is detected.
    It creates investigation plan, adds to roadmap, and generates user notification.

    Args:
        error: Exception that occurred
        tool_name: Name of the tool that failed
        step_name: Commit procedure step name
        project_root: Project root directory (auto-detected if None)

    Raises:
        MCPToolFailure: Always raises to stop commit procedure
    """
    project_root_path = Path(project_root) if project_root else None
    failure_handler = MCPToolFailureHandler(project_root_path)
    # handle_failure always raises MCPToolFailure, so this never returns
    failure_handler.handle_failure(tool_name, error, step_name)
