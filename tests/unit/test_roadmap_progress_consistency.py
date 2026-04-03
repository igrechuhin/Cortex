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


def test_partial_with_matching_pending_passes() -> None:
    """PARTIAL progress with a matching PENDING roadmap entry passes."""
    progress = "- **Big task** - PARTIAL. More work."
    roadmap = "- **Big task** - PENDING - Do the thing. Plan: `.cortex/plans/x.md`"
    assert check_roadmap_progress_consistency(progress, roadmap) == []


def test_partial_with_em_dash_pending_passes() -> None:
    """Roadmap PENDING lines may use typographic dashes (memory-bank style)."""
    progress = "- **Big task** - PARTIAL. More work."
    roadmap = "- **Big task** — PENDING — `.cortex/plans/x.md`"
    assert check_roadmap_progress_consistency(progress, roadmap) == []


def test_partial_with_unrelated_pending_fails() -> None:
    """PARTIAL progress with an unrelated PENDING entry produces a violation."""
    progress = "- **Auth System** - PARTIAL. Work remaining."
    roadmap = "- **Logging Refactor** - PENDING - unrelated."
    violations = check_roadmap_progress_consistency(progress, roadmap)
    assert len(violations) == 1
    assert "Auth System" in violations[0]
    assert "PARTIAL" in violations[0]
    assert "PENDING" in violations[0]


def test_partial_without_pending_fails() -> None:
    """PARTIAL progress and no PENDING roadmap lines returns a violation per title."""
    progress = "- **Big task** - PARTIAL. More work."
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 1
    assert "Big task" in violations[0]
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
    """A different unresolved PARTIAL title still requires a matching roadmap entry."""
    progress = (
        "- **Big task** - PARTIAL. Started.\n"
        "- **Big task** - COMPLETE. Done.\n"
        "- **Other task** - PARTIAL. Still open.\n"
    )
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 1
    assert "Other task" in violations[0]


def test_multiple_unresolved_partials_produce_per_title_violations() -> None:
    """Each orphaned PARTIAL title gets its own violation message."""
    progress = (
        "- **Feature A** - PARTIAL. In progress.\n"
        "- **Feature B** - PARTIAL. Also open.\n"
    )
    violations = check_roadmap_progress_consistency(
        progress, "# Roadmap\n\n(no items)\n"
    )
    assert len(violations) == 2
    titles_mentioned = {v for v in violations if "Feature A" in v or "Feature B" in v}
    assert len(titles_mentioned) == 2


def test_partial_with_substring_match_in_pending_passes() -> None:
    """Case-insensitive substring match between PARTIAL and PENDING titles passes."""
    progress = "- **Auth System Refactor** - PARTIAL. Half done."
    roadmap = "- **auth system** - PENDING - finish it."
    assert check_roadmap_progress_consistency(progress, roadmap) == []


def test_empty_progress_passes() -> None:
    """Empty progress.md produces no violations."""
    assert check_roadmap_progress_consistency("", "- **Task** - PENDING") == []
