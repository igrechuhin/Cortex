# Phase 71: Fix TOCTOU Race Conditions in File and Task Locking

## Status

PENDING

## Goal

Eliminate time-of-check-to-time-of-use race conditions in file-based locking and task locking to prevent data corruption under concurrent access.

## Context

The code review (2026-03-04) identified two related race condition bugs:

- **HIGH**: TOCTOU in file lock acquisition (`core/file_system.py`, `core/cache_json_access.py`) — check-then-act pattern with a window between check and act
- **HIGH**: Non-atomic task locking (`tools/session/task_locking.py`) — multi-step lock protocol without atomicity guarantees

These affect multi-agent scenarios where concurrent processes can corrupt shared state.

## Approach

Replace check-then-act patterns with atomic operations using POSIX advisory locking (`fcntl.flock()`) or atomic file creation (`O_CREAT | O_EXCL`).

## Implementation Steps

### Step 1: Fix file-based locking in core/file_system.py

- Replace check-then-act with `fcntl.flock()` for atomic lock acquisition
- Add retry logic with exponential backoff for lock contention
- Add lock timeout to prevent deadlocks

### Step 2: Fix cache JSON access in core/cache_json_access.py

- Use atomic file operations for cache read-write
- Ensure read-modify-write cycles are protected by advisory locks

### Step 3: Fix task locking in tools/session/task_locking.py

- Implement atomic lock acquisition using `O_CREAT | O_EXCL`
- Add lock owner identification (PID + timestamp)
- Add stale lock detection and cleanup for crashed processes

### Step 4: Add tests

- Concurrent lock acquisition tests (multi-process)
- Lock timeout and contention tests
- Stale lock detection and cleanup tests
- Cache corruption prevention under concurrent access

## Dependencies

None.

## Success Criteria

- Lock acquisition is atomic in all three modules
- No TOCTOU window exists between check and act
- Stale locks from crashed processes are detected and cleaned up
- Concurrent agents cannot acquire the same lock
- 95%+ test coverage for changed code

## Testing Strategy

- **Unit Tests**: Lock acquire/release, timeout, stale detection
- **Integration Tests**: Multi-process concurrent lock contention
- **Edge Cases**: Crashed process with held lock, lock timeout expiry, simultaneous lock attempts, disk full during lock creation
- **Coverage Target**: 95%+ for modified modules

## Risks & Mitigation

- **Risk**: Cross-platform differences in lock semantics (macOS vs Linux `flock` behavior)
- **Mitigation**: Test on both platforms; use `fcntl.flock()` which has consistent POSIX semantics
- **Risk**: Stale lock cleanup may incorrectly remove active locks
- **Mitigation**: Include PID liveness check before cleanup; add grace period

## Timeline

Medium effort (4-8h)
