"""Unit tests for usage analytics_collection helpers."""

from __future__ import annotations

from cortex.tools.usage.analytics_collection import (
    normalize_usage_observation_ids,
    usage_date_range_from_strings,
)


def test_normalize_usage_observation_ids_filters_empty_preserves_order() -> None:
    assert normalize_usage_observation_ids(["a", "", "b", "  ", "c"]) == [
        "a",
        "b",
        "  ",
        "c",
    ]


def test_usage_date_range_invalid_start_keeps_prior_default_start() -> None:
    start, end = usage_date_range_from_strings("not-a-date", None, default_days=7)
    assert start < end
    delta_days = (end - start).total_seconds() / 86400.0
    assert 6.9 <= delta_days <= 7.1
