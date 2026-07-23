"""Unit tests for :mod:`cortex.memory.wal`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.memory.wal import (
    MemoryWAL,
    ToolInvocationEntry,
    ToolInvocationLog,
    WALEntry,
    WalOperation,
    WalStatus,
    wal_build_entry,
    wal_build_tool_invocation_entry,
    wal_redact_arg_keys,
    wal_short_hash,
)


def test_wal_entry_builds() -> None:
    e = wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file=".cortex/memory-bank/x.md",
        agent_hint="test",
        before_exists=False,
        before_text="",
        after_text="hello",
        status=WalStatus.OK,
        error=None,
    )
    assert len(e.id) == 12
    assert e.content_hash_before == "none"
    assert e.byte_delta == len("hello".encode("utf-8"))
    assert e.after_byte_len == len("hello".encode("utf-8"))


def test_memory_wal_log_read_roundtrip(tmp_path: Path) -> None:
    wal_dir = tmp_path / "wal"
    root = tmp_path / "proj"
    (root / ".cortex" / "memory-bank").mkdir(parents=True)
    _ = (root / ".cortex" / "memory-bank" / "a.md").write_text("x", encoding="utf-8")
    wal = MemoryWAL(wal_dir, project_root=root)
    entry = wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file=".cortex/memory-bank/a.md",
        agent_hint="u",
        before_exists=True,
        before_text="x",
        after_text="xy",
        status=WalStatus.OK,
        error=None,
    )
    wal.log(entry)
    log_path = wal_dir / "write_log.jsonl"
    assert log_path.is_file()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = WALEntry.model_validate_json(lines[0])
    assert parsed.operation == WalOperation.WRITE


def _burst_entry(index: int) -> WALEntry:
    return WALEntry(
        id=f"{index:012d}",
        timestamp=f"2026-04-15T12:00:{index:02d}+00:00",
        operation=WalOperation.WRITE,
        file=".cortex/memory-bank/same.md",
        agent_hint="x",
        content_hash_before="none" if index == 0 else "aa",
        content_hash_after="bb",
        byte_delta=1,
        after_byte_len=2,
        status=WalStatus.OK,
        error=None,
    )


def test_detect_anomalies_shrink_and_burst(tmp_path: Path) -> None:
    wal_dir = tmp_path / "wal"
    wal = MemoryWAL(wal_dir)
    ts = "2026-04-15T12:00:00+00:00"
    big_before = "a" * 1000
    small_after = "b" * 100
    shrink_entry = WALEntry(
        id="0" * 12,
        timestamp=ts,
        operation=WalOperation.WRITE,
        file=".cortex/memory-bank/r.md",
        agent_hint="x",
        content_hash_before="abc",
        content_hash_after="def",
        byte_delta=len(small_after.encode("utf-8")) - len(big_before.encode("utf-8")),
        after_byte_len=len(small_after.encode("utf-8")),
        status=WalStatus.OK,
        error=None,
    )
    wal.log(shrink_entry)
    warns = wal.detect_anomalies()
    assert any("large shrink" in w for w in warns)

    wal2_dir = tmp_path / "wal2"
    wal2 = MemoryWAL(wal2_dir)
    for i in range(12):
        wal2.log(_burst_entry(i))
    burst = wal2.detect_anomalies()
    assert any("burst" in b for b in burst)


def test_snapshot_restore(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    mb = root / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (mb / "f.md").write_text("one", encoding="utf-8")
    wal_dir = root / ".cortex" / "wal"
    wal = MemoryWAL(wal_dir, project_root=root)
    snap = wal.snapshot("s1")
    assert snap.is_dir()
    _ = (mb / "f.md").write_text("two", encoding="utf-8")
    n = wal.restore("s1")
    assert n == 1
    assert (mb / "f.md").read_text(encoding="utf-8") == "one"


def test_restore_missing_raises(tmp_path: Path) -> None:
    wal = MemoryWAL(tmp_path / "wal", project_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        _ = wal.restore("nope")


def test_read_since_filter(tmp_path: Path) -> None:
    wal = MemoryWAL(tmp_path / "wal")
    early = wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file="a",
        agent_hint="u",
        before_exists=False,
        before_text="",
        after_text="1",
        status=WalStatus.OK,
        error=None,
    )
    wal.log(early)
    late = WALEntry(
        id="1" * 12,
        timestamp="2099-01-01T00:00:00+00:00",
        operation=WalOperation.WRITE,
        file="a",
        agent_hint="u",
        content_hash_before="none",
        content_hash_after=wal_short_hash("2"),
        byte_delta=1,
        after_byte_len=1,
        status=WalStatus.OK,
        error=None,
    )
    wal.log(late)
    filtered = wal.read(since="2099-01-01")
    assert len(filtered) == 1


def test_wal_build_tool_invocation_entry_redacts_and_caps_arg_keys() -> None:
    # Arrange
    raw_keys = [f"key_{i}" for i in range(30)]

    # Act
    entry = wal_build_tool_invocation_entry(
        session_id="s1",
        tool_name="run_quality_gate",
        arg_keys=raw_keys,
        status=WalStatus.OK,
        error_type=None,
    )

    # Assert
    assert len(entry.id) == 12
    assert entry.tool_name == "run_quality_gate"
    assert len(entry.arg_keys) == 20
    assert entry.arg_keys == raw_keys[:20]
    assert entry.error_type is None


def test_wal_redact_arg_keys_caps_count_and_length() -> None:
    # Arrange
    raw_keys = [f"very_long_key_name_{i}" * 10 for i in range(25)]

    # Act
    redacted = wal_redact_arg_keys(raw_keys)

    # Assert
    assert len(redacted) == 20
    assert all(len(k) <= 80 for k in redacted)


def test_tool_invocation_entry_never_persists_arg_values() -> None:
    # Arrange
    entry = wal_build_tool_invocation_entry(
        session_id="s1",
        tool_name="write_artifact",
        arg_keys=["content", "name"],
        status=WalStatus.OK,
        error_type=None,
    )

    # Act
    raw = json.loads(entry.model_dump_json())

    # Assert: only key names are present, never their would-be values.
    assert raw["arg_keys"] == ["content", "name"]
    assert "SECRET" not in json.dumps(raw)


def test_tool_invocation_log_append_only_ordering(tmp_path: Path) -> None:
    # Arrange
    log = ToolInvocationLog(tmp_path / "wal")
    first = wal_build_tool_invocation_entry(
        session_id="s1",
        tool_name="tool_a",
        arg_keys=["x"],
        status=WalStatus.OK,
        error_type=None,
    )
    second = wal_build_tool_invocation_entry(
        session_id="s1",
        tool_name="tool_b",
        arg_keys=[],
        status=WalStatus.ERROR,
        error_type="ValueError",
    )

    # Act
    log.log(first)
    log.log(second)
    entries = log.read()

    # Assert: append-only, order preserved, no in-place mutation of prior lines.
    assert [e.tool_name for e in entries] == ["tool_a", "tool_b"]
    assert entries[1].status == WalStatus.ERROR
    assert entries[1].error_type == "ValueError"


def test_tool_invocation_log_read_filters_by_session(tmp_path: Path) -> None:
    # Arrange
    log = ToolInvocationLog(tmp_path / "wal")
    log.log(
        wal_build_tool_invocation_entry(
            session_id="s1",
            tool_name="tool_a",
            arg_keys=[],
            status=WalStatus.OK,
            error_type=None,
        )
    )
    log.log(
        wal_build_tool_invocation_entry(
            session_id="s2",
            tool_name="tool_b",
            arg_keys=[],
            status=WalStatus.OK,
            error_type=None,
        )
    )

    # Act
    session_slice = log.read(session_id="s1")

    # Assert
    assert [e.tool_name for e in session_slice] == ["tool_a"]


def test_tool_invocation_log_read_empty_session_returns_empty_list(
    tmp_path: Path,
) -> None:
    # Arrange
    log = ToolInvocationLog(tmp_path / "wal")

    # Act
    entries = log.read(session_id="unused-session")

    # Assert
    assert entries == []


def test_tool_invocation_entry_model_validate_json_roundtrip() -> None:
    # Arrange
    entry = wal_build_tool_invocation_entry(
        session_id="s1",
        tool_name="memory_wal",
        arg_keys=["operation"],
        status=WalStatus.OK,
        error_type=None,
    )

    # Act
    parsed = ToolInvocationEntry.model_validate_json(entry.model_dump_json())

    # Assert
    assert parsed == entry


def test_wal_json_includes_after_byte_len_roundtrip() -> None:
    e = wal_build_entry(
        operation=WalOperation.APPEND,
        relative_file=".cortex/memory-bank/log.md",
        agent_hint="u",
        before_exists=True,
        before_text="ab",
        after_text="abcd",
        status=WalStatus.OK,
        error=None,
    )
    raw = json.loads(e.model_dump_json())
    assert raw["after_byte_len"] == len("abcd".encode("utf-8"))
