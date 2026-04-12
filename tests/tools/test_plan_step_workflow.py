"""Tests for step-by-step plan MCP operations."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.plan import plan

_RESOLVE_PATCHES = (
    "cortex.tools.plans.step_plan_workflow.resolve_project_root_async",
    "cortex.tools.plans.step_plan_internal.resolve_project_root_async",
)


@contextmanager
def patch_step_roots(tmp_path: Path):
    with (
        patch(
            _RESOLVE_PATCHES[0],
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            _RESOLVE_PATCHES[1],
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
    ):
        yield


def _sample_plan_markdown() -> str:
    return """---
title: Demo Plan
status: PENDING
---
## Goal

Build planning modes.

## Context

High stakes.

## Implementation Steps

### Step 1: Wire tools

Edits.

## Verification

Manual.

## Testing Strategy

Pytest.
"""


@pytest.mark.asyncio
async def test_plan_create_step_mode_writes_draft_with_goal_only(
    tmp_path: Path,
) -> None:
    """planning_mode=step persists only Goal into draft-<slug>.md."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    with patch_step_roots(tmp_path):
        raw = await plan(
            operation="create",
            title="Demo Plan",
            content=_sample_plan_markdown(),
            slug="demo-step-plan",
            planning_mode="step",
        )
    result = json.loads(raw)
    assert result["status"] == "success"
    draft = plans / "draft-demo-step-plan.md"
    assert draft.is_file()
    text = draft.read_text(encoding="utf-8")
    assert "## Goal" in text
    assert "Build planning modes" in text
    assert "## Context" not in text
    assert result.get("planning_mode") == "step"
    assert result.get("review_prompt")


@pytest.mark.asyncio
async def test_continue_step_requires_prior_approval(tmp_path: Path) -> None:
    """continue_step is rejected while the current section remains draft."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="create",
            title="Demo Plan",
            content=_sample_plan_markdown(),
            slug="block-continue",
            planning_mode="step",
        )
        raw = await plan(
            operation="continue_step",
            slug="block-continue",
            content="Should not land yet.",
        )
    err = json.loads(raw)
    assert err["status"] == "error"
    assert "approve" in (err.get("message") or "").lower()


async def _create_mini_step_plan(tmp_path: Path, slug: str) -> None:
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="create",
            title="Mini",
            content=_sample_plan_markdown(),
            slug=slug,
            planning_mode="step",
        )
        _ = await plan(
            operation="approve_step",
            slug=slug,
            step_section="goal",
        )


async def _continue_and_approve_section(
    tmp_path: Path, slug: str, section_key: str
) -> None:
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="continue_step",
            slug=slug,
            content=f"Body for {section_key}.",
        )
        _ = await plan(
            operation="approve_step",
            slug=slug,
            step_section=section_key,
        )


async def _fill_plan_for_finalize(tmp_path: Path, slug: str) -> None:
    await _create_mini_step_plan(tmp_path, slug)
    for key in ("context", "implementation_steps", "verification", "testing"):
        await _continue_and_approve_section(tmp_path, slug, key)


def _write_minimal_roadmap(tmp_path: Path) -> None:
    memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank.mkdir(parents=True)
    roadmap = memory_bank / "roadmap.md"
    _ = roadmap.write_text(
        "# Roadmap\n\n## Pending plans (from .cortex/plans)\n- **Other** - PENDING\n",
        encoding="utf-8",
    )


async def _invoke_finalize_step(
    tmp_path: Path, slug: str
) -> tuple[dict[str, object], AsyncMock]:
    with (
        patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.plans.register.register_plan_in_roadmap",
            new_callable=AsyncMock,
        ) as mock_reg,
    ):
        mock_reg.return_value = json.dumps(
            {"status": "success", "file_name": "roadmap.md"}
        )
        with patch_step_roots(tmp_path):
            raw = await plan(
                operation="finalize_step",
                slug=slug,
                plan_title="Mini Plan",
                description="Roadmap entry",
                status="PENDING",
                section="pending",
            )
    return cast(dict[str, object], json.loads(raw)), mock_reg


async def _create_and_approve_goal(tmp_path: Path, slug: str) -> None:
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="create",
            title="Demo Plan",
            content=_sample_plan_markdown(),
            slug=slug,
            planning_mode="step",
        )
        _ = await plan(
            operation="approve_step",
            slug=slug,
            step_section="goal",
        )


@pytest.mark.asyncio
async def test_continue_step_after_approve_appends_next_section(
    tmp_path: Path,
) -> None:
    """After approving Goal, continue_step drafts Context."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    await _create_and_approve_goal(tmp_path, "flow-ctx")
    with patch_step_roots(tmp_path):
        raw = await plan(
            operation="continue_step",
            slug="flow-ctx",
            content="Context body from agent.",
        )
    ok = json.loads(raw)
    assert ok["status"] == "success"
    assert ok.get("section_key") == "context"
    text = (plans / "draft-flow-ctx.md").read_text(encoding="utf-8")
    assert "## Context" in text and "Context body from agent." in text


