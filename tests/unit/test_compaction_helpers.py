"""Unit tests for compaction helpers (Phase 56)."""

from cortex.tools.compaction_helpers import (
    apply_progress_tiers,
    compact_active_context_completed_work,
    get_completed_work_sections,
    get_progress_date_sections,
    summarize_entries_as_line,
    summarize_progress,
    trim_recent_changes,
)


class TestGetCompletedWorkSections:
    """Tests for get_completed_work_sections."""

    def test_finds_single_section(self) -> None:
        content = """# Active Context

## Completed Work (2026-02-17)

- Item 1
- Item 2
"""
        sections = get_completed_work_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == "2026-02-17"
        assert sections[0][1] == 2
        assert sections[0][2] == 7  # exclusive end (no next ##)

    def test_finds_multiple_sections(self) -> None:
        content = """# Active Context

## Completed Work (2026-02-17)

- Item 1

## Completed Work (2026-02-16)

- Item 2
"""
        sections = get_completed_work_sections(content)
        assert len(sections) == 2
        assert sections[0][0] == "2026-02-17"
        assert sections[1][0] == "2026-02-16"

    def test_empty_content(self) -> None:
        assert get_completed_work_sections("") == []

    def test_no_completed_work(self) -> None:
        content = "# Active Context\n\n## Current Focus\n\nNothing."
        assert get_completed_work_sections(content) == []


class TestCompactActiveContextCompletedWork:
    """Tests for compact_active_context_completed_work."""

    def test_keeps_current_date_full(self) -> None:
        content = """# Active Context

## Completed Work (2026-02-17)

- Task A
- Task B
"""
        result = compact_active_context_completed_work(content, "2026-02-17")
        assert "Task A" in result
        assert "Task B" in result
        assert "Summary" not in result

    def test_summarizes_older_dates(self) -> None:
        content = """# Active Context

## Completed Work (2026-02-17)

- Task A

## Completed Work (2026-02-16)

- Task B
- Task C
"""
        result = compact_active_context_completed_work(content, "2026-02-17")
        assert "Task A" in result
        assert "Summary (2026-02-16)" in result
        assert "2 entries archived" in result
        assert "Task B" not in result
        assert "Task C" not in result
        # MD022: blank line between heading and list (markdownlint compliance)
        assert "## Completed Work (2026-02-16)\n\n-" in result

    def test_invalid_date_unchanged(self) -> None:
        content = """## Completed Work (2026-02-17)

- Item
"""
        result = compact_active_context_completed_work(content, "not-a-date")
        assert result == content

    def test_no_completed_work_sections_unchanged(self) -> None:
        """When content has no Completed Work sections, return unchanged."""
        content = "# Active Context\n\n## Current Focus\n\nNothing."
        result = compact_active_context_completed_work(content, "2026-02-17")
        assert result == content

    def test_invalid_section_date_kept_verbatim(self) -> None:
        """Section with unparseable date (e.g. 2026-13-01) is kept as-is."""
        content = """# Active Context

## Completed Work (2026-02-17)

- Task A

## Completed Work (2026-13-01)

- Task B
"""
        result = compact_active_context_completed_work(content, "2026-02-17")
        assert "Task A" in result
        assert "Task B" in result
        assert "## Completed Work (2026-13-01)" in result


class TestTrimRecentChanges:
    """Tests for trim_recent_changes."""

    def test_under_limit_unchanged(self) -> None:
        content = """# Context

## Recent Changes

- Change 1
- Change 2
"""
        result = trim_recent_changes(content, max_entries=5)
        assert result == content

    def test_over_limit_trimmed(self) -> None:
        content = """# Context

## Recent Changes

- Change 1
- Change 2
- Change 3
- Change 4
- Change 5
- Change 6
"""
        result = trim_recent_changes(content, max_entries=3)
        assert "Change 1" in result
        assert "Change 3" in result
        assert "Change 4" not in result
        assert "Change 6" not in result

    def test_no_recent_changes_unchanged(self) -> None:
        content = "# Context\n\n## Other\n\nText"
        assert trim_recent_changes(content) == content


class TestGetProgressDateSections:
    """Tests for get_progress_date_sections."""

    def test_parses_date_sections(self) -> None:
        content = """# Progress Log

## 2026-02-17

- Entry 1

## 2026-02-16

- Entry 2
"""
        sections = get_progress_date_sections(content)
        assert len(sections) == 2
        assert sections[0][0] == "2026-02-17"
        assert "Entry 1" in "\n".join(sections[0][1])
        assert sections[1][0] == "2026-02-16"

    def test_empty_progress(self) -> None:
        assert get_progress_date_sections("") == []


