---
title: "Improvement: Memory Write-Ahead Log for Audit Trail and Rollback"
component: memory-bank
work_type: improvement
status: PENDING
priority: medium
created: 2026-04-14
depends_on: []
---

## Goal

Add a write-ahead log (WAL) that records every memory bank mutation — writes, updates, deletions, and roadmap additions — to a structured JSONL file. The WAL enables three capabilities: audit trail (what changed, when, from which agent), poisoning detection (unexpected writes from untrusted sources), and snapshot-based rollback (restore memory bank to a prior state).

Inspired by MemPalace's WAL implementation which logs all `add_drawer` / `delete_drawer` operations and enables rollback for agent-written memories.

## Context

## Current behaviour

`manage_file(operation="write")` and `update_memory_bank(...)` mutate `.cortex/memory-bank/` files directly with no record of what was changed. When a memory bank file becomes corrupted or incorrectly updated (e.g., by a misbehaving agent), there is no way to know what changed or revert it without digging through git history.

## Problems this causes

1. Multiple concurrent agents (6 active sessions noted in the current session report) write to the same files without coordination — writes can be lost or overwritten silently.
2. "Memory poisoning" — an agent writing incorrect facts — is undetectable.
3. Rollback requires `git checkout` which discards all intervening changes, including correct ones.
4. No audit trail for "who wrote what and when" across agent sessions.

## Target behaviour

Every memory bank mutation is appended to `.cortex/wal/write_log.jsonl` before the write completes. Each entry records:

- `timestamp`, `operation`, `file`, `agent_hint` (session ID or caller context), `content_hash_before`, `content_hash_after`, `status` (success/fail).

A `MemoryWAL` class provides:

- `log(...)` — append a WAL entry (atomic write, newline-delimited JSON).
- `read(since: str | None) -> list[WALEntry]` — read entries optionally filtered by timestamp.
- `detect_anomalies() -> list[str]` — heuristics to flag suspicious writes (e.g., roadmap.md shrunk by > 20%).
- `snapshot(label: str) -> Path` — copy all memory bank files to `.cortex/wal/snapshots/{label}/`.
- `restore(label: str) -> int` — copy snapshot back to memory bank; return number of files restored.

## Implementation Steps

## Step 1: Define WAL entry schema

File: `src/cortex/memory/wal.py` (new file)

1. Create `WALEntry(BaseModel)`:
   - `id: str` — `uuid4().hex[:12]`
   - `timestamp: str` — ISO 8601, UTC, always via `datetime.now(UTC).isoformat()`
   - `operation: str` — one of: `"write"`, `"append"`, `"roadmap_add"`, `"active_add"`, `"progress_add"`, `"delete"`
   - `file: str` — relative path from project root (e.g., `.cortex/memory-bank/activeContext.md`)
   - `agent_hint: str` — session ID if available, else `"unknown"`
   - `content_hash_before: str` — `sha256(before_content)[:16]` or `"none"` if file didn't exist
   - `content_hash_after: str` — `sha256(after_content)[:16]`
   - `byte_delta: int` — `len(after_bytes) - len(before_bytes)`
   - `status: str` — `"ok"` or `"error"`, set after the write completes
   - `error: str | None = None`
2. No I/O in this file — pure data model.

**Verification**: `WALEntry(id="abc", ...)` instantiates without error; all fields have correct types.

## Step 2: Implement `MemoryWAL`

File: `src/cortex/memory/wal.py` (same file, continue)

1. `MemoryWAL` class:
   - `__init__(wal_dir: Path)`: create `wal_dir` if not exists; set `_log_path = wal_dir / "write_log.jsonl"`.
   - `log(entry: WALEntry) -> None`: open file in append mode, write `entry.model_dump_json() + "\n"`, fsync. Must be atomic: write to `tmp` file first, then `os.replace(tmp, log)` — POSIX atomic.
   - `read(since: str | None = None) -> list[WALEntry]`: read all lines, parse each as `WALEntry`, filter by `timestamp >= since` if set.
   - `detect_anomalies() -> list[str]`: check last 50 entries; flag if: any file shrank by > 30% in a single write, same file written > 10 times in 60 seconds, any write with `status="error"`.
   - `snapshot(label: str) -> Path`: copy all `.cortex/memory-bank/*.md` to `.cortex/wal/snapshots/{label}/`; return snapshot dir path.
   - `restore(label: str) -> int`: copy snapshot files back to memory bank; return count. Fail loudly if label doesn't exist.
2. Each method ≤ 25 lines.
3. No external dependencies — stdlib only (`hashlib`, `shutil`, `os`, `uuid`, `datetime`).

**Verification**: `MemoryWAL(tmp_path / "wal").log(entry)` creates the JSONL file; `read()` returns the entry; `detect_anomalies()` returns empty list for normal writes.

## Step 3: Integrate WAL into `manage_file` write path

File: `src/cortex/tools/memory/manage_file.py` (existing)

