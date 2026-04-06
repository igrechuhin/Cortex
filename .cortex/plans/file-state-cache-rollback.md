---
title: "File State Cache and Rollback"
component: pipeline
work_type: feature
status: PENDING
priority: medium
created: 2026-04-06
depends_on: []
---

## File State Cache and Rollback

## Goal

Add a lightweight file snapshot mechanism to Cortex: before a pipeline phase edits files, snapshot the affected paths. If the phase fails or the user requests rollback, restore the snapshots. Pure file I/O — no git dependency, no external packages.

## Context

- Cortex pipelines (`/cortex/do`, `/cortex/fix`) can edit multiple files across several phases. A mid-pipeline failure leaves files in a partially-modified state with no recovery path.
- Claude Code tracks `FileStateCache` + git history to enable undo. Cortex implements a simpler, MCP-compatible version: snapshot files to `.cortex/.session/{session_id}/snapshots/` before edits, restore on demand.
- Sessions already have a `.cortex/.session/{session_id}/` directory managed by `pipeline_handoff_io.py`.

## Implementation Steps

### Step 1: Define `FileSnapshot` model

**File**: `src/cortex/core/file_snapshot.py` (new, ≤ 120 lines)

```python
class FileSnapshot(BaseModel):
    path: Path
    content: str
    encoding: str
    snapshot_at: str   # ISO-8601
    existed: bool      # False if file did not exist at snapshot time
```

- `FileSnapshot.from_path(path: Path) -> FileSnapshot` — reads file; if missing, `existed=False, content=""`.
- `FileSnapshot.restore() -> None` — writes content back; if `existed=False` deletes file if it now exists.

**Verification**: grep `FileSnapshot`; read the file.

### Step 2: `FileStateCache` — session-scoped snapshot store

**File**: `src/cortex/core/file_snapshot.py` (same file, second class)

```python
class FileStateCache:
    def __init__(self, session_dir: Path) -> None: ...
    def snapshot(self, paths: list[Path]) -> str: ...        # returns snapshot_id
    def restore(self, snapshot_id: str) -> list[Path]: ...   # returns restored paths
    def list_snapshots(self) -> list[str]: ...
    def drop(self, snapshot_id: str) -> None: ...
    def drop_all(self) -> None: ...
```

- Storage: `{session_dir}/snapshots/{snapshot_id}/{encoded_path}.json`
- `snapshot_id` = `datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")` — sortable, unique within session.
- `encoded_path`: `path.as_posix().replace("/", "__")`

**Verification**: grep `FileStateCache`; read class methods.

### Step 3: Integrate with pipeline session directory

**File**: `src/cortex/tools/session/pipeline_handoff_io.py`

- Add `get_file_state_cache(session_id: str, project_root: Path) -> FileStateCache`.

**Verification**: grep `get_file_state_cache`.

### Step 4: Expose `snapshot` and `rollback` via `pipeline_handoff`

**File**: `src/cortex/tools/session/pipeline_handoff.py`

- `operation="snapshot"`: takes `paths: list[str]` → returns `{"snapshot_id": "..."}`.
- `operation="rollback"`: takes `snapshot_id: str` → returns `{"restored": [...]}`.
- Zero-arg safe: missing `paths` returns an error message.

**Verification**: grep `"snapshot"` and `"rollback"` in `pipeline_handoff.py`.

### Step 5: Session cleanup on deregister

**File**: `src/cortex/tools/session/dispatcher.py`

- In `deregister` branch: call `FileStateCache.drop_all()` if snapshot dir exists.

**Verification**: grep `drop_all` in `dispatcher.py`.

### Step 6: Tests

**File**: `tests/unit/core/test_file_snapshot.py` (new)

- `TestFileSnapshot::test_from_path_existing`
- `TestFileSnapshot::test_from_path_nonexistent`
- `TestFileSnapshot::test_restore_existing`
- `TestFileSnapshot::test_restore_creates_deleted_file`
- `TestFileSnapshot::test_restore_deletes_new_file`
- `TestFileStateCache::test_snapshot_creates_files`
- `TestFileStateCache::test_restore_returns_paths`
- `TestFileStateCache::test_list_snapshots_chronological`
- `TestFileStateCache::test_drop_removes_snapshot`
- `TestFileStateCache::test_drop_all_clears_cache`
- `TestPipelineHandoff::test_snapshot_operation`
- `TestPipelineHandoff::test_rollback_operation`

Coverage target: 95%+.

## Dependencies

- No external dependencies beyond Python stdlib.
- Internal: `pipeline_handoff_io.py`, `dispatcher.py`.

## Success Criteria

1. `pipeline_handoff(operation="snapshot", paths=[...])` returns a `snapshot_id`.
2. `pipeline_handoff(operation="rollback", snapshot_id="...")` restores all snapshotted files.
3. Session deregister cleans up snapshot files.
4. All 12 tests pass; coverage ≥ 95%.
5. No regression in existing `pipeline_handoff` tests.

## Testing Strategy

- All tests use `tmp_path` — no mocking of file I/O.
- AAA pattern throughout.
- Run via `run_quality_gate()` after implementation.
