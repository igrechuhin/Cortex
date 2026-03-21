"""Tests for MCP server crash fixes (2026-03-21 investigation).

Fix 1: MCP error -32000 treated as graceful disconnect (exit 0).
Fix 2: run_docs_gate calls validate_impl directly (no nested semaphore).
Fix 3: _record_connection_closure/_recovery protected by asyncio.Lock.
"""

# pyright: reportPrivateUsage=false

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.mcp_stability_retry import (
    _get_connection_state,
    _record_connection_closure,
    _record_connection_recovery,
    ensure_clean_connection_state_for_testing,
)


def _reset() -> None:
    """Reset global connection state for test isolation."""
    ensure_clean_connection_state_for_testing()


class TestConnectionStateLockProtection:
    """Fix 3: _record_connection_closure and _record_connection_recovery
    are protected by asyncio.Lock to prevent state corruption."""

    @pytest.mark.asyncio
    async def test_record_closure_sets_connected_false(self) -> None:
        """_record_connection_closure marks state as disconnected."""
        _reset()
        state = _get_connection_state()
        assert state.connected is True

        await _record_connection_closure()

        assert state.connected is False

    @pytest.mark.asyncio
    async def test_record_recovery_resets_state(self) -> None:
        """_record_connection_recovery resets all degraded-mode flags."""
        _reset()
        state = _get_connection_state()
        state.connected = False
        state.reconnecting = True
        state.circuit_open = True
        state.consecutive_failures = 5
        state.last_error = "test error"

        await _record_connection_recovery()

        assert state.connected is True
        assert state.reconnecting is False
        assert state.circuit_open is False
        assert state.consecutive_failures == 0
        assert state.last_error is None

    @pytest.mark.asyncio
    async def test_concurrent_closure_and_recovery_do_not_corrupt(
        self,
    ) -> None:
        """Concurrent _record_connection_closure and _record_connection_recovery
        calls do not leave state in an inconsistent intermediate."""
        _reset()

        barrier = asyncio.Barrier(2)

        async def close_then_recover() -> None:
            _ = await _record_connection_closure()
            _ = await barrier.wait()
            _ = await _record_connection_recovery()

        async def close_then_recover_delayed() -> None:
            _ = await _record_connection_closure()
            _ = await barrier.wait()
            _ = await _record_connection_recovery()

        _ = await asyncio.gather(close_then_recover(), close_then_recover_delayed())

        state = _get_connection_state()
        assert state.connected is True
        assert state.circuit_open is False
        assert state.consecutive_failures == 0


class TestDocsGateBypassesSemaphore:
    """Fix 2: run_docs_gate calls validate_impl directly, avoiding nested
    tool-semaphore acquisition."""

    @pytest.mark.asyncio
    async def test_run_single_validation_calls_validate_impl(self) -> None:
        """_run_single_validation calls validate_impl (not validate MCP wrapper)."""
        from cortex.tools.execution.pre_commit_docs_memory_helpers import (
            _run_single_validation,
        )
        from cortex.tools.validation.operations import ValidateCheckTypeName

        mock_result = '{"valid": true, "message": "ok"}'
        with patch(
            "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_impl",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_impl:
            result = await _run_single_validation(
                ValidateCheckTypeName.TIMESTAMPS, ctx=None
            )

        mock_impl.assert_awaited_once()
        assert result is not None
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_run_single_validation_does_not_call_validate(
        self,
    ) -> None:
        """_run_single_validation does NOT call the validate() MCP wrapper."""
        mock_result = '{"valid": true}'
        with (
            patch(
                "cortex.tools.execution.pre_commit_docs_memory_helpers.validate_impl",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "cortex.tools.validation.operations.validate",
                new_callable=AsyncMock,
            ) as mock_validate,
        ):
            from cortex.tools.execution.pre_commit_docs_memory_helpers import (
                _run_single_validation,
            )
            from cortex.tools.validation.operations import (
                ValidateCheckTypeName,
            )

            _ = await _run_single_validation(ValidateCheckTypeName.TIMESTAMPS, ctx=None)

        mock_validate.assert_not_awaited()


class TestGracefulDisconnectOnMCPError32000:
    """Fix 1: RuntimeError('MCP error -32000: Connection closed') in a
    BaseExceptionGroup is treated as a graceful disconnect (exit 0)."""

    def test_handle_broken_resource_returns_true_for_mcp_error_32000(
        self,
    ) -> None:
        """_handle_broken_resource_in_group returns True for MCP -32000."""
        from cortex.main import _handle_broken_resource_in_group

        exc = RuntimeError("MCP error -32000: Connection closed")
        eg = BaseExceptionGroup("TaskGroup", [exc])
        assert _handle_broken_resource_in_group(eg) is True

    def test_handle_broken_resource_returns_false_for_unrelated_error(
        self,
    ) -> None:
        """_handle_broken_resource_in_group returns False for non-connection errors."""
        from cortex.main import _handle_broken_resource_in_group

        exc = ValueError("unrelated")
        eg = BaseExceptionGroup("TaskGroup", [exc])
        assert _handle_broken_resource_in_group(eg) is False

    @patch("cortex.main.get_effective_transport", return_value="stdio")
    @patch("cortex.main.mcp")
    def test_main_exits_0_on_mcp_error_32000(
        self, mock_mcp: MagicMock, _mock_transport: MagicMock
    ) -> None:
        """main() exits with code 0 when MCP -32000 is in BaseExceptionGroup."""
        from cortex.main import main

        exc = RuntimeError("MCP error -32000: Connection closed")
        eg = BaseExceptionGroup("TaskGroup (1 sub-exception)", [exc])
        mock_mcp.run.side_effect = eg

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
