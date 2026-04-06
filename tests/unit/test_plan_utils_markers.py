"""Tests for plan clarification marker parsing."""

from __future__ import annotations

from cortex.core.plan_utils import find_clarification_markers


def test_find_zero_markers() -> None:
    assert find_clarification_markers("No markers here.") == []


def test_find_one_non_blocking_marker() -> None:
    text = "Do [NEEDS CLARIFICATION: pick a timeout] before shipping."
    markers = find_clarification_markers(text)
    assert len(markers) == 1
    m = markers[0]
    assert m.reason == "pick a timeout"
    assert m.blocking is False
    assert m.resolved is False
    assert "line 1" in m.location


def test_find_blocking_marker() -> None:
    text = "[NEEDS CLARIFICATION(blocking): confirm API contract]"
    markers = find_clarification_markers(text)
    assert len(markers) == 1
    assert markers[0].blocking is True
    assert markers[0].reason == "confirm API contract"


def test_find_multiple_markers() -> None:
    text = """# Plan
- Step [NEEDS CLARIFICATION: first unknown]
- More [NEEDS CLARIFICATION(blocking): second unknown]
"""
    markers = find_clarification_markers(text)
    assert len(markers) == 2
    assert markers[0].reason == "first unknown"
    assert markers[0].blocking is False
    assert markers[1].blocking is True
    assert markers[1].reason == "second unknown"


def test_skips_markers_inside_fenced_code_block() -> None:
    text = """Intro
```
[NEEDS CLARIFICATION: ignore me]
```
Real [NEEDS CLARIFICATION: keep me]
"""
    markers = find_clarification_markers(text)
    assert len(markers) == 1
    assert markers[0].reason == "keep me"


def test_skips_empty_reason() -> None:
    text = "[NEEDS CLARIFICATION: ] and [NEEDS CLARIFICATION: valid]"
    markers = find_clarification_markers(text)
    assert len(markers) == 1
    assert markers[0].reason == "valid"
