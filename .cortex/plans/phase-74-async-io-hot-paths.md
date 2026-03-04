# Phase 74: Async I/O Migration for Hot Paths

## Status

PENDING

## Goal

Migrate synchronous file I/O to async equivalents in the highest-impact code paths, and add parallel file reading to context loading.

## Context

The code review (2026-03-04) identified:

- **HIGH**: 25+ locations use synchronous file I/O (`open()`, `os.path.exists()`, `Path.read_text()`) inside async functions, blocking the event loop
- **HIGH**: Context files are loaded sequentially instead of using `asyncio.gather()` for parallel I/O

This is a systemic issue. This plan focuses on the **hot paths** (context loading, cache access, session management) rather than attempting a full codebase migration.

## Approach

Phase 1: Migrate hot-path async functions to use `aiofiles` or `asyncio.to_thread()`. Phase 2: Add parallel file reading with `asyncio.gather()` to context loading.

## Implementation Steps

### Step 1: Identify hot-path async functions with sync I/O

- Audit context loading, cache access, and session management modules
- Catalog each sync I/O call in an async function
- Prioritize by call frequency and latency impact

### Step 2: Migrate context loading to async I/O

- Replace `open()` / `Path.read_text()` with `aiofiles.open()` in context loading modules
- Replace `os.path.exists()` with `aiofiles.os.path.exists()` or `asyncio.to_thread()`

### Step 3: Add parallel file reading to context loading

- Replace sequential file reading loop with `asyncio.gather()`
- Add concurrency limit (e.g., `asyncio.Semaphore(10)`) to prevent file descriptor exhaustion
- Measure context loading time before/after

### Step 4: Migrate cache access to async I/O

- Replace sync file reads/writes in cache modules with async equivalents

### Step 5: Migrate session management to async I/O

- Replace sync file operations in session modules with async equivalents

### Step 6: Add tests

- Test async file operations work correctly
- Test parallel file reading with various file counts
- Test concurrency limit enforcement
- Benchmark context loading time improvement

## Dependencies

- Phase 73 (event loop blocking fixes should land first)

## Success Criteria

- Zero sync file I/O in hot-path async functions (context loading, cache, session)
- Context loading uses parallel I/O with `asyncio.gather()`
- Measurable reduction in context loading time
- 95%+ test coverage for changed code

## Testing Strategy

- **Unit Tests**: Async file read/write, parallel loading, semaphore limiting
- **Integration Tests**: Full context loading cycle with async I/O
- **Edge Cases**: Missing files, permission errors, concurrent access, file descriptor limits
- **Performance**: Measure before/after context loading time
- **Coverage Target**: 95%+ for modified modules

## Risks & Mitigation

- **Risk**: aiofiles may behave differently from sync file I/O in edge cases
- **Mitigation**: Test with same edge cases as existing sync tests; keep sync fallback for error paths
- **Risk**: Too many parallel reads may exhaust file descriptors
- **Mitigation**: Use `asyncio.Semaphore` to cap concurrent reads

## Timeline

Medium-High effort (8-16h)
