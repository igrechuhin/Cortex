---
title: "File Review Reports into Memory Bank"
component: memory-bank
work_type: feature
status: PENDING
priority: high
created: 2026-04-07
depends_on: []
---

## File Review Reports into Memory Bank

## Goal

When a `/cortex/review` or `/cortex/analyze` session produces a valuable output (review report, session analysis, architectural finding), automatically file that output as a named page in the memory bank — not just into `.cortex/history/` where it disappears from agent context. Filed pages are cross-referenced from `activeContext.md` so they compound into the project's knowledge base.

## Context

Cortex currently writes review reports to `.cortex/history/` (e.g., `activeContext_v11.md`, `progress_v11.md`). These are versioned snapshots but they are **not cross-referenced** from the living memory bank. When a future agent reads `cortex://context` it doesn't see "we reviewed the auth module on 2026-04-07 and found X" unless someone manually added that to `activeContext.md`.

Karpathy's LLM-wiki pattern makes this explicit: **good answers should be filed back into the wiki as new pages**. A comparison you asked for, an analysis, a connection you discovered — these shouldn't disappear into chat history.

Applied to Cortex: every review report, session analysis, and architectural finding that rises above a quality threshold should be filed as a named memory-bank page and cross-referenced.

## Implementation Steps

### Step 1: Define "fileable artifact" types

Create `src/cortex/tools/artifacts/artifact_types.py` with:

```python
class ArtifactType(str, Enum):
    REVIEW_REPORT = "review_report"
    SESSION_ANALYSIS = "session_analysis"
    ARCHITECTURAL_FINDING = "architectural_finding"
    QUERY_RESULT = "query_result"       # for future wiki query results
```

Each type maps to:

- A default storage location (e.g., `review_report` → `.cortex/memory-bank/reviews/`)
- A naming convention (e.g., `review-{slug}-{date}.md`)
- A summary format for cross-reference entries

**Verification**: Import `ArtifactType`; confirm enum values and their metadata are accessible.

### Step 2: Add `file_artifact` operation to `manage_file`

1. Read `src/cortex/tools/files/manage_file_helpers.py`.
2. Add `operation="file_artifact"` that:
   - Accepts `artifact_type: ArtifactType`, `title: str`, `content: str`, `tags: list[str] | None`
   - Writes the artifact to the correct subdirectory under `.cortex/memory-bank/`
   - Creates the subdirectory if it doesn't exist
   - Returns the path of the written file
3. Add `FileArtifactParams` Pydantic model.

**Verification**: Call `manage_file(operation="file_artifact", artifact_type="review_report", title="Auth Review", content="...")` → file appears in `.cortex/memory-bank/reviews/`.

### Step 3: Auto-cross-reference in `activeContext.md`

After `file_artifact` writes a file:

1. Append a one-line cross-reference entry to `activeContext.md`:

   ```text
   - [Auth Review](reviews/review-auth-2026-04-07.md) — Review of auth module; 3 bugs found, 2 architectural concerns.
   ```

2. Use `update_memory_bank(operation="active_context_append")` internally.
3. The cross-reference is a markdown link relative to `.cortex/memory-bank/`.

**Verification**: After `file_artifact`, read `activeContext.md`; confirm new markdown link appears.

### Step 4: Wire into `/cortex/review` prompt

1. Read `.cortex/synapse/prompts/review.md` or the review pipeline prompts.
2. At the end of the review pipeline (after `review-performance` step), add:
   - If the overall review score ≥ 7/10: call `manage_file(operation="file_artifact", artifact_type="review_report", ...)` with the full report content.
   - Log the filing to `log.md` via `update_memory_bank(operation="log_append")` (non-blocking if log feature not yet implemented).
3. The threshold (7/10) is configurable via `.cortex/lint-config.json` → `review_filing_threshold`.

**Verification**: Run `/cortex/review` on a test file with score ≥ 7; confirm report filed under `.cortex/memory-bank/reviews/`.

### Step 5: Wire into `/cortex/analyze` prompt

1. After the analyze pipeline completes, call `file_artifact` with `artifact_type="session_analysis"` and the assembled report.
2. Always file session analyses (no threshold — these are always valuable).

**Verification**: Run `/cortex/analyze`; confirm session analysis filed under `.cortex/memory-bank/analyses/`.

### Step 6: Update `cortex://context` resource to surface recent artifacts

1. Read `src/cortex/resources/context.py`.
2. Add a `## Recent Artifacts` section listing the 5 most recently modified files under `.cortex/memory-bank/reviews/` and `.cortex/memory-bank/analyses/` with their one-line descriptions.

**Verification**: After filing an artifact, call `cortex://context`; confirm `## Recent Artifacts` section appears.

## Dependencies

- `memory-bank-operations-log.md` plan (for `log_append` calls in Step 4) — non-blocking; skip log calls if not implemented
- No other hard dependencies

## Success Criteria

- Review reports with score ≥ threshold are filed as named pages in `.cortex/memory-bank/reviews/`
- Session analyses are always filed in `.cortex/memory-bank/analyses/`
- Each filed artifact is cross-referenced in `activeContext.md` as a markdown link
- `cortex://context` surfaces the 5 most recent artifacts
- 95%+ test coverage on `file_artifact` operation

## Testing Strategy

- Unit tests for `file_artifact`: correct path, correct naming convention, creates subdirectory, returns path
- Unit tests for cross-reference append: verify markdown link format, relative path correctness
- Integration test: full `/cortex/review` run → artifact filed when score ≥ threshold, not filed when below
- Integration test: full `/cortex/analyze` run → session analysis always filed
- Edge cases: `reviews/` dir doesn't exist (auto-created), duplicate titles (filename deduplication via counter suffix)
