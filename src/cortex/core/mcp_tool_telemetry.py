"""Redacted tool-invocation telemetry hook for the MCP tool dispatch wrapper.

Wires into ``mcp_tool_wrapper`` (the single per-tool dispatch interception
point also used by ``record_usage_finish``/``UsageTracker`` for
``query_usage(query_type="anomalies")`` telemetry) to additionally persist a
session-scoped, append-only JSONL record of tool name + arg key names +
outcome via :mod:`cortex.memory.wal_hooks`.

This is an additive evidence source for analyze-tools/analyze-session
consolidation-candidate detection -- it does not replace or compete with the
existing UsageTracker-based anomaly telemetry. See plan:
tool-invocation-telemetry-log-to-strengthen-skill-crystallization-signal.
"""

from __future__ import annotations

from collections.abc import Mapping

from cortex.core.models import JsonValue
from cortex.core.usage_context import get_current_project_root
from cortex.memory.wal_hooks import (
    try_wal_record_tool_invocation,
    wal_arg_keys_from_kwargs,
)


def record_tool_invocation_success(
    tool_name: str, kwargs: Mapping[str, JsonValue]
) -> None:
    """Record a successful tool invocation (arg key names only, no values)."""
    root = get_current_project_root()
    arg_keys = wal_arg_keys_from_kwargs(kwargs)
    try_wal_record_tool_invocation(root, tool_name, arg_keys, True, None)


def record_tool_invocation_failure(
    tool_name: str, kwargs: Mapping[str, JsonValue], error_type: str
) -> None:
    """Record a failed tool invocation (arg key names only, no values)."""
    root = get_current_project_root()
    arg_keys = wal_arg_keys_from_kwargs(kwargs)
    try_wal_record_tool_invocation(root, tool_name, arg_keys, False, error_type)
