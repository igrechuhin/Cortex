"""Plan enrichment flow for clarification marker resolution."""

from __future__ import annotations

from pathlib import Path

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_utils import (
    apply_clarifications_summary_to_plan,
    find_clarification_markers,
    resolve_clarification_markers,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.enrich_models import EnrichPlanResult


def _resolve_target_plan_path(
    root: Path,
    *,
    slug: str | None,
    plan_file_name: str | None,
    plan_relative_path: str | None,
) -> Path | None:
    if plan_relative_path:
        return root / plan_relative_path
    if plan_file_name:
        return get_cortex_path(root, CortexResourceType.PLANS) / plan_file_name
    if slug:
        return get_cortex_path(root, CortexResourceType.PLANS) / f"{slug}.md"
    return None


def _append_resolution_delta(content: str, resolved_markers: int) -> str:
    if resolved_markers <= 0:
        return content
    heading = "## Clarification Resolution Delta"
    bullet = f"- Resolved {resolved_markers} clarification marker(s) via plan enrich."
    if heading in content:
        return f"{content.rstrip()}\n{bullet}\n"
    return f"{content.rstrip()}\n\n{heading}\n\n{bullet}\n"


def _enrich_plan_content(
    content: str, resolved_clarifications: dict[str, str]
) -> tuple[str, int, int]:
    replaced, resolved_count = resolve_clarification_markers(
        content, resolved_clarifications
    )
    with_summary, _ = apply_clarifications_summary_to_plan(replaced)
    with_delta = _append_resolution_delta(with_summary, resolved_count)
    remaining = len(find_clarification_markers(with_delta))
    return with_delta, resolved_count, remaining


async def _enrich_plan_impl(
    *,
    slug: str | None,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    resolved_clarifications: dict[str, str],
    ctx: MCPContext | None,
) -> str:
    root = await resolve_project_root_async(None, ctx)
    target = _resolve_target_plan_path(
        root,
        slug=slug,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
    )
    if target is None:
        return _missing_target_result()
    if not target.exists():
        return _plan_not_found_result(target)
    return await _enrich_existing_plan(target, resolved_clarifications, ctx)


def _missing_target_result() -> str:
    return EnrichPlanResult(
        status=ToolResultStatus.ERROR,
        message="slug, plan_file_name, or plan_relative_path is required",
        error="Missing target plan reference",
    ).model_dump_json()


def _plan_not_found_result(target: Path) -> str:
    return EnrichPlanResult(
        status=ToolResultStatus.ERROR,
        file_path=str(target),
        message="Plan file not found",
        error=f"Plan not found at {target}",
    ).model_dump_json()


async def _enrich_existing_plan(
    target: Path,
    resolved_clarifications: dict[str, str],
    ctx: MCPContext | None,
) -> str:
    content = target.read_text(encoding="utf-8")
    enriched, resolved_count, remaining_count = _enrich_plan_content(
        content, resolved_clarifications
    )
    _ = target.write_text(enriched, encoding="utf-8")
    await log_client(
        ctx,
        "info",
        f"enrich_plan: resolved={resolved_count}, remaining={remaining_count}, file={target}",
        logger_name=__name__,
    )
    return EnrichPlanResult(
        status=ToolResultStatus.SUCCESS,
        file_path=str(target),
        message="Plan enrichment complete",
        resolved_markers=resolved_count,
        remaining_markers=remaining_count,
    ).model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def enrich_plan(
    slug: str | None = None,
    plan_file_name: str | None = None,
    plan_relative_path: str | None = None,
    resolved_clarifications: dict[str, str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Resolve plan clarification markers and refresh the summary section."""
    payload = resolved_clarifications or {}
    return await _enrich_plan_impl(
        slug=slug,
        plan_file_name=plan_file_name,
        plan_relative_path=plan_relative_path,
        resolved_clarifications=payload,
        ctx=ctx,
    )
