"""Unit tests for pre_commit_tools_run_helpers (heartbeat and callbacks)."""

import asyncio
from collections.abc import Callable, Coroutine
from unittest.mock import MagicMock

import pytest

from cortex.tools.execution import pre_commit_tools_run_helpers

Recorded = list[tuple[float, float | None, str | None]]


async def _yielding_sleep(_interval: float) -> None:
    await asyncio.sleep(0)


def _make_fake_log(
    recorded: Recorded,
) -> Callable[[object, str, str], Coroutine[None, None, None]]:
    async def fake_log(
        _ctx: object,
        _level: str,
        message: str,
    ) -> None:
        progress = float(len(message))
        recorded.append((progress, None, message))

    return fake_log


def _patch_heartbeat_mocks(monkeypatch: pytest.MonkeyPatch, recorded: Recorded) -> None:
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_tools_run_helpers.log_client",
        _make_fake_log(recorded),
    )
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_tools_run_helpers._async_sleep",
        _yielding_sleep,
    )


async def _cancel_heartbeat_after_yields(task: asyncio.Task[None], yields: int) -> None:
    for _ in range(yields):
        await asyncio.sleep(0)
    _ = task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_heartbeat_loop_builds_monotonic_dot_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each heartbeat tick lengthens the message by one dot; total stays None."""
    recorded: Recorded = []
    _patch_heartbeat_mocks(monkeypatch, recorded)
    ctx = MagicMock()
    task = asyncio.create_task(pre_commit_tools_run_helpers.heartbeat_loop(ctx, 0.001))
    await _cancel_heartbeat_after_yields(task, 12)
    assert len(recorded) >= 3
    for i, (prog, tot, msg) in enumerate(recorded[:5], start=1):
        assert prog == float(i)
        assert tot is None
        assert msg == "." * i


@pytest.mark.asyncio
async def test_heartbeat_loop_caps_dot_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """After _HEARTBEAT_MAX_DOTS, message length and numeric progress stop growing."""
    monkeypatch.setattr(pre_commit_tools_run_helpers, "_HEARTBEAT_MAX_DOTS", 3)
    recorded: Recorded = []
    _patch_heartbeat_mocks(monkeypatch, recorded)
    ctx = MagicMock()
    task = asyncio.create_task(pre_commit_tools_run_helpers.heartbeat_loop(ctx, 0.001))
    await _cancel_heartbeat_after_yields(task, 25)
    assert recorded
    for _prog, tot, msg in recorded:
        assert tot is None
        assert msg is not None
        assert len(msg) <= 3
        assert msg == "." * len(msg)
    assert recorded[-1] == (3.0, None, "...")
