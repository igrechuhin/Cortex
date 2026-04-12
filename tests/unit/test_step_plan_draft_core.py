"""Unit tests for step plan draft parsing and rendering."""

from __future__ import annotations

from cortex.core.models import PlanSectionStatus
from cortex.tools.plans.step_draft_core import (
    canonical_section_key,
    extract_goal_markdown,
    initial_section_records,
    parse_step_draft_file,
    render_published_plan,
    render_step_draft_file,
)


def test_initial_section_records_orders_goal_draft() -> None:
    recs = initial_section_records()
    assert recs[0].key == "goal"
    assert recs[0].status == PlanSectionStatus.DRAFT
    assert recs[1].status == PlanSectionStatus.PENDING


def test_extract_goal_from_full_markdown() -> None:
    md = """---
title: T
---
## Goal

Ship it.

## Context

Later.
"""
    assert extract_goal_markdown(md) == "Ship it."


def test_parse_render_roundtrip_preserves_state() -> None:
    fm = "---\ntitle: X\n---\n"
    bodies = {"goal": "G1"}
    recs = initial_section_records()
    raw = render_step_draft_file(fm, bodies, recs)
    parsed = parse_step_draft_file(raw)
    assert parsed is not None
    assert parsed.frontmatter is not None
    assert "title: X" in parsed.frontmatter
    assert parsed.bodies.get("goal") == "G1"
    assert len(parsed.records) == 5


def test_render_published_plan_omits_footer() -> None:
    text = render_published_plan(
        "---\ntitle: Z\n---\n",
        {"goal": "only"},
    )
    assert "CORTEX_STEP_PLAN_STATE" not in text
    assert "## Goal" in text


def test_canonical_section_key_accepts_heading_labels() -> None:
    assert canonical_section_key("Goal") == "goal"
    assert canonical_section_key("implementation_steps") == "implementation_steps"
    assert canonical_section_key("Verification Checklist") == "verification"
