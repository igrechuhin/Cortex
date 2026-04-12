---
title: "Wiki Auto-Update as Commit Pipeline Step"
component: wiki
work_type: feature
status: COMPLETE
priority: medium
created: 2026-04-07
updated: 2026-04-11
depends_on:
  - project-wiki-attached-projects.md
---

## Wiki Auto-Update as Commit Pipeline Step

## Goal

When `/cortex/commit` stages and commits changes that include doc files (README, ADR, design doc, CHANGELOG), the commit pipeline automatically ingests the changed files into the project wiki **before** staging — so wiki updates are committed atomically alongside the source changes. No git hooks, no dirty workspace, no separate commit for wiki pages.

## Context

A post-commit git hook approach was considered and rejected: it would leave `.cortex/wiki/` files unstaged after every commit touching a doc, requiring a follow-up commit just for wiki updates. Integrating wiki update into the `/cortex/commit` pipeline solves this cleanly:

1. Phase A passes (quality gate).
2. **New step**: detect staged doc files → ingest into wiki → stage wiki pages.
3. Phase B (docs gate) re-runs with wiki changes included.
4. Phase C: commit + push — wiki pages land in the same commit as the source change.

The wiki stays current, the workspace stays clean, and history stays linear.

## Implementation Steps

### Step 1: Define doc file patterns for wiki ingest

Create `src/cortex/tools/wiki/auto_ingest_config.py` with default patterns:

```python
DEFAULT_AUTO_INGEST_PATTERNS = [
    "README*.md",
    "docs/**/*.md",
    "adr-*.md",
    "ADR-*.md",
    "CHANGELOG.md",
    "ARCHITECTURE.md",
    "*.design.md",
]
```

These are configurable via `.cortex/wiki/schema.md` frontmatter:

```yaml
auto_ingest_patterns:
  - "docs/**/*.md"
  - "adr-*.md"
```

**Verification**: Import `DEFAULT_AUTO_INGEST_PATTERNS`; confirm list is non-empty and patterns compile as globs.

### Step 2: Implement `wiki_ingest_staged_docs` helper

Create `src/cortex/tools/wiki/staged_ingest.py`:

```python
async def wiki_ingest_staged_docs(
    staged_files: list[str],
    project_root: str,
) -> WikiIngestResult
```

Logic:

1. Load auto-ingest patterns from `.cortex/wiki/schema.md` (fall back to defaults).
2. Filter `staged_files` to those matching any pattern.
3. For each matched file:
   a. Read the file content.
   b. Call `ingest()` tool with `source_type="markdown_file"`, `content=content`, `title=<derived from H1 or filename>`.
   c. Ingest flow runs: summary page created/updated, `index.md` updated, cross-references maintained.
4. Return `WikiIngestResult(ingested: list[str], skipped: list[str], errors: list[str], wiki_files_written: list[str])`.

The `wiki_files_written` field lists the `.cortex/wiki/` paths written so the commit pipeline can stage them.

**Verification**: Call `wiki_ingest_staged_docs(staged_files=["docs/auth.md"], project_root="...")` → ingest runs, returns `wiki_files_written` with at least one path.

### Step 3: Wire into `/cortex/commit` pipeline between Phase A and Phase B

Update the `/cortex/commit` Synapse prompt:

1. After Phase A passes, read staged files via `git diff --cached --name-only`.
2. Call `wiki_ingest_staged_docs()` with the staged file list.
3. If `wiki_files_written` is non-empty:
   a. Stage the wiki files: `git add .cortex/wiki/`.
   b. Log: `Wiki updated: N pages ingested, staged.`
4. Proceed to Phase B (docs gate). Phase B now validates the commit including the newly staged wiki pages.
5. Phase C commits everything atomically.

If `wiki_files_written` is empty (no staged doc files matched patterns), skip silently.

**Verification**: Stage `docs/auth.md`, run `/cortex/commit`; wiki pages appear in `git diff --cached` after the wiki step; final commit includes both `docs/auth.md` and the wiki pages.

### Step 4: Idempotency — update existing wiki pages, don't duplicate

1. When `ingest()` is called with a file that was previously ingested (same slug):
   - Detect the existing summary page.
   - Diff the new content against the old source.
   - If content changed: update the summary page, append a `## Revision` section with the diff summary.
   - If content unchanged: no-op (return `skipped`).
2. The raw source in `sources/` is updated to the new version (versioned by appending `-v2`, `-v3`, etc. for history).

**Verification**: Ingest `docs/auth.md` twice with different content; second ingest updates the page and adds a `## Revision` section; no duplicate page created.

## Partial Progress Log

- 2026-04-12: Steps 1–2 — `DEFAULT_AUTO_INGEST_PATTERNS`, optional YAML `auto_ingest_patterns` in `.cortex/wiki/schema.md`, `load_auto_ingest_patterns`, `paths_matching_patterns`, sync `ingest_source_at_project_root` in `ingest_handler`, `wiki_ingest_staged_docs` with `WikiStagedIngestResult`; unit tests — files: `src/cortex/tools/wiki/`, `src/cortex/tools/ingest/ingest_handler.py`, `tests/unit/test_wiki_auto_ingest_config.py`, `tests/unit/test_wiki_staged_ingest.py`
- 2026-04-12: Step 3 — `/cortex/commit` Synapse prompt: after Phase A, run `wiki_ingest_staged_docs` on `git diff --cached --name-only` output, `git add` returned wiki paths, stop on errors; sequential execution order updated — files: `.cortex/synapse/prompts/commit.md`
- 2026-04-12: Step 4 (partial) — Idempotent staged ingest: stable slug from repo-relative path, unchanged body short-circuits, content changes archive prior raw to `*-v{n}.md` and append `## Revision` on summary page — files: `src/cortex/tools/ingest/ingest_handler.py`, `src/cortex/tools/ingest/stable_path_ingest.py`, `src/cortex/tools/ingest/source_types.py`, `src/cortex/tools/ingest/slug.py`, `src/cortex/wiki/ingest_wiki.py`, `src/cortex/tools/wiki/staged_ingest.py`, `tests/unit/test_wiki_staged_ingest.py`, `tests/tools/test_ingest_tool.py`

## Dependencies

- `project-wiki-attached-projects.md` — wiki must exist for ingest to run
- `memory-bank-ingest-tool.md` — `ingest()` tool is the ingest primitive

## Success Criteria

- Staging and committing `docs/auth.md` via `/cortex/commit` results in wiki pages in the same commit
- No dirty workspace after commit — wiki files are staged and committed atomically
- Files not matching auto-ingest patterns are silently skipped
- Re-ingesting an unchanged file is a no-op (no duplicate pages, no spurious wiki files staged)
- Re-ingesting a changed file updates the summary page with a revision note
- Works when Cortex is attached to itself: committing a `.cortex/synapse/prompts/*.md` change updates Cortex's own wiki in the same commit
- 95%+ test coverage on `wiki_ingest_staged_docs` and idempotency logic

## Testing Strategy

- Unit tests for pattern matching: each default pattern matches expected files, misses non-doc files
- Unit tests for `wiki_ingest_staged_docs`: matched files ingested, unmatched skipped, errors returned for unreadable files, `wiki_files_written` populated correctly
- Unit tests for idempotency: same content → no-op; changed content → revision section added
- Integration test: stage `docs/auth.md`, run commit pipeline → wiki page and source file in same commit
- Integration test: stage `src/foo.py` only → no wiki ingest triggered, pipeline unaffected
- Self-hosting test: Cortex attached to Cortex; commit a `.cortex/synapse/prompts/` change → Cortex wiki updated in same commit
