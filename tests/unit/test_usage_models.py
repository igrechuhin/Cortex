"""Unit tests for usage tracking models (Phase 29)."""

from cortex.managers.usage_models import ToolUsageEvent, ToolUsageStats


class TestToolUsageEvent:
    """Test ToolUsageEvent model."""

    def test_event_creation_minimal(self) -> None:
        """Test creating event with required fields only."""
        event = ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-01T12:00:00+00:00",
            duration_ms=10.5,
            success=True,
        )
        assert isinstance(event.id, str)
        assert event.id
        assert event.tool_name == "manage_file"
        assert event.timestamp == "2026-02-01T12:00:00+00:00"
        assert event.duration_ms == 10.5
        assert event.success is True
        assert event.error_type is None
        assert event.params_hash is None

    def test_event_creation_with_error(self) -> None:
        """Test creating event with error type."""
        event = ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-01T12:00:00+00:00",
            duration_ms=5.0,
            success=False,
            error_type="ValueError",
        )
        assert isinstance(event.id, str)
        assert event.id
        assert event.success is False
        assert event.error_type == "ValueError"

    def test_event_model_dump(self) -> None:
        """Test event serialization."""
        event = ToolUsageEvent(
            tool_name="get_tool_usage_stats",
            timestamp="2026-02-01T12:00:00+00:00",
            duration_ms=1.0,
            success=True,
            params_hash="abc123",
        )
        d = event.model_dump()
        assert "id" in d
        assert isinstance(d["id"], str)
        assert d["id"]
        assert d["tool_name"] == "get_tool_usage_stats"
        assert d["params_hash"] == "abc123"

    def test_event_phase57_error_pattern_fields(self) -> None:
        """Test Phase 57 fields: retry_count, param_validation_failure, result_used."""
        event = ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-01T12:00:00+00:00",
            duration_ms=10.0,
            success=True,
            retry_count=1,
            param_validation_failure=None,
            result_used=True,
        )
        assert event.retry_count == 1
        assert event.param_validation_failure is None
        assert event.result_used is True
        event2 = ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-01T12:00:01+00:00",
            duration_ms=5.0,
            success=False,
            error_type="ValidationError",
            param_validation_failure="file_name: required",
        )
        assert event2.param_validation_failure == "file_name: required"
        assert event2.retry_count is None
        assert event2.result_used is None

    def test_event_phase62_response_tokens(self) -> None:
        """Test Phase 62 field: response_tokens (token-efficiency tracking)."""
        event = ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-01T12:00:00+00:00",
            duration_ms=10.0,
            success=True,
            response_tokens=1500,
        )
        assert event.response_tokens == 1500
        event_none = ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-01T12:00:01+00:00",
            duration_ms=5.0,
            success=True,
        )
        assert event_none.response_tokens is None


class TestToolUsageStats:
    """Test ToolUsageStats model."""

    def test_stats_creation(self) -> None:
        """Test creating stats with all fields."""
        stats = ToolUsageStats(
            tool_name="manage_file",
            total_calls=100,
            successful_calls=98,
            failed_calls=2,
            avg_duration_ms=15.5,
            min_duration_ms=1.0,
            max_duration_ms=200.0,
            error_types={"ValueError": 2},
            first_used="2026-01-01T00:00:00+00:00",
            last_used="2026-02-01T12:00:00+00:00",
        )
        assert stats.tool_name == "manage_file"
        assert stats.total_calls == 100
        assert stats.successful_calls == 98
        assert stats.failed_calls == 2
        assert stats.avg_duration_ms == 15.5
        assert stats.error_types == {"ValueError": 2}

    def test_stats_default_error_types(self) -> None:
        """Test stats default error_types is empty dict."""
        stats = ToolUsageStats(
            tool_name="x",
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            avg_duration_ms=0.0,
            min_duration_ms=0.0,
            max_duration_ms=0.0,
            first_used="2026-01-01T00:00:00+00:00",
            last_used="2026-01-01T00:00:00+00:00",
        )
        assert stats.error_types == {}
