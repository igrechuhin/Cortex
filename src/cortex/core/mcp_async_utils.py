from __future__ import annotations

import asyncio


async def cancel_and_drain_progress_task(
    progress_task: asyncio.Task[None],
) -> None:
    """Cancel a progress task and wait for it to finish."""
    _ = progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        # Normal path when cancelling a long-running task.
        pass
