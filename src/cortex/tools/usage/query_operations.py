"""Unified usage analytics query tool (Phase 50).

Single entry point for tool usage stats, unused tools, report, recommendations,
search, events, observation, and timeline.
"""

from __future__ import annotations

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.server import mcp
from cortex.tools.response_builder import error_response

from .query_handlers import USAGE_HANDLERS
from .query_models import QueryUsageParams


def _usage_error_payload(message: str) -> str:
    """Return a JSON error payload for query_usage."""
    return json.dumps(
        error_response(error=message, error_type="ValueError"),
        indent=2,
    )


def _params_from_tool_args(
    locals_dict: dict[str, str | int | bool | list[str] | None],
) -> QueryUsageParams:
    """Build QueryUsageParams from query_usage's locals (excluding query_type, ctx)."""
    d: dict[str, str | int | bool | list[str] | None] = {
        k: v for k, v in locals_dict.items() if k not in ("query_type", "ctx")
    }
    d["ids"] = d.get("ids") or []
    rf = d.get("response_format", ResponseFormat.CONCISE)
    d["response_format"] = ResponseFormat(rf) if isinstance(rf, str) else rf
    return QueryUsageParams.model_validate(d)


def _build_query_usage_params_from_locals(
    locals_dict: dict[str, str | int | bool | list[str] | None],
) -> QueryUsageParams:
    """Build QueryUsageParams from query_usage's locals (excludes query_type, ctx)."""
    return _params_from_tool_args(
        {k: v for k, v in locals_dict.items() if k not in ("query_type", "ctx")}
    )


async def _query_usage_impl(
    query_type: str,
    params: QueryUsageParams,
    ctx: MCPContext | None,
) -> str:
    """Dispatch to the handler for query_type; catch and return errors as JSON."""
    handler = USAGE_HANDLERS.get(query_type)
    if handler is None:
        return _usage_error_payload(f"Unknown query_type: {query_type}")
    try:
        return await handler(params, ctx)
    except Exception as e:
        return json.dumps(
            error_response(error=str(e), error_type=type(e).__name__),
            indent=2,
        )


async def _log_query_usage_start(ctx: MCPContext | None, query_type: str) -> None:
    """Log that query_usage is starting."""
    await log_client(
        ctx,
        "info",
        f"query_usage: starting query_type={query_type}",
        logger_name=__name__,
    )


@mcp.tool(annotations=read_only_annotations("Query Usage"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def query_usage(
    query_type: str,
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    response_format: str = "concise",
    days: int = 30,
    min_usage_count: int = 0,
    min_usage_threshold: int = 5,
    ids: list[str] | None = None,
    observation_id: str | None = None,
    around_id: str | None = None,
    success: bool | None = None,
    limit: int = 50,
    query: str | None = None,
    format: str = "markdown",
    include_recommendations: bool = True,
    hours: int = 24,
    production_baseline_days: int = 7,
    production_window_hours: int = 24,
    ctx: MCPContext | None = None,
) -> str:
    """Query tool usage analytics: stats, unused tools, report, recommendations, anomalies.

    USE WHEN: User needs usage stats, low-usage tool list, optimization
    recommendations, session anomalies, or production monitoring.

    EXAMPLES: 'query_usage(query_type="stats")', 'get usage statistics',
    'query_usage(query_type="recommendations", days=90)',
    'query_usage(query_type="anomalies", hours=24)'.

    DO NOT:
    - Use this tool to mutate logs or usage records; it is analytics-only.
    - Call it in tight loops or for per-turn logging; prefer periodic queries
      (for example, after a session or as part of scheduled analysis).

    RETURNS: JSON (or markdown when format=markdown) with result for
    query_type: stats, unused, report, recommendations, search, events,
    observation, timeline, anomalies, tool_description_optimization,
    production_monitoring, token_efficiency, redundancy, session_continuity,
    tool_frequency, tool_classification. tool_name required for
    tool_description_optimization.     tool_classification returns usage-ranked
    tools with current category (agent-skills Step 3).
    token_efficiency shows top token-expensive tools (Anthropic Step 2).
    redundancy shows repeated identical calls (Step 3). session_continuity
    tracks turns until productive (Step 5). tool_frequency shows tools by
    session presence and token savings when tiered loading is enabled (Step 6).

    Args:
        query_type: stats, unused, report, recommendations, anomalies, etc.
        tool_name: Required for tool_description_optimization. Optional for others.
        days, hours, limit: Query-specific window and limit parameters.
    """
    await _log_query_usage_start(ctx, query_type)
    params = _build_query_usage_params_from_locals(locals())
    return await _query_usage_impl(query_type, params, ctx)
