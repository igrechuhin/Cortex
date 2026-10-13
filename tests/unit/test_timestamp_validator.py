"""Unit tests for cortex.validation.timestamp_validator."""

from unittest.mock import patch

import pytest

from cortex.validation.timestamp_validator import scan_timestamps


class TestScanTimestamps:
    """Tests for scan_timestamps()."""

    @pytest.mark.parametrize("counts", ("21/34/43", "22/33/41", "40-50-60"))
    def test_inventory_counts_are_not_dates(self, counts: str) -> None:
        """Numeric triplets without calendar components are not date citations."""
        result = scan_timestamps(f"Graph inventory ({counts}) confirms selection.")
        assert result.valid_count == 0
        assert result.invalid_format_count == 0
        assert result.violations == []

    @pytest.mark.parametrize(
        "timestamp",
        (
            "31/12/2024",
            "12/31/24",
            "31-12-24",
            "99/99/2026",
            "31/13/26",
            "32/12/26",
            "00/00/26",
            "30/02/2026",
            "123-12-31",
        ),
    )
    def test_non_standard_date_citations_remain_violations(
        self, timestamp: str
    ) -> None:
        """Date recognition retains unsupported and malformed calendar dates."""
        result = scan_timestamps(f"Evidence cites ({timestamp}).")
        assert result.invalid_format_count == 1
        assert [v.timestamp for v in result.violations] == [timestamp]

    def test_accepts_date_only_line(self) -> None:
        """A line with only YYYY-MM-DD is valid and counted."""
        result = scan_timestamps("2026-01-20")
        assert result.valid_count >= 1
        assert result.invalid_format_count == 0
        assert len(result.violations) == 0

    def test_accepts_datetime_line(self) -> None:
        """A line with YYYY-MM-DDTHH:MM is valid and counted."""
        result = scan_timestamps("Completed 2026-01-15T10:00")
        assert result.valid_count >= 1
        assert len(result.violations) == 0

    def test_invalid_datetime_with_seconds_adds_violation(self) -> None:
        """A line with YYYY-MM-DDTHH:MM:SS is invalid (seconds not allowed)."""
        result = scan_timestamps("Done 2026-01-15T10:00:00")
        assert len(result.violations) >= 1

    def test_invalid_datetime_with_timezone_adds_violation(self) -> None:
        """A line with timezone (Z or +00:00) is invalid."""
        result = scan_timestamps("Done 2026-01-15T10:00Z")
        assert len(result.violations) >= 1

    def test_non_standard_date_format_adds_violation(self) -> None:
        """A line with non-YYYY-MM-DD date format (e.g. DD/MM/YYYY) is invalid."""
        result = scan_timestamps("Updated 31/12/2024")
        assert result.invalid_format_count >= 1 or len(result.violations) >= 1

    def test_date_like_substring_of_identifier_is_not_a_violation(self) -> None:
        """Run pointers and log filenames must not be read as malformed dates.

        Regression: the pattern used \\b, and "-" satisfies \\b, so every
        hyphen-joined identifier containing digits produced phantom violations.
        """
        for line in (
            "Run pointer `26-07-09-17-42-55-sprint2`, running on M1 Max",
            "See .cortex/.session/logs/swift-test-2026-07-25-16-17-51.log:19623",
            "Committed over 2026-07-13/14",
            "Run pointer `run-31/12/24`; log `31-12-24-result`",
        ):
            result = scan_timestamps(line)
            assert result.invalid_format_count == 0, line
            assert result.violations == [], line

    def test_year_outside_current_plus_minus_one_adds_violation(self) -> None:
        """An entry-opening date with year outside current ± 1 is a likely typo."""
        from datetime import date as date_type

        with patch("cortex.validation.timestamp_validator.date") as mock_date:
            mock_date.today.return_value = date_type(2026, 3, 4)
            result = scan_timestamps("2024-01-15 Completed")
        assert result.invalid_year_count >= 1
        assert any("outside allowed range" in v.issue for v in result.violations)

    def test_real_memory_bank_timestamp_forms_are_checked(self) -> None:
        """Every work-timestamp convention the memory bank actually uses.

        Measured over TradeWing + Cortex memory banks: date-opened headings,
        emoji-decorated list entries, and the trailing "(date)" parenthetical
        used by "## Completed Work (...)" and "- ✅ **Plan** - COMPLETE (...)".
        A scope rule that misses these stops catching typos where work
        timestamps actually live.
        """
        from datetime import date as date_type

        for line in (
            "## 2024-01-15",
            "- **2024-01-15 — Sprint closed**",
            "- ✅ **2024-01-15 — Sprint closed**",
            "## Completed Work (2024-01-15)",
            "- ✅ **Replay Trades** - COMPLETE (2024-01-15) - closed gaps",
        ):
            with patch("cortex.validation.timestamp_validator.date") as mock_date:
                mock_date.today.return_value = date_type(2026, 3, 4)
                result = scan_timestamps(line)
            assert result.invalid_year_count >= 1, line

    def test_historical_date_cited_in_prose_is_not_a_violation(self) -> None:
        """Prose citing a past event is not a mistyped work timestamp.

        Regression: the year check scanned every date on every line, so real
        memory-bank sentences about 2018-2021 market data produced 12 phantom
        violations and held the docs gate permanently red.
        """
        from datetime import date as date_type

        with patch("cortex.validation.timestamp_validator.date") as mock_date:
            mock_date.today.return_value = date_type(2026, 3, 4)
            for line in (
                "**Dead Candle Series: Pairs Stopped 2018-03-21 / 2019-09-05**",
                "Baseline run started 2020-08-19 on the M1.",
                "Fifteen FIGIs trail from 2018-03-21 to 2019-09-05.",
                "The data window (2018-03-21) was sampled hourly.",
                "Backtest covered (2019-01-01) through (2020-12-31).",
            ):
                result = scan_timestamps(line)
                assert result.invalid_year_count == 0, line
                assert result.violations == [], line
