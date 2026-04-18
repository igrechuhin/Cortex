# pyright: reportUnusedFunction=false
"""Shared helpers for tests/unit/test_mcp_stability_timeouts.py (keeps main module under size limits)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import cortex.core.mcp_stability_semaphores as semaphores_mod
from cortex.core.mcp_stability import run_and_finalize
from cortex.core.mcp_stability_config import (
    get_long_running_semaphore,
    get_usage_context_init_lock,
)
from cortex.core.models import HandlerKind

ExecResultT = tuple[str, bool, str | None, bool, int | None, str | None]


async def _lr_hold_until_event(
    first_acquired: asyncio.Event, done: asyncio.Event
) -> ExecResultT:
    _ = first_acquired.set()
    _ = await done.wait()
    return "first", True, None, False, None, None


async def _lr_wait_never(
    first_acquired: asyncio.Event, never: asyncio.Event
) -> ExecResultT:
    _ = first_acquired.set()
    _ = await never.wait()
    return "first", True, None, False, None, None


async def _lr_fixed_second() -> ExecResultT:
    return "second", True, None, False, None, None


async def _release_sem_after_sleep(
    sem: object, ev: asyncio.Event, delay: float
) -> None:
    await asyncio.sleep(delay)
    release = getattr(sem, "release")
    release()
    _ = ev.set()


async def run_two_long_running_sequential(wait_patch_seconds: float) -> tuple[str, str]:
    semaphores_mod.reset_long_running_tools_semaphore_for_testing()
    _ = get_long_running_semaphore()
    first_done, first_acquired = asyncio.Event(), asyncio.Event()

    async def first_execute() -> ExecResultT:
        return await _lr_hold_until_event(first_acquired, first_done)

    async def second_execute() -> ExecResultT:
        return await _lr_fixed_second()

    path = "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_WAIT_SECONDS"
    with patch(path, wait_patch_seconds):
        rf = run_and_finalize
        t1 = asyncio.create_task(
            rf(first_execute, None, None, "first_tool", 0, HandlerKind.TOOL, True)
        )
        _ = await first_acquired.wait()
        t2 = asyncio.create_task(
            rf(second_execute, None, None, "second_tool", 0, HandlerKind.TOOL, True)
        )
        _ = first_done.set()
        return await t1, await t2


async def second_long_running_retry_result() -> tuple[str, asyncio.Event]:
    semaphores_mod.reset_long_running_tools_semaphore_for_testing()
    sem = get_long_running_semaphore()
    await sem.acquire()
    released_during_retry = asyncio.Event()

    async def second_execute() -> ExecResultT:
        return await _lr_fixed_second()

    p_wait = patch(
        "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
        0.1,
    )
    p_retry = patch(
        "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS",
        0.5,
    )
    with p_wait, p_retry:
        release_task = asyncio.create_task(
            _release_sem_after_sleep(sem, released_during_retry, 0.12)
        )
        result = await run_and_finalize(
            second_execute, None, None, "second_tool", 0, HandlerKind.TOOL, True
        )
        await release_task
    return result, released_during_retry


async def long_running_cancel_first_then_second(wait_patch_seconds: float) -> str:
    semaphores_mod.reset_long_running_tools_semaphore_for_testing()
    _ = get_long_running_semaphore()
    first_acquired, never_set = asyncio.Event(), asyncio.Event()

    async def first_execute() -> ExecResultT:
        return await _lr_wait_never(first_acquired, never_set)

    async def second_execute() -> ExecResultT:
        return await _lr_fixed_second()

    path = "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_WAIT_SECONDS"
    with patch(path, wait_patch_seconds):
        rf = run_and_finalize
        first_task = asyncio.create_task(
            rf(first_execute, None, None, "first_tool", 0, HandlerKind.TOOL, True)
        )
        acquired = await first_acquired.wait()
        assert acquired
        _ = first_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_task
        return await rf(
            second_execute, None, None, "second_tool", 0, HandlerKind.TOOL, True
        )


async def start_hold_usage_init_lock_forever() -> asyncio.Task[None]:
    lock = get_usage_context_init_lock()
    lock_acquired = asyncio.Event()

    async def hold_lock_forever() -> None:
        async with lock:
            _ = lock_acquired.set()
            _ = await asyncio.Event().wait()

    hold_task = asyncio.create_task(hold_lock_forever())
    _ = await lock_acquired.wait()
    return hold_task


async def expect_tool_fails_usage_init_lock(
    test_tool: Callable[[], Awaitable[str]],
) -> None:
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/test"),
        ),
        patch(
            "cortex.managers.initialization.get_managers",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        with pytest.raises(
            RuntimeError, match="Failed to acquire usage context init lock"
        ):
            _ = await test_tool()
