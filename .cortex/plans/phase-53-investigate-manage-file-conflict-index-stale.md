## Phase 53: Investigate `manage_file` conflict due to stale index

### Problem

`manage_file(operation="write")` can fail with `FileConflictError` (“modified externally… expected hash … got …”) when `.cortex/index.json` metadata is stale relative to the actual file on disk.

In this session, `manage_file(operation="metadata")` for `roadmap.md` reported:

- `content_hash`: `sha256:cceef...`
- `size_bytes`: `22117`
- `last_modified`: `2026-01-16...`

But the actual file on disk had:

- `sha256:9cef...`
- `35820` bytes

This blocks any future `manage_file(write)` operations for the affected file(s), because there is **no documented override/force flag** in the tool schema.

### Observations

- `check_structure_health(perform_cleanup=True, cleanup_actions=["update_index"], dry_run=False)` reported success but did **not** show any performed actions and did not refresh metadata.
- `manage_file(read)` succeeds even with a mismatch, but `manage_file(write)` fails due to the mismatch.

### Expected Behavior

One of the following should be true:

- `update_index` cleanup action refreshes `.cortex/index.json` to match current disk state, or
- `manage_file(write)` provides a safe “accept external change / rebase” flow (e.g., include the current disk hash in request or an explicit force flag), or
- there is a documented repair tool (e.g., detect external changes) that updates metadata safely.

### Reproduction Steps (Minimal)

1. Modify a memory bank file directly on disk (outside MCP) after it has been indexed.
2. Call `manage_file(operation="metadata")` and observe stale `content_hash`/`size_bytes`.
3. Call `manage_file(operation="write")` and observe `FileConflictError`.
4. Attempt `check_structure_health(... cleanup_actions=["update_index"] ...)` and observe no effect on metadata.

### Proposed Fix Directions

- **Option A (preferred)**: Make `update_index` action actually refresh `.cortex/index.json` and any related metadata caches for memory-bank files.
- **Option B**: Add `expected_content_hash` to `manage_file(write)` (optimistic concurrency), letting callers supply the disk hash they read.
- **Option C**: Add `force_write=True` (explicit, audit-logged) to allow updating index after external edits.

### Acceptance Criteria

- After running a documented repair action, `manage_file(write)` succeeds without requiring manual file rollback.
- `manage_file(metadata)` reflects actual file size/hash on disk after repair.
- Tests cover: stale index detection, repair path, and successful write after repair.
