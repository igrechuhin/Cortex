"""Unit tests for roadmap vs progress.md backlog consistency invariant."""

from __future__ import annotations

from cortex.validation.roadmap_progress_consistency import (
    check_roadmap_progress_consistency,
)


def test_no_partial_any_roadmap_passes() -> None:
    """No PARTIAL lines: invariant does not apply."""
    assert (
        check_roadmap_progress_consistency("## Log\n\n- **Done** - COMPLETE.", "") == []
    )


def test_partial_with_pending_passes() -> None:
    """PARTIAL progress with at least one PENDING roadmap line passes."""
    progress = "- **Big task** - PARTIAL. More work."
    roadmap = "- **Big task** - PENDING - Do the thing. Plan: `.cortex/plans/x.md`"
    assert check_roadmap_progress_consistency(progress, roadmap) == []


def test_partial_without_pending_fails() -> None:
    """PARTIAL progress and no PENDING roadmap lines fails with a clear message."""
    progress = "- **Big task** - PARTIAL. More work."
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 1
    assert "PARTIAL" in violations[0]
    assert "PENDING" in violations[0]
