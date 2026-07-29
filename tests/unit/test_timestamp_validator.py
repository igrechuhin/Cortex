"""Unit tests for cortex.validation.timestamp_validator."""

from unittest.mock import patch

from cortex.validation.timestamp_validator import scan_timestamps


class TestScanTimestamps:
    """Tests for scan_timestamps()."""

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
        assert result.invalid_with_time_count >= 1 or len(result.violations) >= 1

    def test_invalid_datetime_with_timezone_adds_violation(self) -> None:
        """A line with timezone (Z or +00:00) is invalid."""
        result = scan_timestamps("Done 2026-01-15T10:00Z")
        assert result.invalid_with_time_count >= 1 or len(result.violations) >= 1

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
        ):
            result = scan_timestamps(line)
            assert result.invalid_format_count == 0, line
            assert result.violations == [], line

    def test_year_outside_current_plus_minus_one_adds_violation(self) -> None:
        """A date with year outside current year ± 1 is invalid (catches typos)."""
        from datetime import date as date_type

        with patch("cortex.validation.timestamp_validator.date") as mock_date:
            mock_date.today.return_value = date_type(2026, 3, 4)
            result = scan_timestamps("Completed 2024-01-15")
        assert result.invalid_year_count >= 1
        assert any("outside allowed range" in v.issue for v in result.violations)
