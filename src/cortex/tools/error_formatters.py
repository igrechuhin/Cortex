"""Standardized tool error response formatting.

This module provides consistent error response formatting for all MCP tools,
following Anthropic's guidance: "error responses should clearly communicate
specific and actionable improvements, rather than opaque error codes or tracebacks."

Structure:
- ToolErrorResponse: Pydantic model for standardized error JSON
- format_tool_error: Main entry point; auto-generates suggestions when omitted
- Domain formatters: format_file_not_found_error, format_invalid_parameter_error,
  format_missing_parameter_error, format_validation_error, etc.
"""

from cortex.tools.error_formatters_core import (
    ToolErrorResponse,
    format_tool_error,
)
from cortex.tools.error_formatters_domain import (
    format_configuration_error,
    format_external_tool_error,
    format_file_not_found_error,
    format_invalid_parameter_error,
    format_missing_parameter_error,
    format_validation_error,
)

__all__ = [
    "ToolErrorResponse",
    "format_tool_error",
    "format_configuration_error",
    "format_external_tool_error",
    "format_file_not_found_error",
    "format_invalid_parameter_error",
    "format_missing_parameter_error",
    "format_validation_error",
]
