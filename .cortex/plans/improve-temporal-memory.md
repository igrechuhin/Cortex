---
title: "Improvement: Temporal Memory with Validity Windows"
component: memory-bank
work_type: improvement
status: PENDING
priority: high
created: 2026-04-14
depends_on: []
---

## Goal

Add temporal validity to memory bank entries so agents can query "what was true on date X" rather than only seeing current state. Every memory fact gets `valid_from` and `valid_to` fields; facts can be invalidated (ended) without deletion. Historical queries reconstruct past project state accurately.

Inspired by MemPalace's knowledge graph temporal model which uses SQLite for local, zero-cost entity-relationship storage with time-filtered queries.

## Context

## Current behaviour

Memory bank entries (activeContext.md, progress.md, roadmap.md) are append-only flat markdown files. When a decision changes, the old entry is either overwritten or left as a stale duplicate with no way to know when it became outdated. Agents reading the memory bank cannot distinguish "current" from "historical".

## Problems this causes

1. Stale plans remain PENDING in roadmap after being superseded — agents pick them as "next step" incorrectly.
2. After migrations (e.g., FastMCP v2 → v3), old implementation notes still appear in context.
3. No way to ask "what did we decide about X in March?" — the answer is buried in git history or lost.

## Target behaviour

A lightweight SQLite-backed temporal store (`TemporalMemoryStore`) wraps the existing memory bank:

- Each meaningful fact carries `valid_from: date` and optional `valid_to: date`.
- Invalidating a fact sets `valid_to` without deleting the row.
- `query_as_of(date)` returns only facts valid at that date.
- The memory bank markdown files remain the source of truth for human reading; the temporal store is an index over them.
- New MCP tool `memory_timeline` surfaces this to agents.

Inspired by MemPalace's approach where `kg.invalidate("Maya", "assigned_to", "auth-migration", ended="2026-02-01")` creates a closed interval without data loss.

## Implementation Steps

## Step 1: Design the temporal store schema

File: `src/cortex/memory/temporal_store.py` (new file)

1. Create SQLite table `memory_facts` with columns:
   - `id TEXT PRIMARY KEY` — deterministic hash of `(category + subject + predicate + object)`
   - `category TEXT` — e.g., "decision", "assignment", "status", "preference"
   - `subject TEXT` — entity being described (plan slug, component name, person)
   - `predicate TEXT` — relationship type ("assigned_to", "status", "depends_on")
   - `object TEXT` — value
   - `valid_from TEXT` — ISO date string
   - `valid_to TEXT NULLABLE` — NULL means "still valid"
   - `source_file TEXT` — memory bank file that originated this fact
   - `source_line INT` — line number in source file
   - `created_at TEXT` — when this row was inserted
2. Create `TemporalFact(BaseModel)` mirroring the schema.
3. Create `TemporalMemoryStore` class with `__init__(db_path: Path)` that runs `CREATE TABLE IF NOT EXISTS`.
4. DB path: `.cortex/temporal.db`.
5. Keep `__init__` under 20 lines; use a class-level `_CREATE_SQL` constant for the DDL.

**Verification**: `TemporalMemoryStore(db_path=tmp_path / "test.db")` creates the file and table without errors.

## Step 2: Implement core CRUD operations

File: `src/cortex/memory/temporal_store.py` (same file, continue)

1. `add_fact(fact: TemporalFact) -> None` — INSERT OR IGNORE (idempotent via deterministic ID).
2. `invalidate(subject: str, predicate: str, object: str, ended: str) -> bool` — UPDATE `valid_to = ended` WHERE `subject/predicate/object` AND `valid_to IS NULL`; return True if row found.
3. `query_as_of(date: str, subject: str | None = None, category: str | None = None) -> list[TemporalFact]` — SELECT where `valid_from <= date AND (valid_to IS NULL OR valid_to > date)`; optional subject/category filters.
4. `current_facts(subject: str | None = None) -> list[TemporalFact]` — shorthand for `query_as_of(today, subject)`.
5. Each method ≤ 25 lines; use parameterized queries only (no string interpolation — SQL injection prevention).

**Verification**: Unit test — add fact, query_as_of before valid_from returns empty; query_as_of during validity returns fact; after invalidate, query_as_of returns empty.

## Step 3: Implement memory bank indexer

File: `src/cortex/memory/temporal_indexer.py` (new file)

1. `TemporalIndexer` class accepts `TemporalMemoryStore` and `project_root: Path`.
2. `index_file(file_path: Path) -> int` — parse markdown file and extract facts:
   - Roadmap entries: `subject=plan_slug`, `predicate="status"`, `object=status_word` (PENDING/DONE/etc.), `category="status"`, `valid_from=today`.
   - Plan frontmatter: `depends_on` list → `predicate="depends_on"` facts.
   - activeContext entries with `completed:` date → `valid_to` set.
3. `index_all() -> dict[str, int]` — index all memory bank files; return `{filename: facts_added}`.
4. Extraction is best-effort: unknown formats are skipped, not errored.
5. Re-indexing a file is safe (idempotent inserts via deterministic IDs).

