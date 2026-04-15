"""Tests for ``memory_wal`` MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

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
