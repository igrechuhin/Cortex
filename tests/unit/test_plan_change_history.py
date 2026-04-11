"""Tests for plan change history and ``PlanDelta`` computation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cortex.core.models import PlanDelta
from cortex.core.plan_change_history import (
    CHANGE_HISTORY_HEADING,
    IMPLEMENTATION_STEPS_HEADING,
    append_change_history_entry,
    change_history_stats,
    compute_plan_delta,
    ensure_change_history_section,
    extract_markdown_section,
    last_change_context_line,
    parse_implementation_blocks,
    render_plan_delta_markdown,
)


def _steps_doc(steps_body: str) -> str:
    return f"""---
title: T
status: PENDING
---

{IMPLEMENTATION_STEPS_HEADING}

{steps_body}
"""


def test_parse_implementation_blocks_splits_headers() -> None:
    sec = "### A\nbody a\n\n### B\nbody b"
    got = parse_implementation_blocks(sec)
    assert got["### A"] == "body a"
    assert got["### B"] == "body b"


def test_compute_plan_delta_detects_added() -> None:
    old = _steps_doc("### Step 1\nx")
    new = _steps_doc("### Step 1\nx\n\n### Step 2\ny")
    d = compute_plan_delta(old, new, author="tester", reason="r")
    assert d is not None
    assert d.added == ["### Step 2"]
    assert d.removed == []
    assert d.modified == []
    assert d.renamed == []


def test_compute_plan_delta_detects_removed() -> None:
    old = _steps_doc("### Step 1\nx\n\n### Step 2\ny")
    new = _steps_doc("### Step 1\nx")
    d = compute_plan_delta(old, new, author="a", reason="r")
    assert d is not None
    assert d.removed == ["### Step 2"]


def test_compute_plan_delta_detects_modified() -> None:
    old = _steps_doc("### Step 1\nold")
    new = _steps_doc("### Step 1\nnew")
    d = compute_plan_delta(old, new, author="a", reason="r")
    assert d is not None
    assert d.modified and "### Step 1" in d.modified[0]


def test_compute_plan_delta_detects_renamed_same_body() -> None:
    old = _steps_doc("### Step A\nsame body")
    new = _steps_doc("### Step B\nsame body")
    d = compute_plan_delta(old, new, author="a", reason="r")
    assert d is not None
    assert d.renamed == ["### Step A → ### Step B"]
    assert d.added == []
    assert d.removed == []


def test_compute_plan_delta_none_when_steps_unchanged() -> None:
    body = "### Step 1\nx"
    d = compute_plan_delta(_steps_doc(body), _steps_doc(body), author="a", reason="r")
    assert d is None


def test_render_order_renamed_before_added() -> None:
    delta = PlanDelta(
        timestamp=datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
        author="agent",
        renamed=["### A → ### B"],
        removed=["### Z"],
        modified=["### M"],
        added=["### N"],
        reason="because",
    )
    md = render_plan_delta_markdown(delta)
    assert md.index("**RENAMED**") < md.index("**REMOVED**")
    assert md.index("**REMOVED**") < md.index("**MODIFIED**")
    assert md.index("**MODIFIED**") < md.index("**ADDED**")
    assert "**Reason**" in md
    assert "because" in md


def test_append_change_history_idempotent() -> None:
    delta = PlanDelta(
        timestamp=datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
        author="agent",
        renamed=[],
        removed=["### X"],
        modified=[],
        added=[],
        reason="r",
    )
    entry = render_plan_delta_markdown(delta)
    base = ensure_change_history_section("# T\n")
    once = append_change_history_entry(base, entry)
    twice = append_change_history_entry(once, entry)
    assert twice == once


def test_change_history_stats_counts_entries() -> None:
    d1 = PlanDelta(
        timestamp=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
        author="u",
        renamed=[],
        removed=["a"],
        modified=[],
        added=[],
        reason="one",
    )
    d2 = PlanDelta(
        timestamp=datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
        author="u",
        renamed=[],
        removed=[],
        modified=[],
        added=["b"],
        reason="two",
    )
    text = ensure_change_history_section("# x\n")
    text = append_change_history_entry(text, render_plan_delta_markdown(d1))
    text = append_change_history_entry(text, render_plan_delta_markdown(d2))
    count, latest = change_history_stats(text)
    assert count == 2
    assert latest is not None
    assert "2026-04-02" in latest


def test_last_change_context_line() -> None:
    d = PlanDelta(
        timestamp=datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
        author="u",
        renamed=[],
        removed=[],
        modified=[],
        added=["z"],
        reason="why",
    )
    text = append_change_history_entry(
        ensure_change_history_section("#\n"), render_plan_delta_markdown(d)
    )
    line = last_change_context_line(text)
    assert line is not None
    assert line.startswith("[LAST CHANGE:")
    assert "2026-04-02" in line


def test_extract_markdown_section_finds_change_history() -> None:
    doc = f"# T\n\n{CHANGE_HISTORY_HEADING}\n\nHello\n\n## Other\nx"
    sec = extract_markdown_section(doc, CHANGE_HISTORY_HEADING)
    assert sec == "Hello"


def test_plan_delta_rejects_missing_reason() -> None:
    with pytest.raises(ValidationError):
        _ = PlanDelta.model_validate(
            {
                "timestamp": datetime.now(timezone.utc),
                "author": "a",
            }
        )
