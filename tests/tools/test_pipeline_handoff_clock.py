"""Unit tests for UTC-aware pipeline_handoff timestamp helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cortex.tools.session.pipeline_handoff_clock import (
    age_seconds,
    ensure_aware,
    now_iso,
    parse_iso,
)


class TestNowIso:
    def test_returns_timezone_aware_iso_string(self) -> None:
        # Act
        raw = now_iso()

        # Assert
        parsed = datetime.fromisoformat(raw)
        assert parsed.tzinfo is not None

    def test_round_trips_through_parse_iso_as_aware(self) -> None:
        # Arrange
        raw = now_iso()

        # Act
        parsed = parse_iso(raw)

        # Assert
        assert parsed.tzinfo is not None


class TestEnsureAware:
    def test_aware_value_passed_through_unchanged(self) -> None:
        # Arrange
        aware = datetime.now(UTC)

        # Act
        result = ensure_aware(aware)

        # Assert
        assert result is aware

    def test_naive_value_gets_local_tzinfo_attached(self) -> None:
        # Arrange
        naive = datetime(2026, 7, 21, 7, 39, 25)

        # Act
        result = ensure_aware(naive)

        # Assert
        assert result.tzinfo is not None


class TestAgeSeconds:
    def test_recent_aware_timestamp_has_small_age(self) -> None:
        # Arrange
        started = (datetime.now(UTC) - timedelta(minutes=15)).isoformat(
            timespec="seconds"
        )

        # Act
        age = age_seconds(started)

        # Assert: ~900s elapsed, not hours -- this is the exact scenario from
        # the reopened plan's gap: a 15-minute-old pipeline must not appear
        # stale under the 4h TTL.
        assert 800 < age < 1000

    def test_legacy_naive_timestamp_does_not_raise(self) -> None:
        # Arrange: pipeline.json written before this fix stored naive local
        # time. A mixed naive/aware comparison must not raise TypeError.
        naive_recent = datetime.now().isoformat(timespec="seconds")

        # Act
        age = age_seconds(naive_recent)

        # Assert
        assert age >= 0

    def test_explicit_now_reference_is_honored(self) -> None:
        # Arrange
        started = datetime(2026, 7, 21, 7, 0, 0, tzinfo=UTC)
        reference = datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC)

        # Act
        age = age_seconds(started.isoformat(timespec="seconds"), now=reference)

        # Assert
        assert age == 2 * 3600
