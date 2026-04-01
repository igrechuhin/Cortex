"""Tests for the phase_a_lock concurrency guard in pre_commit_zero_arg_tools.

Verifies that concurrent calls to Phase-A tools are serialized rather than
running simultaneously, preventing MCP server crashes from concurrent subprocess
jobs racing on shared session files.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import cortex.tools.execution.pre_commit_zero_arg_tools as _module


class TestPhaseALockExists:
    """get_phase_a_lock() must return an asyncio.Lock bound to the running loop."""

    @pytest.mark.asyncio
    async def test_phase_a_lock_is_asyncio_lock(self) -> None:
        # Arrange / Act — must be called inside an async context (running loop)
        lock = _module.get_phase_a_lock()
        # Assert
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_phase_a_lock_same_instance_within_loop(self) -> None:
        """Two calls within the same event loop return the identical lock."""
        lock_a = _module.get_phase_a_lock()
        lock_b = _module.get_phase_a_lock()
        assert lock_a is lock_b


def _make_tracking_impl(order: list[str]):  # noqa: ANN202
    """Return a fake autofix_impl that records start/end into *order*."""

    async def fake_impl(
        root: object, include_untracked_markdown: object, ctx: object
    ) -> str:
        order.append("impl_start")
        await asyncio.sleep(0.05)
        order.append("impl_end")
        return '{"status": "success"}'

    return fake_impl


class TestFixQualityIssuesSerializes:
    """Concurrent autofix calls must be serialized via get_phase_a_lock."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_are_serialized(self) -> None:
        """Two concurrent autofix calls must not run simultaneously."""
        order: list[str] = []

        async def _call() -> None:
            _ = await _module.autofix(ctx=None)

        with (
            patch.object(
                _module, "autofix_impl", side_effect=_make_tracking_impl(order)
            ),
            patch.object(_module, "get_current_project_root", return_value=MagicMock()),
        ):
            _ = await asyncio.gather(_call(), _call())

        expected = ["impl_start", "impl_end", "impl_start", "impl_end"]
        assert order == expected, f"Expected serial execution, got: {order}"


class TestFixQualityIssuesAcquiresLock:
    """autofix must acquire get_phase_a_lock() before calling impl."""

    @pytest.mark.asyncio
    async def test_lock_held_during_autofix_impl(self) -> None:
        """The lock must be held while autofix_impl runs."""
        # Arrange
        lock_was_locked_during_call = False

        async def fake_impl(
            root: object,
            include_untracked_markdown: object,
            ctx: object,
        ) -> str:
            nonlocal lock_was_locked_during_call
            lock_was_locked_during_call = _module.get_phase_a_lock().locked()
            return '{"status": "success"}'

        with (
            patch.object(
                _module,
                "autofix_impl",
                side_effect=fake_impl,
            ),
            patch.object(
                _module,
                "get_current_project_root",
                return_value=MagicMock(),
            ),
        ):
            # Act
            _ = await _module.autofix(ctx=None)

        # Assert
        assert (
            lock_was_locked_during_call
        ), "get_phase_a_lock() was not held while autofix_impl ran"
