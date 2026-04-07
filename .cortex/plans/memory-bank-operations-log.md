---
title: "Memory Bank Operations Log (log.md)"
component: memory-bank
work_type: feature
status: PENDING
priority: high
created: 2026-04-07
depends_on: []
---

## Memory Bank Operations Log (log.md)

## Goal

Add an append-only `log.md` file to `.cortex/memory-bank/` that records every significant memory-bank operation chronologically. Each entry uses a consistent parseable prefix so recent history is queryable with simple tools. This gives agents (and humans) a timeline of what happened without reading the full memory bank.

## Context

Cortex has `progress.md` (project-level milestones) and `activeContext.md` (session-level summaries), but no **chronological operations log**. When an agent starts a session it can't easily answer "what happened in the last 3 sessions?" without reading multiple files and correlating timestamps.

Karpathy's LLM-wiki pattern highlights that a `log.md` with parseable `## [date] operation | title` prefix entries makes history queryable with `grep "^## \[" log.md | tail -5`. Applied to Cortex: every ingest, plan creation, quality gate run, and memory-bank mutation gets a log entry.

The log is the **audit trail**; `activeContext.md` remains the **semantic summary**.

## Implementation Steps

### Step 1: Add `log.md` to memory-bank schema

1. Read `src/cortex/tools/files/manage_file_helpers.py` and `src/cortex/core/constants.py` (or wherever allowed memory-bank filenames are defined).
2. Add `"log.md"` to the list of allowed/recognized memory-bank files.
3. Define the canonical entry format:

   ```text
   ## [YYYY-MM-DD HH:MM] {operation} | {title}
   {1–3 line summary. Optional.}
   ```

   Where `operation` is one of: `ingest`, `plan`, `commit`, `review`, `fix`, `analyze`, `lint`.

**Verification**: grep for the constants/allowed-files list; confirm `log.md` appears after change.

### Step 2: Add `log_append` operation to `update_memory_bank`

1. Read `src/cortex/tools/plans/update_memory_bank.py`.
2. Add a new `operation="log_append"` branch:
   - Parameters: `operation_type: str`, `title: str`, `summary: str | None`, `date_str: str | None` (defaults to `date` shell call).
   - Creates `log.md` if it doesn't exist (with a `# Cortex Operations Log` header).
   - Appends the formatted entry at the end of the file.
   - Never rewrites existing entries.
3. Add `LogAppendParams` Pydantic model alongside the existing params models.
4. Update the `UpdateMemoryBankParams` union to include `LogAppendParams`.

**Verification**: Search for existing `operation=` branches in the file; confirm `log_append` is wired correctly.

### Step 3: Wire log_append calls into existing operations

Add `log_append` calls (non-blocking, fire-and-forget on failure) at:

1. `plan(operation="create")` — after successful plan file creation.
2. `plan(operation="complete")` — after archiving.
3. `update_memory_bank(operation="progress_append")` — after writing progress entry.
4. `run_quality_gate` — after gate completes (pass or fail summary).
5. `autofix` — after autofix run.

**Verification**: Run each operation in a test; confirm `log.md` gains a new entry with correct format.

### Step 4: Expose log in `cortex://context` resource

1. Read `src/cortex/resources/context.py` (or equivalent resource handler).
2. Add a `## Recent Operations` section that includes the last 10 lines of `log.md` (if it exists).
3. This gives agents immediate recency context without reading the full log.

**Verification**: Call `cortex://context` resource; confirm `## Recent Operations` section appears.

### Step 5: Update `manage_file` to support `log.md` reads

Ensure `manage_file(file_name="log.md", operation="read")` works and returns the file content. No special handling needed beyond adding `log.md` to the allowed list (Step 1).

**Verification**: Call `manage_file(file_name="log.md", operation="read")`; confirm it returns content.

## Dependencies

- None (foundational; other plans may depend on this)

## Success Criteria

- `log.md` is created automatically on first log_append call
- Each entry is parseable: `grep "^## \[" .cortex/memory-bank/log.md` returns dated entries
- Last 10 entries appear in `cortex://context` under `## Recent Operations`
- No existing memory-bank files are affected
- 95%+ test coverage on `log_append` operation

## Testing Strategy

- Unit tests for `log_append` operation: creates file on first call, appends on subsequent calls, never overwrites, correct date formatting
- Unit test: `log.md` not in allowed list raises error before this plan; in allowed list passes after
- Integration test: run `plan(operation="create")` in test harness → verify `log.md` gains an entry
- Integration test: `cortex://context` includes `## Recent Operations` when `log.md` exists; omits section when absent
- Edge cases: `log.md` with 0 entries, 1 entry, 1000 entries; concurrent appends (file lock)
