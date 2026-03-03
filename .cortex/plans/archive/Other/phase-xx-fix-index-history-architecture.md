# Phase XX: Remove version_history from index.json

## Status

Status: PENDING

## Problem Statement

`index.json` is a 3 MB, 75K-line tracked file because `version_history` arrays grow without bound (`progress.md` has 3,266 entries, `activeContext.md` has 3,239). This bloat causes git merge conflicts and makes the index hard to reason about.

`version_history` in `index.json` is entirely redundant:

- **Rollback** doesn't use it — `get_snapshot_path()` computes paths deterministically as `{base_name}_v{version}.md`
- **Version listing** could scan `.cortex/history/` on disk instead
- **Snapshot paths** point to gitignored local files — dead on any other machine

## Design Decision

**Remove `version_history` from `index.json` entirely.** History is local, ephemeral, and derivable from disk. The index should only contain current file metadata (hash, size, tokens, sections).

- `version_history` field: removed from serialized `index.json`
- `current_version`: kept (needed to assign next version number)
- Rollback: works from disk snapshots via `get_snapshot_path()` (already does this)
- Version listing: scan `.cortex/history/{base}_v*.md` files, read metadata from snapshot content or file timestamps
- `.cortex/history/`: remains gitignored, local safety net, pruned by existing `prune_versions()`

## Multi-machine behavior

With `version_history` gone from the tracked index:

- **No merge conflicts** from history data — `index.json` shrinks from 75K lines to ~200 lines of current-state metadata
- **On clone**: Empty `.cortex/history/`, `current_version` in index tells the next version number. No dead pointers.
- **Rollback**: Only available for local snapshots. `get_snapshot_path()` checks disk — if file exists, rollback works; if not, clear error. No index consultation needed.
- **Version listing**: Scans local `.cortex/history/` — only shows what's actually available on this machine

## Implementation Steps

### Step 1: Stop writing version_history to index.json

In `metadata_cache.py` (`add_version_to_history_impl`): stop appending to `version_history`. Keep updating `current_version`.

**Files**: `src/cortex/core/metadata_cache.py`

### Step 2: Remove version_history from index schema

Remove `version_history` from `DetailedFileMetadata` model (or make it excluded from serialization). Keep the field in-memory if any code path still reads it during a session, but don't persist it.

**Files**: `src/cortex/core/models/_metadata.py`, `src/cortex/core/metadata_cache.py`

### Step 3: Rewrite get_version_history to scan disk

Replace `foundation_version.py`'s `_get_version_history_impl` to:

1. Scan `.cortex/history/{base}_v*.md` for existing snapshots
2. Extract version number from filename
3. Use file mtime for timestamp, file size for size_bytes
4. Return available versions

This makes `get_version_history` show only what's actually recoverable.

**Files**: `src/cortex/tools/memory/foundation_version.py`

### Step 4: Clean up consumers

- `export_version_history` in `version_manager.py`: rewrite to scan disk
- `rollback_execution.py`: already uses `get_snapshot_path()` in the helper; remove any fallback to index-based lookup
- `crud_operations.py` read flow: stop including `version_history` in read responses (or derive from disk)
- `version_snapshots.py` (refactoring): adapt `find_snapshot_version` to work from disk scan

**Files**: `src/cortex/core/version_manager.py`, `src/cortex/refactoring/rollback_execution.py`, `src/cortex/tools/files/crud_operations.py`, `src/cortex/refactoring/version_snapshots.py`

### Step 5: One-time index cleanup

On startup or first write, strip existing `version_history` arrays from `index.json`. This is the migration — just drop the field from persisted data.

### Step 6: Consider lowering keep_versions default

Current default is 10. For a session safety net, 3-5 may be sufficient. Lower if no code path uses versions older than the last 3.

## Testing Strategy

- **Unit tests**: After writes, `index.json` contains no `version_history` field; `current_version` still increments correctly
- **Unit tests**: `get_version_history` returns correct results from disk scan; returns empty list when `.cortex/history/` is missing
- **Unit tests**: Rollback works from disk snapshots without consulting index history
- **Regression**: Existing write, read, rollback, and refactoring flows continue to work
- **Coverage**: >=95% for changed code in version_manager, metadata_cache, foundation_version

## What This Plan Replaces

This single plan replaces:

- The former `phase-xx-fix-index-history-architecture.md` (8-step, 3-option architecture evaluation)
- The former `phase-yy-history-retention-keep-versions.md` (8-step retention policy with age-based pruning)

The actual fix: stop persisting redundant data that's already on disk.