@pytest.mark.asyncio
async def test_finalize_step_publishes_and_calls_register(
    tmp_path: Path,
) -> None:
    """finalize_step writes final plan, removes draft, and invokes register."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    _write_minimal_roadmap(tmp_path)
    slug = "mini-finalize"
    await _fill_plan_for_finalize(tmp_path, slug)
    fin, mock_reg = await _invoke_finalize_step(tmp_path, slug)
    assert fin["status"] == "success"
    assert (plans / f"{slug}.md").is_file()
    assert not (plans / f"draft-{slug}.md").exists()
    mock_reg.assert_awaited()


@pytest.mark.asyncio
async def test_approve_step_with_corrections_keeps_draft_status(
    tmp_path: Path,
) -> None:
    """Passing corrections to approve_step revises the section body but stays draft."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="create",
            title="Demo Plan",
            content=_sample_plan_markdown(),
            slug="corrections-plan",
            planning_mode="step",
        )
        raw = await plan(
            operation="approve_step",
            slug="corrections-plan",
            step_section="goal",
            section_corrections="Revised goal body.",
        )
    result = json.loads(raw)
    assert result["status"] == "success"
    assert result.get("section_key") == "goal"
    text = (plans / "draft-corrections-plan.md").read_text(encoding="utf-8")
    assert "Revised goal body." in text
    # Section must still be draft (not approved) so the cycle can continue
    from cortex.core.models import PlanSectionStatus
    from cortex.tools.plans.step_draft_core import parse_step_draft_file

    parsed = parse_step_draft_file(text)
    assert parsed is not None
    goal_rec = next(r for r in parsed.records if r.key == "goal")
    assert goal_rec.status == PlanSectionStatus.DRAFT


@pytest.mark.asyncio
async def test_approve_step_skip_marks_section_skipped(
    tmp_path: Path,
) -> None:
    """step_skip=True transitions a pending/draft section to skipped."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    with patch_step_roots(tmp_path):
        _ = await plan(
            operation="create",
            title="Demo Plan",
            content=_sample_plan_markdown(),
            slug="skip-plan",
            planning_mode="step",
        )
        raw = await plan(
            operation="approve_step",
            slug="skip-plan",
            step_section="goal",
            step_skip=True,
        )
    result = json.loads(raw)
    assert result["status"] == "success"
    assert result.get("section_key") == "goal"
    from cortex.core.models import PlanSectionStatus
    from cortex.tools.plans.step_draft_core import parse_step_draft_file

    text = (plans / "draft-skip-plan.md").read_text(encoding="utf-8")
    parsed = parse_step_draft_file(text)
    assert parsed is not None
    goal_rec = next(r for r in parsed.records if r.key == "goal")
    assert goal_rec.status == PlanSectionStatus.SKIPPED


@pytest.mark.asyncio
async def test_continue_step_no_pending_sections_returns_error(
    tmp_path: Path,
) -> None:
    """continue_step returns error when all sections are already approved/skipped."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    await _fill_plan_for_finalize(tmp_path, "no-pending")
    with patch_step_roots(tmp_path):
        raw = await plan(
            operation="continue_step",
            slug="no-pending",
            content="Should not land.",
        )
    err = json.loads(raw)
    assert err["status"] == "error"
    assert "pending" in (err.get("message") or "").lower()


@pytest.mark.asyncio
async def test_finalize_step_errors_when_sections_incomplete(
    tmp_path: Path,
) -> None:
    """finalize_step returns error when sections are not all approved/skipped."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    await _create_and_approve_goal(tmp_path, "incomplete-finalize")
    with patch_step_roots(tmp_path):
        raw = await plan(
            operation="finalize_step",
            slug="incomplete-finalize",
            plan_title="Incomplete Plan",
            description="Should fail",
        )
    err = json.loads(raw)
    assert err["status"] == "error"
    assert "approved or skipped" in (err.get("message") or "").lower()
