"""Shared helpers for building MCP tool responses.

All Cortex MCP tools should use these helpers so responses share a single,
canonical shape:

Successful responses:
    {"status": "success", ...payload fields...}

Error responses:
    {
        "status": "error",
        "error": "<message>",
        "error_code": "<optional machine-readable code>",
        ...optional extra context fields...
    }
"""

from __future__ import annotations

from cortex.core.models import JsonValue, ModelDict, OperationStatus


def success_response(**data: JsonValue) -> ModelDict:
    """Build a canonical success response payload.

    Additional keyword arguments become top-level fields alongside ``status``.
    """

    response: ModelDict = {"status": OperationStatus.SUCCESS.value}
    # Kwargs are JSON-serializable by construction via JsonValue.
    for key, value in data.items():
        response[key] = value
    return response


def error_response(
    error: str,
    *,
    error_code: str | None = None,
    **extra: JsonValue,
) -> ModelDict:
    """Build a canonical error response payload.

    Args:
        error: Human-readable error message.
        error_code: Optional machine-readable error code.
        **extra: Optional additional JSON-serializable context fields
            (for example ``error_type``, ``context``, or tool-specific data).
    """

    response: ModelDict = {
        "status": OperationStatus.ERROR.value,
        "error": error,
    }
    if error_code is not None:
        response["error_code"] = error_code
    for key, value in extra.items():
        response[key] = value
    return response
