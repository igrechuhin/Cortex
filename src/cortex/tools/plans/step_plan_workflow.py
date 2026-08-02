"""Async handlers for step-by-step plan MCP operations."""

from __future__ import annotations

from pathlib import Path

from cortex.core.context_logging import MCPContext
from cortex.core.models import PlanningMode
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.crud import PlanCreateInputs
from cortex.tools.plans.crud_helpers import get_plan_directory
from cortex.tools.plans.step_draft_core import (
    draft_filename_for_slug,
    extract_goal_markdown,
    initial_section_records,
    render_step_draft_file,
    split_frontmatter,
)
from cortex.tools.plans.step_plan_internal import (
    approve_step_run,
    continue_step_run,
    finalize_step_run,
)


async def handle_continue_step(
    slug: str | None,
    content: str | None,
    ctx: MCPContext | None,
) -> str:
    """Append the next pending section as ``draft`` using agent-supplied markdown."""
    return await continue_step_run(slug, content, ctx)


async def handle_approve_step(
    slug: str | None,
    step_section: str | None,
    corrections: str | None,
    step_skip: bool,
    ctx: MCPContext | None,
) -> str:
    """Approve or revise the current draft section, or skip a pending section."""
    return await approve_step_run(slug, step_section, corrections, step_skip, ctx)


async def handle_finalize_step(
    slug: str | None,
    plan_title: str | None,
    description: str | None,
    status: str,
    section: str,
    plan_file_name: str | None,
    plan_relative_path: str | None,
    ctx: MCPContext | None,
) -> str:
    """Publish draft to final plan path and register roadmap entry."""
    return await finalize_step_run(
        slug,
        plan_title,
        description,
        status,
        section,
        plan_file_name,
        plan_relative_path,
        ctx,
    )


def planning_mode_from_param(raw: str | None) -> PlanningMode:
    """Normalize external ``mode`` string to :class:`PlanningMode`."""
    if raw is None or raw == "" or raw == PlanningMode.FAST_FORWARD.value:
        return PlanningMode.FAST_FORWARD
    if raw == PlanningMode.STEP_BY_STEP.value:
        return PlanningMode.STEP_BY_STEP
    # AI: Unknown tokens default to fast-forward to preserve backward compatibility.
    return PlanningMode.FAST_FORWARD


async def _write_step_draft_file(
    root: Path,
    title: str,
    slug: str | None,
    fm: str,
    goal_body: str,
) -> tuple[Path | None, str | None]:
    from cortex.tools.plans.crud_helpers import create_plan_file, sanitize_plan_slug

    bodies = {"goal": goal_body}
    records = initial_section_records()
    rendered = render_step_draft_file(fm, bodies, records)
    base_slug = slug if slug else sanitize_plan_slug(title)
    if not base_slug:
        return (None, "Could not derive slug for draft plan")
    draft_name = draft_filename_for_slug(base_slug)
    draft_slug_stem = draft_name[:-3]
    plans_dir = get_plan_directory(root)
    if (plans_dir / draft_name).is_file():
        return (None, f"Draft already exists: {draft_name}")
    return create_plan_file(root, title, draft_slug_stem, rendered)


def _draft_review_prompt(plan_path: Path | None) -> str:
    return (
        "Review the Goal section in the draft plan file. Reply with approve_step "
        "(step_section='goal') when satisfied, or pass corrections=... to revise. "
        f"Then use continue_step to draft the next section. Draft path: {plan_path}"
    )


async def create_step_draft_plan(
    inputs: PlanCreateInputs,
    ctx: MCPContext | None,
) -> tuple[Path | None, str | None, str]:
    """Build a draft plan containing only Goal; returns (path, error, review_prompt)."""
    from cortex.tools.plans.crud import build_staged_plan_markdown

    root = await resolve_project_root_async(None, ctx)
    final_content, _n = build_staged_plan_markdown(
        root, inputs.content, inputs.explore_log_path, inputs.shape_log_path
    )
    goal_body = extract_goal_markdown(final_content)
    if not goal_body:
        return (
            None,
            "Step-by-step create requires a non-empty '## Goal' section in the markdown",
            "",
        )
    title = inputs.title
    fm, _rest = split_frontmatter(final_content)
    if fm is None:
        fm = f'---\ntitle: "{title.replace(chr(34), chr(39))}"\nstatus: IN_PROGRESS\n---\n'
    plan_path, err = await _write_step_draft_file(
        root, title, inputs.slug, fm, goal_body
    )
    if err:
        return (plan_path, err, "")
    return (plan_path, err, _draft_review_prompt(plan_path))
