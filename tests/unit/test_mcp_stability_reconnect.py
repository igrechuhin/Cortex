"""Unit tests for MCP reconnection and circuit breaker logic (Phase 86)."""

from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.mcp_stability_retry import (
    check_connection_health,
    ensure_clean_connection_state_for_testing,
    get_connection_state,
    reconnect,
)


def _reset_connection_state() -> None:
    """Reset global connection state for test isolation."""
    ensure_clean_connection_state_for_testing()


@pytest.mark.asyncio
async def test_reconnect_succeeds_after_transient_failures() -> None:
    """reconnect() succeeds after transient connection errors with backoff."""
    _reset_connection_state()
    attempts: list[int] = []

    async def ping() -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("Connection closed")

    with (
        patch(
            "cortex.core.mcp_stability_retry._ping_transport",
            new_callable=AsyncMock,
            side_effect=ping,
        ),
        patch("cortex.core.mcp_stability_retry.asyncio.sleep", new_callable=AsyncMock),
    ):
        health = await reconnect("test")

    assert len(attempts) == 3
    assert health.healthy is True
    assert health.degraded is False
    assert health.reconnecting is False
    # After a successful reconnect, consecutive_failures should be reset.
    state = get_connection_state()
    assert state.consecutive_failures == 0


@pytest.mark.asyncio
async def test_reconnect_opens_circuit_after_max_failures() -> None:
    """reconnect() opens circuit breaker and raises after max failures."""
    _reset_connection_state()

    async def ping_fail() -> None:
        raise ConnectionError("Connection closed")

    with (
        patch(
            "cortex.core.mcp_stability_retry._ping_transport",
            new_callable=AsyncMock,
            side_effect=ping_fail,
        ),
        patch("cortex.core.mcp_stability_retry.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(ConnectionError, match="circuit breaker open"):
            _ = await reconnect("test-fail")

    health_after = await check_connection_health()
    assert health_after.healthy is False
    assert health_after.degraded is True
    # In degraded mode, a subsequent reconnect() call should not retry again.
    with patch(
        "cortex.core.mcp_stability_retry._ping_transport",
        new_callable=AsyncMock,
    ) as ping_mock:
        _ = await reconnect("second-call")
    ping_mock.assert_not_awaited()
