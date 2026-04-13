"""Asyncio subprocess helpers (timeout/cancel cleanup)."""

from __future__ import annotations

import asyncio


async def reap_orphaned_subprocess(
    process: asyncio.subprocess.Process | None,
    *,
    wait_timeout: float = 5.0,
) -> None:
    """Kill and wait if ``communicate`` was cancelled while the child still runs.

    ``asyncio.timeout`` cancels ``communicate()`` but does not stop the child; an
    unreaped PID keeps the Unix child-watcher busy and can trigger stdlib logging
    after stderr is closed during interpreter shutdown (e.g. pytest/xdist).
    """
    if process is None or process.returncode is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        return
    try:
        _ = await asyncio.wait_for(process.wait(), timeout=wait_timeout)
    except (TimeoutError, asyncio.CancelledError, ProcessLookupError):
        pass
