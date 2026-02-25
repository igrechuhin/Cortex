"""Error recovery audit tests for Security & Resilience Step 3.

Verifies:
- asyncio.CancelledError is never accidentally caught (propagates through critical paths)
- Resources (semaphores, locks) are released on exception
- No silent error swallowing in BaseException handlers
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from cortex.core.context_logging import log_client, report_progress_safe
from cortex.core.mcp_stability_config import TrackedSemaphore


class TestCancelledErrorPropagation:
    """Verify CancelledError propagates through BaseException handlers."""

    @pytest.mark.asyncio
    async def test_log_client_reraises_cancelled_error(self) -> None:
        """log_client must re-raise CancelledError (never swallow)."""
        ctx = AsyncMock()
        ctx.log = AsyncMock(side_effect=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            await log_client(ctx, "info", "test")

    @pytest.mark.asyncio
    async def test_report_progress_safe_reraises_cancelled_error(self) -> None:
        """report_progress_safe must re-raise CancelledError (never swallow)."""
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock(side_effect=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            await report_progress_safe(ctx, 50.0, 100.0)


class TestResourceReleaseOnException:
    """Verify resources are released when exceptions occur."""

    @pytest.mark.asyncio
    async def test_tracked_semaphore_releases_on_cancelled_error(self) -> None:
        """Semaphore must be released when CancelledError is raised inside context."""
        sem = TrackedSemaphore(1)
        with pytest.raises(asyncio.CancelledError):
            async with sem:
                raise asyncio.CancelledError()
        # Semaphore should be released (available == 1)
        ok = await sem.try_acquire(timeout=0.1)
        assert ok is True
        sem.release()
