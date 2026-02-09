"""Unit tests for cortex.validation.timestamp_validator."""

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
