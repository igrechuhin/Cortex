"""Tests for plan create-time Clarifications Needed section injection."""

from __future__ import annotations

from cortex.core.plan_utils import apply_clarifications_summary_to_plan


def test_no_markers_leaves_body_unchanged_modulo_strip() -> None:
    body = "## Goal\n\nPlain text.\n\n## Context\n\nMore.\n"
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 0
    assert out == body


def test_inserts_summary_before_context_when_present() -> None:
    body = "## Goal\n\nShip [NEEDS CLARIFICATION: pick SLA].\n\n## Context\n\nWhy.\n"
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 1
    assert "## Clarifications Needed" in out
    assert out.index("## Clarifications Needed") < out.index("## Context")
    assert "pick SLA" in out
    assert "line 3" in out


def test_inserts_after_goal_when_no_context() -> None:
    body = (
        "## Goal\n\n"
        "Fix [NEEDS CLARIFICATION: scope].\n\n"
        "## Implementation\n\n"
        "Details.\n"
    )
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 1
    g_end = out.index("## Implementation")
    c_pos = out.index("## Clarifications Needed")
    assert c_pos < g_end


def test_blocking_marker_prefixed_in_summary() -> None:
    body = "[NEEDS CLARIFICATION(blocking): API contract]\n"
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 1
    assert "(blocking)" in out
    assert "API contract" in out


def test_replaces_stale_clarifications_section() -> None:
    body = (
        "## Goal\n\n"
        "A [NEEDS CLARIFICATION: one].\n\n"
        "## Clarifications Needed\n\n"
        "- stale\n\n"
        "## Context\n\n"
        "B.\n"
    )
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 1
    assert out.count("## Clarifications Needed") == 1
    assert "stale" not in out
    assert "one" in out


def test_yaml_front_matter_insert_when_no_goal_or_context() -> None:
    body = """---
title: T
---

Intro [NEEDS CLARIFICATION: reason text].
"""
    out, n = apply_clarifications_summary_to_plan(body)
    assert n == 1
    assert out.index("## Clarifications Needed") > out.index("---\n", 1)
