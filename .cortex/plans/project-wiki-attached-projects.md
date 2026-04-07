---
title: "Project Wiki for Attached Projects (.cortex/wiki/)"
component: wiki
work_type: feature
status: PENDING
priority: high
created: 2026-04-07
depends_on:
  - memory-bank-ingest-tool.md
  - file-review-reports-into-memory-bank.md
---

## Project Wiki for Attached Projects (.cortex/wiki/)

## Goal

When Cortex is attached to a project, it can maintain a `.cortex/wiki/` directory — a persistent, interlinked, LLM-maintained knowledge base for that project. The wiki is seeded from existing docs, compounded by every ingest, review, and analysis session, and queryable via `/cortex/query`. This is the Karpathy LLM-wiki pattern applied as a Cortex service to any attached project.

## Context

Cortex's "Compound Engineering" goal is to make each unit of work easier than the last. Currently this compounds at the **process** level (plans, quality gates, reviews). The wiki extends compounding to the **knowledge** level: every design decision, architecture discussion, PR analysis, and external source enriches a persistent knowledge base that future agents (and humans) read from.

A project attached to Cortex gets `.cortex/wiki/` alongside its code. Cortex owns the wiki entirely — creates pages, updates them, maintains cross-references, keeps everything consistent. Humans read it; Cortex writes it. When Cortex is attached to itself (self-hosting), Cortex's own codebase gets a wiki too.

## Implementation Steps

### Step 1: Define wiki directory structure and schema

Create `.cortex/wiki-schema.md` (the schema document — configurable per project):

```text
.cortex/wiki/
  index.md          # content-oriented catalog (all pages, one-line summaries, by category)
  _schema.md        # this project's wiki conventions (copy of/link to wiki-schema.md)
  concepts/         # core concepts, algorithms, data models
  entities/         # key classes, modules, services
  decisions/        # architectural decisions (ADRs, design choices)
  workflows/        # how things work end-to-end
  sources/          # ingested external sources (immutable)
  analyses/         # filed review reports and analyses
```

Default schema defines:

- Page types and their frontmatter (title, category, tags, source_count, last_updated)
- Cross-reference conventions (wiki-style `[[PageName]]` or markdown links)
- `index.md` format: table with columns `Page | Category | Summary | Sources`

**Verification**: Create `.cortex/wiki/` with the directory structure; confirm `index.md` is readable.

### Step 2: Add wiki initialization to `session()` / project setup

1. Read `src/cortex/tools/session.py` (or wherever `session()` is implemented).
2. Add a `wiki_status` field to the session response: `{"wiki_enabled": bool, "wiki_page_count": int, "wiki_path": str | None}`.
3. If `.cortex/wiki/` doesn't exist but the project has docs (README, ADRs, design docs), suggest initializing: "Wiki not found. Run `/cortex/init-wiki` to seed it from existing docs."
4. The suggestion is non-blocking — no auto-creation.

**Verification**: `session()` response includes `wiki_status` field; suggestion appears when wiki absent and docs exist.

### Step 3: Implement `/cortex/init-wiki` prompt

Create `.cortex/synapse/prompts/init-wiki.md` with:

**Step 1**: Scan project for existing docs: README.md, docs/, ADRs, CHANGELOG.md, architecture diagrams.
**Step 2**: Create `.cortex/wiki/` directory structure (Step 1 schema).
**Step 3**: For each doc found, run the ingest flow (Step 4 in `ingest.md` plan) adapted for wiki targets — write pages to wiki categories instead of memory-bank.
**Step 4**: Build `index.md` from all created pages.
**Step 5**: Write `_schema.md` with the project-specific wiki conventions.
**Step 6**: Report: pages created, index entries, suggested next ingests.

**Verification**: Run `/cortex/init-wiki` on a project with a README and one ADR; confirm wiki is created with at least 2 pages and a populated `index.md`.

### Step 4: Implement wiki-aware `ingest` for attached projects

1. Read the `ingest.md` plan's `/cortex/ingest` prompt.
2. When `.cortex/wiki/` exists, the ingest flow writes the summary page to the appropriate wiki category (instead of `.cortex/memory-bank/`).
3. `index.md` is updated after every ingest.
4. The raw source still goes to `sources/` (immutable).

**Verification**: After wiki init, run `/cortex/ingest`; new page appears in correct category, `index.md` updated.

### Step 5: Implement `/cortex/query` prompt

Create `.cortex/synapse/prompts/query.md`:

**Step 1**: Receive user question.
**Step 2**: Read `index.md` to find relevant pages (LLM scans titles + one-line summaries).
**Step 3**: Read the 3–5 most relevant pages.
**Step 4**: Synthesize answer with citations (page links).
**Step 5**: Offer to file the answer as a new wiki page if it's a novel synthesis (user confirms).

**Verification**: Run `/cortex/query "how does auth work?"` on a wiki with auth-related pages; answer includes citations and correct synthesis.

### Step 6: Wire wiki updates into existing Cortex pipelines

After each of these operations, update the wiki (non-blocking):

- `/cortex/review` completes: file review findings to `wiki/analyses/`
- `/cortex/commit` Phase B: if commit includes new public API or architectural change, trigger wiki update prompt suggestion
- `/cortex/analyze` completes: file session analysis to `wiki/analyses/`

**Verification**: After a review run with a wiki present, confirm the review report is filed to `wiki/analyses/` (not just `.cortex/history/`).

### Step 7: Extend memory-bank lint to include wiki health checks

1. The wiki checks in `memory-bank-lint.md` plan (OrphanedWikiPagesCheck, CrossRefCheck) are activated when `.cortex/wiki/` exists.
2. Add `IndexStalenessCheck`: pages in `.cortex/wiki/` not listed in `index.md`.

**Verification**: Add a wiki page without updating `index.md`; lint reports `IndexStalenessCheck` warning.

## Dependencies

- `memory-bank-ingest-tool.md` — `/cortex/ingest` is the ingest primitive that wiki builds on
- `file-review-reports-into-memory-bank.md` — `file_artifact` operation used for filing to wiki
- `memory-bank-lint.md` — wiki health checks extend lint

## Success Criteria

- `.cortex/wiki/` is created by `/cortex/init-wiki` with correct structure
- `index.md` is updated on every ingest and review filing
- `/cortex/query` returns answers with citations from wiki pages
- Wiki checks in lint fire correctly when wiki exists; no-op when absent
- Works correctly when Cortex is attached to itself (`.cortex/wiki/` in the Cortex repo)
- 95%+ test coverage on init, ingest-to-wiki, and query flows

## Testing Strategy

- Unit tests for wiki directory structure creation and `index.md` generation
- Unit tests for `wiki_status` in `session()` response
- Integration test: `/cortex/init-wiki` on a project with README + 1 ADR → wiki created with 2+ pages
- Integration test: `/cortex/ingest` with wiki present → page in correct category, index updated
- Integration test: `/cortex/query` → answer with citations, offer to file
- Self-hosting test: Cortex attached to Cortex → `.cortex/wiki/` created from Cortex's own docs; query answers questions about Cortex correctly
- Lint integration: orphaned page detected, index staleness detected
