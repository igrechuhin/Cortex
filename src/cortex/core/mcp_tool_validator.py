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

logger = logging.getLogger(__name__)


def _is_test_context() -> bool:
    """Check if code is running in a test context (pytest)."""
    return "pytest" in sys.modules or "_pytest" in sys.modules


def validate_mcp_tool_response(
    response: object,
    tool_name: str,
    step_name: str,
    project_root: str | None = None,
) -> None:
    """Validate MCP tool response and enforce failure protocol.

    This function should be called after each MCP tool call in commit procedure
    to ensure the response is valid and detect tool failures.

    NOTE: A response with status="error" is NOT a tool failure - it means the tool
    worked correctly and found errors (e.g., type errors, lint errors). Tool failures
    are things like JSON parsing errors, connection errors, or malformed responses.

    Args:
        response: Response from MCP tool call
        tool_name: Name of the tool that was called
        step_name: Commit procedure step name
        project_root: Project root directory (auto-detected if None)

    Raises:
        MCPToolFailure: If tool response indicates a tool failure (not error status)
        ProtocolViolation: If response validation fails
    """
    project_root_path = Path(project_root) if project_root else None
    failure_handler = MCPToolFailureHandler(project_root_path)

    # Check for None response - this is always a tool failure
    # This check should run even in test contexts
    if response is None:
        error = ValueError(f"MCP tool {tool_name} returned None response")
        # Always handle as failure - None response is never valid
        failure_handler.handle_failure(tool_name, error, step_name)

    # Check for JSON string (should be dict, not string)
    # This check should run even in test contexts to detect double-encoding
    if isinstance(response, str):
        try:
            # Try to parse as JSON
            json.loads(response)
            # If it parses, it might be a double-encoded response (tool failure)
            error_msg = (
                f"MCP tool {tool_name} returned JSON string instead of dict "
                f"(possible double-encoding): {response[:100]}"
            )
            error = ValueError(error_msg)
            if failure_handler.detect_failure(error, tool_name, step_name):
                failure_handler.handle_failure(tool_name, error, step_name)
        except json.JSONDecodeError:
            # Not JSON, might be valid string response
            pass

    # Skip other validation in test contexts to avoid false positives
    # Tests may call tools directly without MCP protocol, and some validations
    # (like missing status field) are acceptable for testing
    if _is_test_context():
        return

    # Check for dict response structure
    if isinstance(response, dict):
        # NOTE: A response with status="error" is a VALID response, not a tool failure!
        # The tool worked correctly and is reporting that it found errors in the code.
        # We do NOT raise MCPToolFailure for this case.

        # Check for malformed response structure (missing required fields)
        # Most MCP tools return dict with "status" field
        response_dict = cast(dict[str, object], response)
        if "status" not in response_dict:
            # Might be valid for some tools, but log warning
            response_preview = str(response_dict)[:200]
            logger.warning(
                f"MCP tool {tool_name} response missing 'status' field: {response_preview}"
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
