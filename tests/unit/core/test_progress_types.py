"""Unit tests for structured progress models and helper."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import Future
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.progress_types import (
    CommitProgress,
    PipelineProgress,
    QualityGateProgress,
    SessionProgress,
    report_structured_progress,
)
from cortex.tools.execution import pre_commit_tools_run_helpers


def test_quality_gate_progress_serializes_to_json() -> None:
    # Arrange
    progress = QualityGateProgress(
        tool="quality_gate",
        phase="checks",
        message="Running lint",
        checks_completed=1,
        checks_total=8,
        current_check="lint",
    )

    # Act
    payload = json.loads(progress.model_dump_json())

    # Assert
    assert payload["tool"] == "quality_gate"
    assert payload["phase"] == "checks"
    assert payload["current_check"] == "lint"


def test_quality_gate_progress_errors_found_default_zero() -> None:
    # Arrange
    progress = QualityGateProgress(
        tool="quality_gate",
        phase="checks",
        message="Running format",
        checks_completed=2,
        checks_total=8,
        current_check="format",
    )

    # Assert
    assert progress.errors_found == 0


def test_commit_progress_phase_label_field() -> None:
    # Arrange
    progress = CommitProgress(
        tool="commit",
        phase="commit",
        message="Phase A",
        phase_label="preflight",
        step=1,
        total_steps=3,
    )

    # Assert
    assert progress.phase_label == "preflight"


def test_pipeline_progress_pipeline_field() -> None:
    # Arrange
    progress = PipelineProgress(
        tool="pipeline",
        phase="handoff",
        message="Writing phase data",
        pipeline="implement",
        operation="write",
    )

    # Assert
    assert progress.pipeline == "implement"


def test_session_progress_operation_field() -> None:
    # Arrange
    progress = SessionProgress(
        tool="session",
        phase="dispatch",
        message="Starting session operation",
        operation="start",
    )

    # Assert
    assert progress.operation == "start"


@pytest.mark.asyncio
async def test_report_structured_progress_calls_ctx_report_progress() -> None:
    # Arrange
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    progress = SessionProgress(
        tool="session",
        phase="dispatch",
        message="Registering session task",
        operation="register",
    )

    # Act
    await report_structured_progress(ctx, progress, current=1, total=1)

    # Assert
    ctx.report_progress.assert_awaited_once()


@pytest.mark.asyncio
async def test_report_structured_progress_none_ctx_does_not_raise() -> None:
    # Arrange
    progress = SessionProgress(
        tool="session",
        phase="dispatch",
        message="Deregistering session",
        operation="deregister",
    )

    # Act / Assert
    await report_structured_progress(None, progress, current=1, total=1)


@pytest.mark.asyncio
async def test_report_structured_progress_message_is_valid_json() -> None:
    # Arrange
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    progress = SessionProgress(
        tool="session",
        phase="dispatch",
        message="Compacting session memory",
        operation="compact",
    )

    # Act
    await report_structured_progress(ctx, progress, current=1, total=1)

    # Assert
    kwargs = ctx.report_progress.await_args.kwargs
    message = kwargs["message"]
    payload = json.loads(message)
    assert payload["tool"] == "session"
    assert payload["operation"] == "compact"


def test_pre_commit_pipeline_quality_gate_progress_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    captured: dict[str, object] = {}
    loop = asyncio.new_event_loop()

    def fake_run_coroutine_threadsafe(
        coro: object, _loop: asyncio.AbstractEventLoop
    ) -> Future[object]:
        captured["coroutine"] = coro
        future: Future[object] = Future()
        future.set_result(None)
        return future

    monkeypatch.setattr(
        pre_commit_tools_run_helpers,
        "_run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    callback = pre_commit_tools_run_helpers.make_phase_progress_callback(ctx, loop)
    assert callback is not None

    # Act
    callback(3, 8)

    # Assert
    coroutine = captured["coroutine"]
    assert asyncio.iscoroutine(coroutine)
    loop.run_until_complete(coroutine)
    loop.close()
