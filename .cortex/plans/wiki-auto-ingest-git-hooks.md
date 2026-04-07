---
title: "Auto-Ingest from Git Hooks (Wiki Auto-Update)"
component: wiki
work_type: feature
status: PENDING
priority: medium
created: 2026-04-07
depends_on:
  - project-wiki-attached-projects.md
  - hook-conditional-dsl.md
---

## Auto-Ingest from Git Hooks (Wiki Auto-Update)

## Goal

When a commit adds or modifies a doc file (README, ADR, design doc, CHANGELOG), a Cortex post-commit hook automatically ingests the changed file into the project wiki. No manual `/cortex/ingest` call needed — the wiki stays current as the codebase evolves.

## Context

The LLM-wiki pattern's long-term value depends on the wiki staying current. Manual ingest requires discipline; hooks make it automatic. When Cortex's `hook-conditional-dsl.md` plan is implemented, hooks can fire only on relevant file patterns — `FileEdit(docs/**)`, `FileEdit(*.md)`, `FileEdit(adr-*.md)` — avoiding false triggers on code changes.

When Cortex is attached to itself, this means every time a `.cortex/synapse/prompts/*.md` or `docs/*.md` file is committed, the Cortex wiki is automatically updated with the new content.

## Implementation Steps

### Step 1: Define doc file patterns for auto-ingest

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

These are configurable via `.cortex/wiki-schema.md` frontmatter:

```yaml
auto_ingest_patterns:
  - "docs/**/*.md"
  - "adr-*.md"
```

**Verification**: Import `DEFAULT_AUTO_INGEST_PATTERNS`; confirm list is non-empty and patterns compile as globs.

### Step 2: Implement `wiki_auto_ingest` hook handler

Create `src/cortex/hooks/wiki_auto_ingest.py`:

```python
async def wiki_auto_ingest(
    changed_files: list[str],    # from hook event payload
    project_root: str,
    ctx: MCPContext | None = None,
) -> ModelDict
```

Logic:

1. Load auto-ingest patterns from `.cortex/wiki-schema.md` (fall back to defaults).
2. Filter `changed_files` to those matching any pattern.
3. For each matched file:
   a. Read the file content.
   b. Call `ingest()` tool with `source_type="markdown_file"`, `content=content`, `title=<derived from H1 or filename>`.
   c. The ingest flow (prompt-driven) runs: summary page created/updated, index updated, cross-references maintained.
4. Return `AutoIngestResult(ingested: list[str], skipped: list[str], errors: list[str])`.

**Verification**: Call `wiki_auto_ingest(changed_files=["docs/auth.md"], project_root="...")` → ingest runs for `docs/auth.md`.

### Step 3: Register as a post-commit hook

1. Read `src/cortex/setup/claude_settings.py` and existing hook registration patterns.
2. Add a hook entry to the default hook configuration:

   ```json
   {
     "type": "command",
     "event": "PostToolUse",
     "matcher": "Bash(git commit*)",
     "command": "cortex wiki-auto-ingest --changed-files {changed_files}"
   }
   ```

3. The hook uses the conditional DSL from `hook-conditional-dsl.md` plan — it fires only on `Bash(git commit*)` events.
4. When `hook-conditional-dsl.md` is not yet implemented, fall back to a simpler post-commit git hook in `.git/hooks/post-commit` (shell script that calls `cortex wiki-auto-ingest`).

**Verification**: Commit a doc file change; confirm `wiki_auto_ingest` is called and the wiki is updated.

### Step 4: Add `cortex wiki-auto-ingest` CLI entry point

1. Read `src/cortex/cli.py` (or main entry point).
2. Add a `wiki-auto-ingest` subcommand that:
   - Reads changed files from `git diff --name-only HEAD~1 HEAD` (or accepts `--changed-files` argument)
   - Calls `wiki_auto_ingest()` handler
   - Prints a brief summary: `Ingested: docs/auth.md → wiki/concepts/auth.md`
3. The CLI is what the hook script calls.

**Verification**: Run `cortex wiki-auto-ingest` after a commit with a doc change; correct output printed.

### Step 5: Idempotency — update existing wiki pages, don't duplicate

1. When `ingest()` is called with a file that was previously ingested (same slug):
   - Detect the existing summary page.
   - Diff the new content against the old source.
   - If content changed: update the summary page, append a `## Revision` section with the diff summary.
   - If content unchanged: no-op (return `skipped`).
2. The raw source in `sources/` is updated to the new version (versioned by appending `-v2`, `-v3`, etc. for history).

**Verification**: Ingest `docs/auth.md` twice with different content; second ingest updates the page and adds a `## Revision` section; no duplicate page created.

### Step 6: Wire into `/cortex/init-wiki` as a registration step

At the end of `/cortex/init-wiki`, offer to register the auto-ingest hook:
> "Auto-ingest hook not configured. Register it now to keep the wiki current automatically? [y/N]"

If yes: call the hook registration step (Step 3).

**Verification**: Run `/cortex/init-wiki` with `y` response → hook appears in settings.

## Dependencies

- `project-wiki-attached-projects.md` — wiki must exist for auto-ingest to run
- `hook-conditional-dsl.md` — for glob-matched hook firing (soft dependency; fallback to `.git/hooks/` exists)
- `memory-bank-ingest-tool.md` — `ingest()` tool is the ingest primitive

## Success Criteria

- Committing `docs/auth.md` triggers auto-ingest; wiki updated within the session
- Files not matching auto-ingest patterns are silently skipped
- Re-ingesting an unchanged file is a no-op (no duplicate pages)
- Re-ingesting a changed file updates the summary page with a revision note
- Works when Cortex is attached to itself: committing a `.cortex/synapse/prompts/*.md` file updates Cortex's own wiki
- 95%+ test coverage on `wiki_auto_ingest` handler and idempotency logic

## Testing Strategy

- Unit tests for pattern matching: each default pattern matches expected files, misses non-doc files
- Unit tests for `wiki_auto_ingest`: matched files ingested, unmatched skipped, errors returned for unreadable files
- Unit tests for idempotency: same content → no-op; changed content → revision section added
- Integration test: mock git commit with `docs/auth.md` changed → ingest called, wiki updated
- Integration test: mock git commit with `src/foo.py` changed → no ingest triggered
- Self-hosting test: Cortex attached to Cortex; commit a `.cortex/synapse/prompts/` change → Cortex wiki updated
