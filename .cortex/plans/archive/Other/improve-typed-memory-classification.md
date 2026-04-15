---
title: "Improvement: Typed Memory Classification for Memory Bank Entries"
component: memory-bank
work_type: improvement
status: PENDING
priority: medium
created: 2026-04-14
depends_on: []
---

## Goal

Classify every memory bank write into one of five typed buckets — **decision**, **preference**, **milestone**, **problem**, **status** — and tag each entry with its type. This enables targeted retrieval ("show me all decisions about auth"), better context scoring, and richer session summaries without requiring any LLM API calls.

Inspired by MemPalace's `general_extractor.py` which classifies memories using pure regex heuristics and achieves 90%+ accuracy at zero API cost.

## Context

## Current behaviour

`manage_file(operation="write", ...)` and `update_memory_bank(operation="...")` write raw markdown. All entries are treated identically — a preference ("always use Pydantic 2") and a milestone ("FastMCP v3 baseline merged") look the same to the retrieval layer.

## Problems this causes

1. Context loading has no way to prioritize decisions over status updates.
2. Preferences (recurring guidance) are hard to distinguish from one-time observations.
3. Session summaries mix everything together, making it hard to scan for what changed.
4. Without typed entries, contradiction detection (temporal plan) has no category signal.

## Target behaviour

Every memory write is automatically classified into one of five types using heuristic matching:

| Type | Trigger patterns | Example |
|------|-----------------|---------|
| `decision` | "decided", "chose", "switched to", "will use", "we agreed" | "decided to migrate to FastMCP v3" |
| `preference` | "always", "never", "prefer", "avoid", "policy" | "always use Pydantic BaseModel for tool returns" |
| `milestone` | "completed", "merged", "done", "shipped", "achieved", "fixed" | "FastMCP v3 baseline merged" |
| `problem` | "failed", "broke", "bug", "error", "blocked", "issue" | "startup crash when structured-output enabled" |
| `status` | everything else | "3 plans PENDING, 0 BLOCKED" |

Type is stored as a YAML frontmatter tag on each entry's markdown block and also indexed by the temporal store (if present).

## Implementation Steps

## Step 1: Define memory types

File: `src/cortex/memory/memory_types.py` (new file)

1. Create `MemoryType` enum: `DECISION`, `PREFERENCE`, `MILESTONE`, `PROBLEM`, `STATUS`.
2. Create `MEMORY_TYPE_PATTERNS: dict[MemoryType, list[str]]` mapping each type to its trigger keyword list (case-insensitive, whole-word match preferred).
3. Create `classify_text(text: str) -> MemoryType` pure function:
   - Check each type's patterns in priority order: DECISION > PREFERENCE > MILESTONE > PROBLEM > STATUS.
   - Return first match; default to `STATUS` if none.
   - Must be ≤ 20 lines, no I/O, no regex compilation at call time (compile at module load).
4. Create `MemoryEntry(BaseModel)` with fields: `content: str`, `memory_type: MemoryType`, `tags: list[str] = []`, `created: str`.

**Verification**: Unit test — `classify_text("we decided to use FastMCP v3")` returns `DECISION`; `classify_text("always use Pydantic")` returns `PREFERENCE`; unknown text returns `STATUS`.

## Step 2: Add tag injection to `manage_file` write path

File: `src/cortex/tools/memory/manage_file.py` (existing)

1. Before writing, call `classify_text(content)` to determine memory type.
2. If writing a new section (append mode), prepend the markdown block with:

   ```text
   <!-- memory_type: decision -->
   ```

   as an HTML comment (invisible in rendered markdown, parseable by grep/regex).
3. Do NOT modify existing content — only new appended blocks get the tag.
4. Add `skip_classification: bool = False` parameter for callers that want to bypass (e.g., bulk imports).
5. Keep changes ≤ 15 lines in the existing write handler.

**Verification**: `manage_file(operation="write", content="we decided to use X")` — re-read the file and assert `<!-- memory_type: decision -->` appears before the written block.

## Step 3: Add tag injection to `update_memory_bank`

File: `src/cortex/tools/memory/update_memory_bank.py` (existing) or the handler that processes `roadmap_add`, `progress_add`, `active_add`.

1. For each `entry_text` argument, classify and prepend the type comment before the entry.
2. Same `skip_classification: bool = False` escape hatch.
3. Keep changes ≤ 10 lines.

