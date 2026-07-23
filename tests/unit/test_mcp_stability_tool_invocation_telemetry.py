"""Integration test: mcp_tool_wrapper -> tool-invocation telemetry -> read accessor.

Simulates a short tool-call sequence (one success, one failure) through the
real ``@mcp_tool_wrapper`` decorator and confirms
``memory_wal(operation="tool_invocations")`` surfaces both calls -- the
evidence-source path analyze-tools/analyze-session consume.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.mcp_stability import CANCELLED_RESPONSE_JSON, mcp_tool_wrapper
from cortex.tools.memory.wal_tool import (
    MemoryWALInput,
    MemoryWalToolOp,
    handle_memory_wal_sync,
)


@mcp_tool_wrapper(timeout=1.0)
async def _succeeding_tool(operation: str) -> str:
    return f"ok:{operation}"


@mcp_tool_wrapper(timeout=1.0)
async def _failing_tool(label: str) -> str:
    raise ValueError("boom")


@mcp_tool_wrapper(timeout=1.0)
async def _cancelled_tool(label: str) -> str:
    raise asyncio.CancelledError


@contextmanager
def _patched_telemetry_session(root: Path) -> Iterator[None]:
    """Pin project root + session id so the write path and read path line up.

    ``wal_hooks.wal_agent_hint`` (write path) and ``wal_tool``'s imported
    reference (read path) are separate bindings that must be patched together.
    """
    with (
        patch(
            "cortex.core.mcp_tool_telemetry.get_current_project_root",
            return_value=root,
        ),
        patch("cortex.memory.wal_hooks.wal_agent_hint", return_value="unknown"),
        patch("cortex.tools.memory.wal_tool.wal_agent_hint", return_value="unknown"),
    ):
        yield


@pytest.mark.asyncio
async def test_tool_call_sequence_surfaces_via_tool_invocations_accessor(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()

    # Act: run a short call sequence, then read it back via the accessor.
    with _patched_telemetry_session(root):
        _ = await _succeeding_tool(operation="read")
        with pytest.raises(ValueError):
            _ = await _failing_tool(label="x")
        res = handle_memory_wal_sync(
            root, MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS)
        )

    # Assert: both calls surfaced with outcome and arg key names, no values.
    assert res.tool_invocations is not None
    by_name = {e.tool_name: e for e in res.tool_invocations}
    assert by_name["_succeeding_tool"].status.value == "ok"
    assert by_name["_succeeding_tool"].arg_keys == ["operation"]
    assert by_name["_failing_tool"].status.value == "error"
    assert by_name["_failing_tool"].error_type == "ValueError"
    assert by_name["_failing_tool"].arg_keys == ["label"]


@pytest.mark.asyncio
async def test_cancelled_tool_call_is_recorded_as_error_not_success(
    tmp_path: Path,
) -> None:
    """A cancelled tool call must not be logged as a successful invocation.

    ``with_mcp_stability`` swallows ``asyncio.CancelledError`` internally and
    returns ``CANCELLED_RESPONSE_JSON`` as a normal (non-exception) value, so
    the telemetry hook must inspect the returned value -- not rely on an
    exception -- to classify the outcome correctly.
    """
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()

    # Act: invoke a tool whose body raises CancelledError; the wrapper must
    # not propagate the exception (with_mcp_stability already handles it).
    with _patched_telemetry_session(root):
        result = await _cancelled_tool(label="x")
        res = handle_memory_wal_sync(
            root, MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS)
        )

    # Assert: the call surfaces as an error/CancelledError, not a success.
    assert result == CANCELLED_RESPONSE_JSON
    assert res.tool_invocations is not None
    by_name = {e.tool_name: e for e in res.tool_invocations}
    assert by_name["_cancelled_tool"].status.value == "error"
    assert by_name["_cancelled_tool"].error_type == "CancelledError"
    assert by_name["_cancelled_tool"].arg_keys == ["label"]
