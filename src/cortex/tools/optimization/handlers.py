"""Phase 4 token optimization handlers and resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from urllib.parse import unquote

import cortex.tools.optimization as opt
from cortex.core.cache import TTLCache
from cortex.core.constants import (
    CORTEX_CONTEXT_RESOURCE_READ_META,
    MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS,
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ContextDepth, OperationStatus, ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.context.l0_identity import build_l0
from cortex.tools.context.l1_essential import build_l1
from cortex.tools.context.l2_on_demand import build_l2
from cortex.tools.context.l3_deep_search import build_l3
from cortex.tools.context.layers import ContextConfig, ContextLayer, LayerResult
from cortex.tools.context.scoped_snapshot import ScopedSnapshot
from cortex.tools.optimization.context_appenders import (
    append_context_scoped_payload as _append_scoped_context_to_payload,
)
from cortex.tools.optimization.context_appenders import (
    append_explore_summary_to_context_payload as _append_explore_summary_to_context_payload,
)
from cortex.tools.optimization.context_appenders import (
    append_recent_artifacts_to_context_payload as _append_recent_artifacts_to_context_payload,
)
from cortex.tools.optimization.context_appenders import (
    append_recent_ingested_sources_to_context_payload as _append_recent_ingested_sources_to_context_payload,
)
from cortex.tools.optimization.context_appenders import (
    append_recent_operations_to_context_payload as _append_recent_operations_to_context_payload,
)
from cortex.tools.optimization.context_appenders import (
    append_session_goal_to_context_payload,
    read_recent_ingested_sources_markdown,
    session_config_mapping,
)
from cortex.tools.optimization.context_appenders import (
    append_session_scope_to_context_payload as _append_session_scope_to_context_payload,
)
from cortex.tools.optimization.context_appenders import (
    read_explore_summary_markdown as _read_explore_summary_markdown,
)
from cortex.tools.optimization.context_appenders import (
    read_recent_artifacts_markdown as _read_recent_artifacts_markdown,
)
from cortex.tools.optimization.context_appenders import (
    read_recent_operations_lines as _read_recent_operations_lines,
)
from cortex.tools.optimization.context_appenders import (
    resolve_context_cache_scope as _resolve_context_cache_scope,
)
from cortex.tools.optimization.context_budget import (
    context_token_counter,
    enforce_context_budget,
    invalid_context_budget,
)
from cortex.tools.optimization.relevance_operations import get_relevance_scores_impl
from cortex.tools.optimization.scoped_resource import (
    load_revision_bound_context,
    parse_context_layers,
    render_context_layer,
)
from cortex.tools.optimization.summarization_operations import summarize_content_impl
from cortex.tools.synapse.rules_operations import get_relevant_rules

from .handlers_format import inject_plan_graph_into_context_result
from .handlers_load import check_optimization_enabled, execute_load_context_with_logging
from .handlers_validation import (
    is_non_trivial_task,
    resolve_load_context_budget,
    validate_task_description_length,
)

__all__ = [
    "append_session_goal_to_context_payload",
    "build_context_resource_payload_async",
    "execute_load_context_with_logging",
    "get_relevant_rules",
    "get_relevance_scores",
    "get_relevance_scores_resource",
    "invalidate_context_resource_cache",
    "is_non_trivial_task",
    "load_context",
    "load_context_impl",
    "log_client",
    "read_recent_ingested_sources_markdown",
    "resolve_load_context_budget",
    "summarize_content",
    "summarize_content_resource",
]

_context_resource_cache: TTLCache[tuple[str, str]] = TTLCache(
    MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS
)
_LOAD_CONTEXT_DEFAULT_BUDGET = 10000


def invalidate_context_resource_cache(key: str | None = None) -> None:
    if key is None:
        _context_resource_cache.clear()
    else:
        _context_resource_cache.invalidate(key)


async def _build_layered_context_payload(
    project_root: Path, layers: list[ContextLayer], topic: str | None, query: str | None
) -> tuple[str, list[str], str, list[str]]:
    config = ContextConfig()
    results: list[LayerResult] = [
        await build_l0(project_root, config),
        await build_l1(project_root, config),
    ]
    essential_payload, essential_names = _render_layers(results)
    if ContextLayer.ON_DEMAND in layers and topic:
        results.append(await build_l2(project_root, config, topic))
    if ContextLayer.DEEP_SEARCH in layers and query:
        results.append(await build_l3(project_root, query))
    layered_payload, loaded_layers = _render_layers(results)
    return layered_payload, loaded_layers, essential_payload, essential_names


def _render_layers(results: list[LayerResult]) -> tuple[str, list[str]]:
    loaded_layers = [
        result.layer.value.upper() for result in results if result.content.strip()
    ]
    body_blocks = [render_context_layer(result) for result in results]
    body = "\n\n".join([block for block in body_blocks if block]).strip()
    loaded_names = ", ".join(loaded_layers)
    header = f"## Context layers loaded: [{loaded_names}]"
    footer = "## Available on demand: L2 (topic=<slug>), L3 (query=<search term>)"
    return f"{header}\n\n{body}\n\n{footer}".strip(), loaded_layers


def _inject_layered_payload(
    base_payload: str, layered_payload: str, loaded_layers: list[str]
) -> str:
    try:
        payload_obj = json.loads(base_payload)
    except json.JSONDecodeError:
        return f"{layered_payload}\n\n{base_payload}".strip()
    if not isinstance(payload_obj, dict):
        return f"{layered_payload}\n\n{base_payload}".strip()
    payload_obj["context_layers_loaded"] = loaded_layers
    payload_obj["layered_context"] = layered_payload
    return json.dumps(payload_obj, indent=2, sort_keys=True)


def _resolve_load_context_inputs(
    task_description: str | None, token_budget: int | None
) -> tuple[str, int | None]:
    if task_description:
        return task_description, token_budget
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    resolved_task = str(cfg.get("task_description", "session context"))
    if token_budget is None:
        raw_budget = cfg.get("token_budget")
        if isinstance(raw_budget, int):
            token_budget = raw_budget
    return resolved_task, token_budget


async def _run_load_context_with_resolved_budget(
    resolved_task: str,
    resolved_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    effective_budget, budget_error = resolve_load_context_budget(
        resolved_task, resolved_budget
    )
    if budget_error is not None:
        return budget_error
    return await execute_load_context_with_logging(
        resolved_task,
        effective_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context_impl(
    task_description: str | None = None,
    token_budget: int | None = None,
    strategy: str = "dependency_aware",
    loading_strategy: str | None = None,
    depth: ContextDepth | None = None,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    role: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    await log_client(ctx, "info", "load_context: starting", logger_name=__name__)
    resolved_task, resolved_budget = _resolve_load_context_inputs(
        task_description, token_budget
    )
    if (length_error := validate_task_description_length(resolved_task)) is not None:
        return length_error
    result = await _run_load_context_with_resolved_budget(
        resolved_task,
        resolved_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )
    await log_client(ctx, "info", "load_context: completed", logger_name=__name__)
    return result


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content(
    file_name: str | None = None,
    target_reduction: float | None = None,
    strategy: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    await log_client(ctx, "info", "summarize_content: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await opt.get_managers(root)
        enabled_error = await check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error
        out = await summarize_content_impl(mgrs, file_name, target_reduction, strategy)
        await log_client(
            ctx, "info", "summarize_content: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"summarize_content: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
            sort_keys=True,
        )


async def _run_relevance_scores(
    task_description: str,
    include_sections: bool,
    ctx: MCPContext | None,
) -> str:
    root = await resolve_project_root_async(None, ctx)
    mgrs = await opt.get_managers(root)
    enabled_error = await check_optimization_enabled(mgrs)
    if enabled_error:
        return enabled_error
    return await get_relevance_scores_impl(mgrs, task_description, include_sections)


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores(
    task_description: str | None = None,
    include_sections: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    await log_client(
        ctx, "info", "get_relevance_scores: starting", logger_name=__name__
    )
    try:
        resolved_task, _ = _resolve_load_context_inputs(task_description, None)
        out = await _run_relevance_scores(resolved_task, include_sections, ctx)
        await log_client(
            ctx, "info", "get_relevance_scores: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"get_relevance_scores: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
            sort_keys=True,
        )


async def build_context_resource_payload_async(
    base_payload: str, project_root: Path, snapshot: ScopedSnapshot | None = None
) -> str:
    summaries = _context_resource_summaries(project_root, snapshot)
    with_goal = (
        append_session_goal_to_context_payload(base_payload, project_root, snapshot)
        if snapshot
        else append_session_goal_to_context_payload(base_payload, project_root)
    )
    scoped = _append_session_scope_to_context_payload(with_goal)
    scoped = (
        await _append_scoped_context_to_payload(scoped, project_root, snapshot)
        if snapshot
        else await _append_scoped_context_to_payload(scoped, project_root)
    )
    payload = _append_recent_artifacts_to_context_payload(
        _append_recent_operations_to_context_payload(
            _append_explore_summary_to_context_payload(
                _append_recent_ingested_sources_to_context_payload(
                    scoped, summaries.get("recent_ingested_sources")
                ),
                summaries.get("explore_summary"),
            ),
            summaries.get("recent_operations"),
        ),
        summaries.get("recent_artifacts"),
    )
    return inject_plan_graph_into_context_result(payload, project_root)


async def _assemble_budgeted_context(
    task: str,
    budget: int,
    layers: list[ContextLayer],
    topic: str | None,
    query: str | None,
    root: Path,
    snapshot: ScopedSnapshot | None,
) -> str:
    result = await load_context_impl(task_description=task, token_budget=budget)
    base_payload = (
        await build_context_resource_payload_async(result, root, snapshot)
        if snapshot
        else await build_context_resource_payload_async(result, root)
    )
    layered, loaded, essential, essential_names = await _build_layered_context_payload(
        root, layers, topic, query
    )
    return enforce_context_budget(
        _inject_layered_payload(base_payload, layered, loaded),
        budget,
        essential,
        essential_names,
        context_token_counter(),
    )


@mcp.resource(uri="cortex://context", meta=CORTEX_CONTEXT_RESOURCE_READ_META)
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context() -> str:
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    task = str(cfg.get("task_description", "general session context"))
    selected_layers = parse_context_layers(cfg.get("context_layers"))
    selected_topic = str(cfg.get("context_topic", "")).strip() or None
    selected_query = str(cfg.get("context_query", "")).strip() or None
    raw_budget = cfg.get("token_budget", _LOAD_CONTEXT_DEFAULT_BUDGET)
    budget_error = invalid_context_budget(raw_budget)
    if budget_error is not None:
        return budget_error
    budget = cast(int, raw_budget)
    cache_key = _resource_cache_key(
        task, budget, selected_layers, selected_topic, selected_query
    )
    root = await resolve_project_root_async(None, None)
    return await load_revision_bound_context(
        root,
        session_config_mapping(cfg),
        cache_key,
        _context_resource_cache,
        lambda snapshot: _assemble_budgeted_context(
            task,
            budget,
            selected_layers,
            selected_topic,
            selected_query,
            root,
            snapshot,
        ),
    )


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores_resource(task_description: str) -> str:
    decoded = unquote(task_description)
    return await get_relevance_scores(task_description=decoded, include_sections=False)


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content_resource(file_name: str) -> str:
    decoded = unquote(file_name)
    name_arg: str | None = None if decoded in ("_", "all", "") else decoded
    return await summarize_content(
        file_name=name_arg,
        target_reduction=None,
        strategy=None,
    )


def _context_resource_summaries(
    project_root: Path, snapshot: ScopedSnapshot | None
) -> dict[str, str | None]:
    if snapshot is not None:
        return snapshot.summaries
    return {
        "recent_operations": _read_recent_operations_lines(project_root),
        "recent_artifacts": _read_recent_artifacts_markdown(project_root),
        "recent_ingested_sources": read_recent_ingested_sources_markdown(project_root),
        "explore_summary": _read_explore_summary_markdown(project_root),
    }


def _resource_cache_key(
    task: str,
    budget: int,
    layers: list[ContextLayer],
    topic: str | None,
    query: str | None,
) -> str:
    scope_key = _resolve_context_cache_scope()
    return (
        f"context:{task}:{budget}:{scope_key}:"
        f"{','.join(layer.value for layer in layers)}:{topic}:{query}"
    )