**Verification**: `update_memory_bank(operation="active_add", entry_text="completed the migration")` — read activeContext.md and assert `<!-- memory_type: milestone -->` present.

## Step 4: Implement typed memory reader

File: `src/cortex/memory/typed_reader.py` (new file)

1. `TypedMemoryReader` class with `read_by_type(file_path: Path, memory_type: MemoryType) -> list[MemoryEntry]`.
2. Parse markdown file: extract blocks that have `<!-- memory_type: {type} -->` comment.
3. Also `read_all(file_path: Path) -> list[MemoryEntry]` — returns all tagged entries.
4. Fallback: entries without type comment are classified in-memory via `classify_text()` and returned with inferred type.
5. Return empty list for non-existent file (no raise).

**Verification**: Unit test — synthetic markdown file with 3 tagged entries; `read_by_type(path, DECISION)` returns only decision entries.

## Step 5: Expose typed retrieval in `manage_file`

File: `src/cortex/tools/memory/manage_file.py` (existing)

1. Add `operation="read_by_type"` with `content={"file_name": "...", "memory_type": "decision"}`.
2. Delegates to `TypedMemoryReader.read_by_type(...)`.
3. Returns serialized `list[MemoryEntry]` as JSON string in response.

**Verification**: `manage_file(operation="read_by_type", content='{"file_name": "activeContext.md", "memory_type": "milestone"}')` returns only milestone entries.

## Step 6: Enrich session summary with type counts

File: `src/cortex/tools/session/brief.py` (existing, minimal touch)

1. During `session(operation="start")`, after reading memory bank, call `TypedMemoryReader.read_all()` on activeContext.md.
2. Compute type distribution: `{"decision": N, "preference": N, "milestone": N, "problem": N, "status": N}`.
3. Append a one-line summary to the session response: `Memory: 12 decisions, 8 preferences, 5 milestones, 3 problems`.
4. Add `"memory_type_counts": {...}` field to session JSON output.
5. Keep changes ≤ 10 lines.

**Verification**: `session(operation="start")` response contains `memory_type_counts` field with at least one non-zero value.

## Step 7: Integrate with L1 context scoring (if layered context plan is active)

File: `src/cortex/resources/context/l1_essential.py` (from layered context plan, if exists)

1. When scoring paragraphs for L1, boost score by type weight:
   - DECISION: +3.0
   - PREFERENCE: +2.5
   - PROBLEM: +2.0
   - MILESTONE: +1.5
   - STATUS: +0.0
2. If layered context plan is not yet merged, skip this step — mark as DEFERRED.

**Verification**: Unit test with mixed-type paragraphs; assert DECISION paragraphs rank above STATUS paragraphs when other scores are equal.

## Step 8: Tests

Files:

- `tests/memory/test_memory_types.py`
- `tests/memory/test_typed_reader.py`
- `tests/tools/memory/test_manage_file_classification.py`

1. Unit: `classify_text` for all 5 types; edge cases (empty string, multi-sentence, ambiguous).
2. Unit: `TypedMemoryReader` parse, fallback classification, empty file.
3. Integration: write via `manage_file` → read_by_type → assert correct type tag present.
4. Regression: existing `manage_file` callers still work; `skip_classification=True` bypasses tagging.

## Dependencies

- No blocking dependencies.
- Optional integration with layered context plan (Step 7) — deferred if that plan not yet merged.
- Complements temporal memory plan: `MemoryType` can be passed as `category` field in `TemporalFact`.

## Success Criteria

- [ ] `classify_text()` achieves correct classification for all 5 types with the standard pattern list.
- [ ] New writes via `manage_file` and `update_memory_bank` are automatically tagged.
- [ ] `manage_file(operation="read_by_type")` returns correctly filtered entries.
- [ ] Session start response includes `memory_type_counts`.
- [ ] All new files ≤ 400 lines, all functions ≤ 30 lines, no `Any` types.
- [ ] 95%+ test coverage for new modules.
- [ ] No breaking change to existing `manage_file` API — `skip_classification=False` default is backwards-compatible.

## Testing Strategy

- **Unit**: `classify_text` exhaustive patterns; `TypedMemoryReader` with synthetic markdown.
- **Integration**: Full write→tag→read cycle via `manage_file`.
- **Regression**: Existing memory bank files without type comments still readable; session start unaffected.
- Target: 95% line coverage for `memory_types.py`, `typed_reader.py`, and the modified handler methods.
