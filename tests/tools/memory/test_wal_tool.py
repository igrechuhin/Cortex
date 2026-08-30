"""Tests for ``memory_wal`` MCP tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.memory.wal import (
    ToolInvocationLog,
    WalOperation,
    WalStatus,
    wal_build_tool_invocation_entry,
)
from cortex.tools.memory.wal_tool import (
    MemoryWALInput,
    MemoryWalToolOp,
    handle_memory_wal_sync,
)


class WALEntryJsonFactory:
    """Minimal JSONL snippets for handler tests."""

    @staticmethod
    def error_line() -> str:
        payload = {
            "id": "a" * 12,
            "timestamp": "2026-04-15T12:00:00+00:00",
            "operation": "write",
            "file": "f.md",
            "agent_hint": "u",
            "content_hash_before": "none",
            "content_hash_after": "ab" * 8,
            "byte_delta": 1,
            "after_byte_len": 2,
            "status": "error",
            "error": "boom",
        }
        return json.dumps(payload) + "\n"

    @staticmethod
    def minimal_line(seq: int, ts: str) -> str:
        payload = {
            "id": f"{seq:012d}",
            "timestamp": ts,
            "operation": "write",
            "file": "f.md",
            "agent_hint": "u",
            "content_hash_before": "none",
            "content_hash_after": "ab" * 8,
            "byte_delta": 1,
            "after_byte_len": 2,
            "status": "ok",
            "error": None,
        }
        return json.dumps(payload)


def test_memory_wal_anomalies_handler(tmp_path: Path) -> None:
    root = tmp_path / "p"
    wal_dir = root / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    _ = (wal_dir / "write_log.jsonl").write_text(
        WALEntryJsonFactory.error_line(),
        encoding="utf-8",
    )
    res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.ANOMALIES),
    )
    assert res.warnings is not None
    assert any("error status" in w for w in res.warnings)


def test_memory_wal_snapshot_restore_flow(tmp_path: Path) -> None:
    root = tmp_path / "p"
    mb = root / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (mb / "z.md").write_text("orig", encoding="utf-8")
    snap_res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.SNAPSHOT, label="L1"),
    )
    assert snap_res.snapshot_path
    _ = (mb / "z.md").write_text("changed", encoding="utf-8")
    rest = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.RESTORE, label="L1"),
    )
    assert rest.files_restored == 1
    assert (mb / "z.md").read_text(encoding="utf-8") == "orig"


def _log_two_session_entries(wal_dir: Path) -> None:
    """Seed one entry for ``current-session`` and one for ``other-session``."""
    log = ToolInvocationLog(wal_dir)
    log.log(
        wal_build_tool_invocation_entry(
            session_id="current-session",
            tool_name="run_quality_gate",
            arg_keys=[],
            status=WalStatus.OK,
            error_type=None,
        )
    )
    log.log(
        wal_build_tool_invocation_entry(
            session_id="other-session",
            tool_name="memory_wal",
            arg_keys=["operation"],
            status=WalStatus.OK,
            error_type=None,
        )
    )


def test_memory_wal_tool_invocations_returns_current_session_slice(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "p"
    _log_two_session_entries(root / ".cortex" / "wal")

    # Act
    with patch(
        "cortex.tools.memory.wal_tool.wal_agent_hint",
        return_value="current-session",
    ):
        res = handle_memory_wal_sync(
            root,
            MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS),
        )

    # Assert: only the current session's tool-call sequence surfaces.
    assert res.tool_invocations is not None
    assert len(res.tool_invocations) == 1
    assert res.tool_invocations[0].tool_name == "run_quality_gate"


def test_memory_wal_tool_invocations_empty_session_returns_empty_list(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "p"

    # Act
    with patch(
        "cortex.tools.memory.wal_tool.wal_agent_hint",
        return_value="unused-session",
    ):
        res = handle_memory_wal_sync(
            root,
            MemoryWALInput(operation=MemoryWalToolOp.TOOL_INVOCATIONS),
        )

    # Assert
    assert res.tool_invocations == []


def test_memory_wal_read_last_50_cap(tmp_path: Path) -> None:
    root = tmp_path / "p"
    wal_dir = root / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    lines = "\n".join(
        WALEntryJsonFactory.minimal_line(i, f"2026-04-15T12:{i % 60:02d}:00+00:00")
        for i in range(55)
    )
    _ = (wal_dir / "write_log.jsonl").write_text(lines + "\n", encoding="utf-8")
    res = handle_memory_wal_sync(
        root,
        MemoryWALInput(operation=MemoryWalToolOp.READ, since=None),
    )
    assert res.entries is not None
    assert len(res.entries) == 50


class TestMemoryWalAsOf:
    """``as_of`` exposes hash-verified historical views to the analyze pipeline."""

    def test_as_of_returns_reconstructed_content(self, tmp_path: Path) -> None:
        # Arrange
        from cortex.memory.wal import MemoryWAL, WalContentFields, wal_build_entry
        from cortex.memory.wal_content import wal_encode_reverse_delta

        rel = ".cortex/memory-bank/a.md"
        payload, codec = wal_encode_reverse_delta(True, "before")
        entry = wal_build_entry(
            operation=WalOperation.WRITE,
            relative_file=rel,
            agent_hint="t",
            before_exists=True,
            before_text="before",
            after_text="after",
            status=WalStatus.OK,
            error=None,
            content_fields=WalContentFields(
                reverse_delta=payload, delta_codec=codec, step_number=4
            ),
        )
        MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path).log(entry)
        # Act
        result = handle_memory_wal_sync(
            tmp_path,
            MemoryWALInput(operation=MemoryWalToolOp.AS_OF, file=rel, step_number=1),
        )
        # Assert
        assert result.as_of is not None
        assert result.as_of.content == "before"
        assert result.as_of.verified is True

    def test_as_of_requires_file_and_step_number(self, tmp_path: Path) -> None:
        # Arrange
        missing_file = MemoryWALInput(operation=MemoryWalToolOp.AS_OF, step_number=1)
        missing_step = MemoryWALInput(operation=MemoryWalToolOp.AS_OF, file="a.md")
        # Act / Assert
        with pytest.raises(ValueError, match="non-empty file"):
            _ = handle_memory_wal_sync(tmp_path, missing_file)
        with pytest.raises(ValueError, match="step_number"):
            _ = handle_memory_wal_sync(tmp_path, missing_step)
