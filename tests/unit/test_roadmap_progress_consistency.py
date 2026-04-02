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
    """PARTIAL progress and no PENDING roadmap lines returns warning guidance."""
    progress = "- **Big task** - PARTIAL. More work."
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 1
    assert "PARTIAL" in violations[0]
    assert "PENDING" in violations[0]
    assert "do not fabricate placeholder backlog" in violations[0]


def test_partial_with_matching_complete_no_pending_passes() -> None:
    """Historical PARTIAL rows are ignored when same title is COMPLETE."""
    progress = (
        "- **Big task** - PARTIAL. Started.\n" "- **Big task** - COMPLETE. Done.\n"
    )
    assert (
        check_roadmap_progress_consistency(progress, "# Roadmap\n\n(no items)\n") == []
    )


def test_unresolved_partial_without_pending_still_fails() -> None:
    """A different unresolved PARTIAL title still requires roadmap backlog."""
    progress = (
        "- **Big task** - PARTIAL. Started.\n"
        "- **Big task** - COMPLETE. Done.\n"
        "- **Other task** - PARTIAL. Still open.\n"
    )
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 1
    assert "unresolved PARTIAL" in violations[0]
    assert "review whether those PARTIAL rows" in violations[0]
