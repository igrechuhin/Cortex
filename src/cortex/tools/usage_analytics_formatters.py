"""Formatting and report-building helpers for usage analytics (Phase 29).

Extracted from usage_analytics.py for Phase 9.1 file size compliance.
"""

import json
from datetime import datetime
from typing import cast

from cortex.core.models import ResponseFormat
from cortex.tools.usage_analytics_models import SearchUsageResponse


def calls_key(t: dict[str, object]) -> int:
    """Sort key for tools by total_calls descending. Public for testing and callers."""
    v = t.get("total_calls", 0)
    return -(int(v) if isinstance(v, (int, float)) else 0)


def _format_tool_usage_stats_response(
    root: object,
    result: dict[str, object],
    response_format: ResponseFormat,
) -> str:
    """Format get_tool_usage_stats response based on response_format."""
    if response_format == ResponseFormat.CONCISE:
        tools_raw: list[dict[str, object]] = cast(
            list[dict[str, object]], result.get("tools") or []
        )
        top_tools = sorted(tools_raw, key=calls_key)[:5]
        concise_tools: list[dict[str, object]] = []
        for t in top_tools:
            name = str(t.get("tool_name", "?"))
            calls_val = t.get("total_calls", 0)
            calls = int(calls_val) if isinstance(calls_val, (int, float)) else 0
            concise_tools.append({"tool_name": name, "total_calls": calls})
        concise_payload: dict[str, object] = {
            "status": "success",
            "project_root": str(root),
            "top_5_tools": concise_tools,
        }
        return json.dumps(concise_payload, indent=2)
    return json.dumps(
        {"status": "success", "project_root": str(root), **result},
        indent=2,
    )


def format_tool_usage_stats_response(
    root: object,
    result: dict[str, object],
    response_format: ResponseFormat,
) -> str:
    """Public formatter for get_tool_usage_stats. See _format_tool_usage_stats_response."""
    return _format_tool_usage_stats_response(root, result, response_format)


def _build_search_usage_summary(entry: dict[str, object]) -> str:
    """Build a one-line summary string for a search_usage entry."""
    tool = str(entry.get("tool_name", "?"))
    ts = str(entry.get("timestamp", ""))
    success_flag = bool(entry.get("success"))
    duration_val = entry.get("duration_ms", 0.0)
    duration_ms = float(duration_val) if isinstance(duration_val, (int, float)) else 0.0
    status = "success" if success_flag else "error"
    return f"{tool} at {ts} - {status} ({duration_ms:.1f} ms)"


def format_search_usage_response(
    root: object,
    payload: SearchUsageResponse,
    response_format: ResponseFormat,
) -> str:
    """Format search_usage response based on response_format."""
    data = payload.model_dump()
    if response_format == ResponseFormat.CONCISE:
        results_raw: list[dict[str, object]] = cast(
            list[dict[str, object]], data.get("results") or []
        )
        concise_results: list[dict[str, object]] = []
        for entry in results_raw:
            concise_results.append(
                {
                    "id": entry.get("id"),
                    "summary": _build_search_usage_summary(entry),
                }
            )
        concise_payload: dict[str, object] = {
            "status": data.get("status", "success"),
            "project_root": data.get("project_root", str(root)),
            "total": data.get("total", len(concise_results)),
            "results": concise_results,
        }
        return json.dumps(concise_payload, indent=2)
    return json.dumps(data, indent=2)


def build_usage_report_text(
    tools: list[dict[str, object]], start: datetime, end: datetime, total: int
) -> str:
    """Build markdown report body from tools and date range. Public for callers."""
    lines = [
        "# MCP Tool Usage Report",
        "",
        f"Period: {start.date()} to {end.date()}",
        f"Total events: {total}",
        "",
        "## By tool",
        "",
    ]
    for t in sorted(tools, key=calls_key):
        name = str(t.get("tool_name", "?"))
        calls_val = t.get("total_calls", 0)
        calls = int(calls_val) if isinstance(calls_val, (int, float)) else 0
        avg_val = t.get("avg_duration_ms", 0)
        avg_ms = float(avg_val) if isinstance(avg_val, (int, float)) else 0.0
        lines.append(f"- **{name}**: {calls} calls, avg {avg_ms:.1f} ms")
    return "\n".join(lines)