**Verification**: Unit test — index a synthetic roadmap.md with 3 PENDING entries; assert 3 "status" facts inserted.

## Step 4: Add contradiction detection

File: `src/cortex/memory/temporal_indexer.py` (same file, add method)

1. `check_contradiction(new_fact: TemporalFact) -> list[TemporalFact]` — query for existing open facts with same `subject+predicate` but different `object`; return conflicting facts.
2. When `index_file` finds a new fact, call `check_contradiction`; if conflicts found, log a warning (do not raise — best-effort detection only).
3. Warning format: `[temporal] Possible contradiction: {subject}.{predicate} = {new_object} conflicts with open fact {old_object} (since {valid_from})`.

**Verification**: Unit test — insert fact A for `subject=plan, predicate=status, object=PENDING`; try to insert fact B `object=DONE` without invalidating A; assert contradiction returned.

## Step 5: Implement `memory_timeline` MCP tool

File: `src/cortex/tools/memory/timeline.py` (new file)

Tool name: `memory_timeline`

1. Input schema `MemoryTimelineInput(BaseModel)`:
   - `subject: str | None = None` — filter by entity
   - `category: str | None = None` — filter by category
   - `as_of: str | None = None` — ISO date for historical query; defaults to today
   - `show_invalidated: bool = False` — include expired facts
2. `handle(input: MemoryTimelineInput) -> MemoryTimelineResult`:
   - Open `TemporalMemoryStore(.cortex/temporal.db)`.
   - If `show_invalidated=True`, query all facts for subject; otherwise `query_as_of(as_of)`.
   - Return `MemoryTimelineResult(facts: list[TemporalFact], queried_as_of: str, total: int)`.
3. Register in tool registry as `memory_timeline`.

**Verification**: Integration test — index a fixture memory bank; call tool with `subject="fastmcp-v3-phase2"`; assert facts returned include status.

## Step 6: Add invalidation support to `manage_file`

File: `src/cortex/tools/memory/manage_file.py` (existing)

1. When `manage_file(operation="write", ...)` updates a file:
   - After writing, call `TemporalIndexer.index_file(path)` to update the temporal store.
2. Add `operation="invalidate_fact"` with `content={"subject": ..., "predicate": ..., "object": ..., "ended": ...}` — delegates to `TemporalMemoryStore.invalidate(...)`.
3. Keep the new code path ≤ 20 lines; do not alter existing write path logic.

**Verification**: Write a synthetic roadmap entry via `manage_file`; then read `TemporalMemoryStore.current_facts()` and assert the fact is indexed.

## Step 7: Wire temporal store into session startup

File: `src/cortex/tools/session/brief.py` (existing, minimal touch)

1. During session start (`session(operation="start")`), after reading memory bank files, call `TemporalIndexer(store, project_root).index_all()` asynchronously (fire-and-forget — do not block session response).
2. Log the result: `[temporal] Indexed {total} facts from {n} files`.
3. If `TemporalMemoryStore` fails to open (permission error, etc.), log warning and continue — do not fail session start.

**Verification**: Session start completes even when `temporal.db` cannot be created (mock permission error); log contains warning but no exception raised.

## Step 8: Tests

Files:

- `tests/memory/test_temporal_store.py`
- `tests/memory/test_temporal_indexer.py`
- `tests/tools/memory/test_memory_timeline.py`

1. Unit: CRUD operations, idempotency, invalidation, `query_as_of` boundary conditions.
2. Unit: Indexer parses roadmap entries, detects contradictions, handles unknown formats.
3. Integration: `memory_timeline` tool returns correct facts for synthetic memory bank.
4. Regression: `session()` start still completes when temporal store is unavailable.

## Dependencies

- No blocking dependencies.
- If layered context plan lands first, L1 essential story generator can use `TemporalMemoryStore.current_facts()` to score paragraphs by recency.

## Success Criteria

- [ ] `TemporalMemoryStore` CRUD operations are idempotent and use parameterized SQL.
- [ ] `index_all()` successfully indexes roadmap.md and activeContext.md without errors.
- [ ] `memory_timeline` tool registered and callable via MCP.
- [ ] `query_as_of("2026-01-01")` returns only facts valid on that date.
- [ ] Contradiction detection logs warnings for conflicting open facts.
- [ ] All new files ≤ 400 lines, all functions ≤ 30 lines, no `Any` types.
- [ ] 95%+ test coverage for new modules.
- [ ] Session start not blocked if temporal store fails to open.

## Testing Strategy

- **Unit**: SQLite CRUD, idempotency via deterministic IDs, temporal boundary queries, contradiction detection.
- **Integration**: Index real `.cortex/memory-bank/` fixture; assert `fastmcp-v3-phase2` status fact present.
- **Regression**: Session start with mocked `TemporalMemoryStore` failure; assert no exception propagates.
- Target: 95% line coverage for all new files.