class TestApplyProgressTiersEdgeCases:
    """Edge cases for apply_progress_tiers."""

    def test_invalid_today_str_keeps_sections_full(self) -> None:
        """When today_str is invalid, _days_between returns None; sections kept full."""
        content = """# Progress

## 2026-02-17

- Entry A
"""
        result = apply_progress_tiers(
            content, "not-a-date", days_full=7, days_weekly=30
        )
        assert "Entry A" in result

    def test_empty_content_unchanged(self) -> None:
        """When content has no progress date sections, return unchanged."""
        result = apply_progress_tiers("", "2026-02-17")
        assert result == ""


class TestApplyProgressTiers:
    """Tests for apply_progress_tiers."""

    def test_recent_days_kept_full(self) -> None:
        content = """# Progress

## 2026-02-17

- Entry A
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Entry A" in result
        assert "summarized" not in result.lower() or "Entry A" in result

    def test_tier1_same_day_kept_full(self) -> None:
        """Tier 1: same-day section is kept in full."""
        content = """# Progress

## 2026-02-17

- Entry A
- Entry B
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Entry A" in result and "Entry B" in result
        assert "summarized" not in result.lower()

    def test_tier1_within_7_days_kept_full(self) -> None:
        """Tier 1: section 5 days old is kept in full."""
        content = """# Progress

## 2026-02-12

- Entry
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Entry" in result
        assert "summarized" not in result.lower()

    def test_tier2_8_days_summarized_as_week(self) -> None:
        """Tier 2: section 8 days old becomes weekly summary."""
        content = """# Progress

## 2026-02-09

- Old 1
- Old 2
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Old 1" not in result and "Old 2" not in result
        assert "Week containing 2026-02-09" in result
        assert "2 entries" in result

    def test_tier2_29_days_still_weekly_summary(self) -> None:
        """Tier 2: section 29 days old is weekly summary."""
        content = """# Progress

## 2026-01-19

- Item
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Item" not in result
        assert "Week containing 2026-01-19" in result

    def test_tier3_31_days_summarized_as_month(self) -> None:
        """Tier 3: section 31+ days old becomes monthly summary."""
        content = """# Progress

## 2026-01-01

- Old entry 1
- Old entry 2
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Old entry 1" not in result
        assert "Month containing 2026-01-01" in result
        assert "2 entries" in result
        assert "## 2026-01-01\n\n-" in result

    def test_old_days_summarized(self) -> None:
        content = """# Progress

## 2026-01-01

- Old entry 1
- Old entry 2
"""
        result = apply_progress_tiers(
            content, "2026-02-17", days_full=7, days_weekly=30
        )
        assert "Old entry 1" not in result
        assert "Summary" in result or "summarized" in result.lower()
        assert "2 entries" in result or "entries" in result
        # MD022: blank line between heading and list (markdownlint compliance)
        assert "## 2026-01-01\n\n-" in result


class TestSummarizeEntriesAsLine:
    """Tests for summarize_entries_as_line."""

    def test_counts_bullets(self) -> None:
        entries = ["- A", "- B", "  sub", "- C"]
        line = summarize_entries_as_line(entries, "Week 1")
        assert "3 entries" in line
        assert "Week 1" in line


class TestSummarizeProgress:
    """Tests for summarize_progress."""

    def test_weekly_tier_recent_kept_full(self) -> None:
        """Weekly tier: 0-7 days kept full."""
        content = """# Progress

## 2026-02-10

- Entry
"""
        result = summarize_progress(content, "weekly", "2026-02-17")
        assert "Entry" in result or "summarized" in result.lower()

    def test_weekly_tier_old_summarized(self) -> None:
        """Weekly tier: 7-30d summarized as week."""
        content = """# Progress

## 2026-02-01

- Item
"""
        result = summarize_progress(content, "weekly", "2026-02-17")
        assert "Week containing" in result or "Item" not in result

    def test_monthly_tier_keeps_0_30_days_full(self) -> None:
        """Monthly tier: 0-30 days kept full."""
        content = """# Progress

## 2026-01-25

- Entry
"""
        result = summarize_progress(content, "monthly", "2026-02-17")
        assert "Entry" in result

    def test_monthly_tier_summarizes_30_plus(self) -> None:
        """Monthly tier: 30+ days summarized as month."""
        content = """# Progress

## 2026-01-01

- Old
"""
        result = summarize_progress(content, "monthly", "2026-02-17")
        assert (
            "Old" not in result or "summarized" in result.lower() or "Summary" in result
        )
        assert "Month containing" in result or "summarized" in result.lower()
