"""Unit tests for progress reporting (Phase 46)."""

from unittest.mock import AsyncMock

import pytest

from cortex.core.progress import ProgressReporter


@pytest.mark.asyncio
async def test_progress_reporter_when_ctx_none_start_is_noop() -> None:
    """ProgressReporter with ctx=None does not call report_progress."""
    reporter = ProgressReporter(total_steps=4, tool_name="test", ctx=None)
    await reporter.start()
    # No exception; report_progress_safe is no-op when ctx is None


@pytest.mark.asyncio
async def test_progress_reporter_when_ctx_present_calls_report_progress() -> None:
    """ProgressReporter with ctx present calls report_progress_safe."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=4, tool_name="test", ctx=ctx)
    await reporter.start()
    ctx.report_progress.assert_awaited_once_with(0.0, 100.0, message=None)


@pytest.mark.asyncio
async def test_progress_reporter_report_normalizes_step_to_pct() -> None:
    """ProgressReporter.report normalizes step index to 0-100."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=4, tool_name="t", ctx=ctx)
    await reporter.report(2, "half")
    ctx.report_progress.assert_awaited_once_with(50.0, 100.0, message=None)


@pytest.mark.asyncio
async def test_progress_reporter_report_accepts_raw_pct() -> None:
    """ProgressReporter.report accepts raw percentage when > total_steps."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=4, tool_name="t", ctx=ctx)
    await reporter.report(90, "ninety")
    ctx.report_progress.assert_awaited_once_with(90.0, 100.0, message=None)


@pytest.mark.asyncio
async def test_progress_reporter_step_increments_and_reports() -> None:
    """ProgressReporter.step increments current step and reports."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=3, tool_name="t", ctx=ctx)
    await reporter.step("one")
    assert ctx.report_progress.await_count == 1
    ctx.report_progress.assert_awaited_with(33.0, 100.0, message=None)
    await reporter.step("two")
    ctx.report_progress.assert_awaited_with(66.0, 100.0, message=None)


@pytest.mark.asyncio
async def test_progress_reporter_complete_reports_100() -> None:
    """ProgressReporter.complete reports 100%."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=4, tool_name="t", ctx=ctx)
    await reporter.complete("done")
    ctx.report_progress.assert_awaited_once_with(100.0, 100.0, message=None)


@pytest.mark.asyncio
async def test_progress_reporter_total_steps_min_one() -> None:
    """ProgressReporter uses at least 1 total step."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = ProgressReporter(total_steps=0, tool_name="t", ctx=ctx)
    await reporter.report(0, "")
    ctx.report_progress.assert_awaited_once_with(0.0, 100.0, message=None)
    await reporter.complete()
    ctx.report_progress.assert_awaited_with(100.0, 100.0, message=None)
