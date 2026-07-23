"""Unit tests for :mod:`cortex.core.mcp_tool_telemetry`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cortex.core.mcp_tool_telemetry import (
    record_tool_invocation_failure,
    record_tool_invocation_success,
)
from cortex.memory.wal import ToolInvocationLog, WalStatus


def test_record_tool_invocation_success_appends_ok_entry(tmp_path: Path) -> None:
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()
    kwargs = {"operation": "read", "ctx": "ctx-placeholder"}

    # Act
    with patch(
        "cortex.core.mcp_tool_telemetry.get_current_project_root",
        return_value=root,
    ):
        record_tool_invocation_success("memory_wal", kwargs)

    # Assert
    entries = ToolInvocationLog(root / ".cortex" / "wal").read()
    assert len(entries) == 1
    assert entries[0].tool_name == "memory_wal"
    assert entries[0].arg_keys == ["operation"]
    assert entries[0].status == WalStatus.OK


def test_record_tool_invocation_failure_appends_error_entry(tmp_path: Path) -> None:
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()
    kwargs = {"label": "x"}

    # Act
    with patch(
        "cortex.core.mcp_tool_telemetry.get_current_project_root",
        return_value=root,
    ):
        record_tool_invocation_failure("memory_wal", kwargs, "ValueError")

    # Assert
    entries = ToolInvocationLog(root / ".cortex" / "wal").read()
    assert len(entries) == 1
    assert entries[0].status == WalStatus.ERROR
    assert entries[0].error_type == "ValueError"


def test_record_tool_invocation_success_noop_without_project_root() -> None:
    # Arrange / Act: no project root resolved -> advisory no-op, never raises.
    with patch(
        "cortex.core.mcp_tool_telemetry.get_current_project_root",
        return_value=None,
    ):
        record_tool_invocation_success("memory_wal", {"operation": "read"})
