"""Core tool error formatting: model, fuzzy match, format_tool_error, suggestion logic."""

from __future__ import annotations

import json
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from cortex.core.models import JsonDict, JsonValue, ResponseStatus


class ToolErrorResponse(BaseModel):
    """Standardized error response model for all MCP tools.

    Extends ErrorResponseModel with additional fields for actionable guidance:
    - suggestion: What to do differently
    - example: Example of correct usage
    - available_options: Valid values if applicable

    All fields from ErrorResponseModel are preserved for backward compatibility.
    """

    model_config = {"extra": "forbid", "validate_assignment": True}

    status: ResponseStatus = Field(
        default=ResponseStatus.ERROR, description="Response status"
    )
    error: str = Field(description="Human-readable error message")
    error_type: str = Field(description="Exception class name")
    action_required: str | None = Field(
        default=None, description="Action required to resolve (legacy field)"
    )
    suggestion: str | None = Field(default=None, description="What to do differently")
    example: dict[str, JsonValue] | None = Field(
        default=None, description="Example of correct usage"
    )
    available_options: list[str] | None = Field(
        default=None, description="Valid values if applicable"
    )
    context: JsonDict | None = Field(default=None, description="Error context")

    def to_json(self) -> str:
        """Convert to JSON string with proper formatting.

        Returns:
            JSON string with indentation
        """
        return json.dumps(self.model_dump(exclude_none=True), indent=2)


def fuzzy_match(
    value: str, candidates: list[str], threshold: float = 0.6, max_results: int = 3
) -> list[str]:
    """Find fuzzy matches for a value among candidates.

    Args:
        value: Value to match
        candidates: List of candidate strings
        threshold: Minimum similarity ratio (0.0-1.0)
        max_results: Maximum number of results to return

    Returns:
        List of candidate strings sorted by similarity (best first)
    """
    matches: list[tuple[float, str]] = []
    for candidate in candidates:
        ratio = SequenceMatcher(None, value.lower(), candidate.lower()).ratio()
        if ratio >= threshold:
            matches.append((ratio, candidate))

    matches.sort(reverse=True, key=lambda x: x[0])
    return [candidate for _, candidate in matches[:max_results]]


def _suggestion_for_mcp_connection_errors(error_lower: str) -> str | None:
    """Return suggestion for MCP connection/closure errors."""
    if "tool not found" in error_lower:
        return (
            "The MCP connection may have dropped. Reconnect Cortex MCP and retry. "
            "See docs/guides/troubleshooting.md."
        )
    if (
        "connection" in error_lower
        or "closed" in error_lower
        or "32000" in error_lower
        or "broken" in error_lower
        or "resource" in error_lower
    ):
        return (
            "Reconnect Cortex MCP and retry. If the error persists, see "
            "docs/guides/troubleshooting.md#issue-mcp-error-32000-connection-closed."
        )
    return None


def _matches_any(error_lower: str, keywords: tuple[str, ...]) -> bool:
    """Return True if any keyword is in error_lower."""
    return any(kw in error_lower for kw in keywords)


def _matches_all(error_lower: str, keywords: tuple[str, ...]) -> bool:
    """Return True if all keywords are in error_lower."""
    return all(kw in error_lower for kw in keywords)


_ERROR_SUGGESTION_RULES: list[tuple[tuple[str, ...], str, bool]] = [
    (
        ("file", "not found"),
        "Verify the file name is correct. Use manage_file(operation='metadata') to list available files.",
        True,
    ),
    (
        ("invalid", "not valid"),
        "Check the parameter values and ensure they match the expected format.",
        False,
    ),
    (
        ("required", "missing"),
        "Provide all required parameters. Check the tool documentation for required fields.",
        False,
    ),
    (
        ("permission", "access"),
        "Check file system permissions. Ensure the process has read/write access to the required directories.",
        False,
    ),
    (
        ("timeout", "lock"),
        "The operation timed out or a lock could not be acquired. Wait and retry, or check for stale lock files.",
        False,
    ),
    (
        ("validation",),
        "The input does not meet validation requirements. Review the error details and fix the issues before retrying.",
        False,
    ),
]


def _generate_default_suggestion(error_type: str, error_message: str) -> str | None:
    """Generate default suggestion based on error type and message."""
    error_lower = error_message.lower()

    mcp_suggestion = _suggestion_for_mcp_connection_errors(error_lower)
    if mcp_suggestion is not None:
        return mcp_suggestion

    for keywords, suggestion, match_all in _ERROR_SUGGESTION_RULES:
        if match_all and _matches_all(error_lower, keywords):
            return suggestion
        if not match_all and _matches_any(error_lower, keywords):
            return suggestion

    return None


def format_tool_error(
    error: Exception,
    suggestion: str | None = None,
    example: dict[str, JsonValue] | None = None,
    available_options: list[str] | None = None,
    context: dict[str, JsonValue] | None = None,
    action_required: str | None = None,
) -> str:
    """Format a tool error into standardized ToolErrorResponse.

    This is the main entry point for creating consistent error responses
    across all MCP tools.

    Args:
        error: The exception that occurred
        suggestion: What to do differently (auto-generated if None)
        example: Example of correct usage (auto-generated if None)
        available_options: Valid values if applicable
        context: Additional error context
        action_required: Legacy field for backward compatibility

    Returns:
        JSON string with standardized error response
    """
    error_type = type(error).__name__
    error_message = str(error)

    if suggestion is None:
        suggestion = _generate_default_suggestion(error_type, error_message)

    context_model: JsonDict | None = None
    if context:
        context_model = JsonDict.from_dict(context)

    if suggestion is None and action_required:
        suggestion = action_required

    response = ToolErrorResponse(
        status=ResponseStatus.ERROR,
        error=error_message,
        error_type=error_type,
        action_required=action_required,
        suggestion=suggestion,
        example=example,
        available_options=available_options,
        context=context_model,
    )

    return response.to_json()
