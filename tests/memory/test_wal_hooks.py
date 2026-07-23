"""Unit tests for :mod:`cortex.memory.wal_hooks`."""

from __future__ import annotations

from pathlib import Path

from cortex.memory.wal import ToolInvocationLog, WalStatus
from cortex.memory.wal_hooks import (
    try_wal_record_tool_invocation,
    wal_arg_keys_from_kwargs,
)


def test_wal_arg_keys_from_kwargs_excludes_framework_keys() -> None:
    # Arrange
    kwargs = {
        "operation": "read",
        "since": None,
        "ctx": object(),
        "timeout": 30.0,
        "stability_timeout": None,
        "kind": "tool",
        "project_root": Path("/tmp"),
        "enable_progress": False,
    }

    # Act
    keys = wal_arg_keys_from_kwargs(kwargs)

    # Assert: only user-facing arg names remain, sorted, no values leaked.
    assert keys == ["operation", "since"]


def test_wal_arg_keys_from_kwargs_empty_returns_empty_list() -> None:
    # Arrange / Act
    keys = wal_arg_keys_from_kwargs({})

    # Assert
    assert keys == []


def test_try_wal_record_tool_invocation_skips_when_project_root_none(
    tmp_path: Path,
) -> None:
    # Arrange / Act
    try_wal_record_tool_invocation(None, "run_quality_gate", ["foo"], True, None)

    # Assert: no wal dir created anywhere relative to tmp_path (no-op).
    assert not (tmp_path / ".cortex" / "wal").exists()


def test_try_wal_record_tool_invocation_appends_entry(tmp_path: Path) -> None:
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()

    # Act
    try_wal_record_tool_invocation(
        root, "memory_wal", ["operation", "label"], True, None
    )

    # Assert
    wal_dir = root / ".cortex" / "wal"
    entries = ToolInvocationLog(wal_dir).read()
    assert len(entries) == 1
    assert entries[0].tool_name == "memory_wal"
    assert entries[0].arg_keys == ["operation", "label"]
    assert entries[0].status == WalStatus.OK


def test_try_wal_record_tool_invocation_records_error_outcome(tmp_path: Path) -> None:
    # Arrange
    root = tmp_path / "proj"
    root.mkdir()

    # Act
    try_wal_record_tool_invocation(root, "fix_markdown_lint", [], False, "ValueError")

    # Assert
    wal_dir = root / ".cortex" / "wal"
    entries = ToolInvocationLog(wal_dir).read()
    assert len(entries) == 1
    assert entries[0].status == WalStatus.ERROR
    assert entries[0].error_type == "ValueError"


def test_try_wal_record_tool_invocation_swallows_oserror(tmp_path: Path) -> None:
    # Arrange: point at a path that cannot be created (file where dir expected).
    root = tmp_path / "proj"
    root.mkdir()
    blocker = root / ".cortex"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    _ = blocker.write_text("not a directory", encoding="utf-8")

    # Act / Assert: advisory logging never raises even when the underlying
    # WAL directory cannot be created (blocked by a same-named file).
    try_wal_record_tool_invocation(root, "memory_wal", ["operation"], True, None)