1. At the start of any mutating operation (`write`, `append`, etc.):
   - Record `content_hash_before` (read file if exists, else `"none"`).
   - Execute the write.
   - Record `content_hash_after`.
   - Call `MemoryWAL(project_root / ".cortex/wal").log(WALEntry(...))`.
2. If WAL logging fails (disk full, permission error), log a warning and continue — do NOT fail the write operation. WAL is advisory.
3. Extract session ID from the active session config for `agent_hint`; fallback to `"unknown"`.
4. Keep new code ≤ 20 lines in the write handler.

**Verification**: Write a value via `manage_file`; assert `.cortex/wal/write_log.jsonl` exists and contains one valid JSON line.

## Step 4: Integrate WAL into `update_memory_bank`

File: `src/cortex/tools/memory/update_memory_bank.py` (existing)

1. Same pattern as Step 3 — wrap each mutation with pre/post hash capture and WAL append.
2. Use `operation` value from the tool input as the WAL `operation` field.
3. Keep new code ≤ 15 lines.

**Verification**: `update_memory_bank(operation="roadmap_add", ...)` adds a WAL entry with `operation="roadmap_add"`.

## Step 5: Add `memory_wal` MCP tool

File: `src/cortex/tools/memory/wal_tool.py` (new file)

Tool name: `memory_wal`

1. Input schema `MemoryWALInput(BaseModel)`:
   - `operation: str` — `"read"`, `"anomalies"`, `"snapshot"`, `"restore"`
   - `since: str | None = None` — for `read`
   - `label: str | None = None` — for `snapshot` / `restore`
2. `handle(input: MemoryWALInput) -> MemoryWALResult`:
   - `"read"` → `MemoryWAL.read(since)` — return last 50 entries if `since` not set
   - `"anomalies"` → `MemoryWAL.detect_anomalies()` — return list of warning strings
   - `"snapshot"` → `MemoryWAL.snapshot(label)` — label defaults to current timestamp
   - `"restore"` → `MemoryWAL.restore(label)` — requires `label`
3. `MemoryWALResult(BaseModel)`: `operation: str`, `entries: list[WALEntry] | None`, `warnings: list[str] | None`, `snapshot_path: str | None`, `files_restored: int | None`.
4. Register as `memory_wal` in tool registry.

**Verification**: `memory_wal(operation="anomalies")` returns successfully with `warnings` field present.

## Step 6: Pre-compact hook integration

File: `.claude/hooks/` or `src/cortex/hooks/pre_compact.py` (check existing hook infrastructure)

1. Before context compaction (Claude Code `PreCompact` hook), call `memory_wal(operation="snapshot", label="pre-compact-{timestamp}")`.
2. This ensures a snapshot exists before the context window shrinks, enabling recovery if compaction causes memory bank drift.
3. If no hook infrastructure exists, document this as a manual step in the WAL tool's docstring.

**Verification**: Snapshot directory created at `.cortex/wal/snapshots/pre-compact-{timestamp}/` after hook fires.

## Step 7: Tests

Files:

- `tests/memory/test_wal.py`
- `tests/tools/memory/test_wal_tool.py`
- `tests/tools/memory/test_manage_file_wal.py`

1. Unit: `MemoryWAL.log` atomicity (tmp file + replace); `read` parsing; `detect_anomalies` triggers.
2. Unit: `snapshot` copies correct files; `restore` overwrites and returns count; missing label raises `FileNotFoundError`.
3. Integration: Write via `manage_file` → read WAL → assert entry present with correct operation and hashes.
4. Regression: WAL logging failure (mock disk full) does not fail the underlying write.

## Dependencies

- No blocking dependencies.
- Complements temporal memory plan — `TemporalIndexer` can use WAL entries as source timestamps.
- Complements typed memory plan — WAL entries provide the `agent_hint` field for attribution.

## Success Criteria

- [ ] Every `manage_file` write appends a WAL entry.
- [ ] Every `update_memory_bank` mutation appends a WAL entry.
- [ ] `memory_wal(operation="snapshot", label="...")` creates a valid snapshot directory.
- [ ] `memory_wal(operation="restore", label="...")` restores files from snapshot.
- [ ] `detect_anomalies()` returns a warning when a file shrinks > 30% in one write.
- [ ] WAL logging failure (disk full) does not fail the underlying write operation.
- [ ] All new files ≤ 400 lines, all functions ≤ 30 lines, no `Any` types.
- [ ] 95%+ test coverage for new modules.

## Testing Strategy

- **Unit**: Atomic write (tmp+replace); JSONL parsing; anomaly heuristics; snapshot/restore with temp dirs.
- **Integration**: Full write → WAL → read → anomaly cycle with real memory bank files.
- **Regression**: `manage_file` and `update_memory_bank` unaffected when WAL logging raises.
- Target: 95% line coverage for `wal.py` and `wal_tool.py`.
