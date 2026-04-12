---
title: "Project Wiki for Attached Projects (.cortex/wiki/)"
component: wiki
work_type: feature
status: IN_PROGRESS
priority: high
created: 2026-04-07
depends_on:
  - memory-bank-ingest-tool.md
  - file-review-reports-into-memory-bank.md
---

## Project Wiki for Attached Projects (.cortex/wiki/)

## Goal

When Cortex is attached to a project, it can maintain a `.cortex/wiki/` directory — a persistent, interlinked, LLM-maintained knowledge base for that project. The wiki is seeded from existing docs, compounded by every ingest, review, and analysis session, and queryable via `/cortex/ask`. This is the Karpathy LLM-wiki pattern applied as a Cortex service to any attached project.

## Context

Cortex's "Compound Engineering" goal is to make each unit of work easier than the last. Currently this compounds at the **process** level (plans, quality gates, reviews). The wiki extends compounding to the **knowledge** level: every design decision, architecture discussion, PR analysis, and external source enriches a persistent knowledge base that future agents (and humans) read from.

A project attached to Cortex gets `.cortex/wiki/` alongside its code. Cortex owns the wiki entirely — creates pages, updates them, maintains cross-references, keeps everything consistent. Humans read it; Cortex writes it. When Cortex is attached to itself (self-hosting), Cortex's own codebase gets a wiki too.

## Implementation Steps

### Step 1: Define wiki directory structure and schema

Create `.cortex/wiki/schema.md` (the normative schema document — configurable per project):

```text
.cortex/wiki/
  schema.md         # normative layout, frontmatter, and index conventions
  index.md          # content-oriented catalog (all pages, one-line summaries, by category)
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

**Verification**: With `.cortex/` present, start the Cortex MCP server (or trigger any tool so usage context initializes); confirm `.cortex/wiki/` is created with `schema.md` (from bundled default) and `index.md` is readable.

### Step 2: Add wiki initialization to `session()` / project setup

1. Read `src/cortex/tools/session.py` (or wherever `session()` is implemented).
2. Add a `wiki_status` field to the session response: `{"wiki_enabled": bool, "wiki_page_count": int, "wiki_path": str | None}`.
3. If `.cortex/wiki/` scaffold exists but has no pages and seed docs exist, suggest: "Wiki is empty. Run `/cortex/init-wiki` to seed it from existing docs." — the prompt will be available in the prompts list.
4. The suggestion is non-blocking — no auto-creation. Once the wiki has content, the hint and the prompt are both suppressed.

**Verification**: `session()` response includes `wiki_status` field; suggestion appears when wiki absent and docs exist.

### Step 3: Implement `/cortex/init-wiki` prompt as a conditional registration

The `/cortex/init-wiki` prompt seeds an empty wiki from existing project docs. It is only useful once — when the wiki has no content yet. Once the wiki has any pages, the prompt is redundant and should not appear in the prompts list.

**Conditional availability rule**: `/cortex/init-wiki` is registered only when `.cortex/wiki/` exists (scaffold present) but contains zero pages across all category directories (`concepts/`, `entities/`, `decisions/`, `workflows/`, `analyses/`). If any category directory contains at least one `.md` file (excluding `index.md` and `schema.md`), the prompt is not registered.

**Implementation**:

1. Add a `wiki_has_content(project_root: Path) -> bool` helper to `src/cortex/wiki/layout.py` — returns `True` if any category dir contains at least one `.md` file.
2. In `src/cortex/setup/lazy_prompt_registration.py`, add `_register_init_wiki_prompt(project_root)` following the existing `_register_initialize_prompt` pattern.
3. In `register_setup_prompts()`, add: if wiki scaffold exists and `not wiki_has_content(project_root)` and `"init_wiki" not in already` → register it.

**Prompt content** (already created at `.cortex/synapse/prompts/init-wiki.md`):

- Scan project for existing docs: README.md, docs/, ADRs, CHANGELOG.md, architecture diagrams.
- Wiki directory layout already exists (created by `bootstrap_wiki_if_cortex_present` on session start) — skip creation.
- For each doc found, ingest into wiki categories (not memory-bank).
- Rebuild `index.md` from all created pages.
- Adjust `schema.md` only if this project needs conventions beyond the default (optional).
- Report: pages created, index entries, suggested next ingests.

**Verification**: With empty wiki, `init_wiki` appears in `list_prompts`. After running it and pages exist, restart server — `init_wiki` no longer appears.

### Step 4: Implement wiki-aware `ingest` for attached projects

1. Read the `ingest.md` plan's `/cortex/ingest` prompt.
2. When `.cortex/wiki/` exists, the ingest flow writes the summary page to the appropriate wiki category (instead of `.cortex/memory-bank/`).
3. `index.md` is updated after every ingest.
4. The raw source still goes to `sources/` (immutable).

**Verification**: After wiki init, run `/cortex/ingest`; new page appears in correct category, `index.md` updated.

### Step 5: Implement `/cortex/ask` prompt

Create `.cortex/synapse/prompts/ask.md`:

**Step 1**: Receive user question.
**Step 2**: Read `index.md` to find relevant pages (LLM scans titles + one-line summaries).
**Step 3**: Read the 3–5 most relevant pages.
**Step 4**: Synthesize answer with citations (page links).
**Step 5**: Offer to file the answer as a new wiki page if it's a novel synthesis (user confirms).

**Verification**: Run `/cortex/ask "how does auth work?"` on a wiki with auth-related pages; answer includes citations and correct synthesis.

### Step 6: Wire wiki updates into existing Cortex pipelines

**`/cortex/commit` (atomic wiki update)**: Between Phase A and Phase B, detect staged doc files matching auto-ingest patterns, ingest them into the wiki, and stage the resulting wiki pages. Phase B then validates the commit including wiki changes. Wiki pages land in the same commit as the source — no dirty workspace, no separate wiki commit. See `wiki-auto-ingest-git-hooks.md` plan for full details.

**`/cortex/review` completes**: File review findings to `wiki/analyses/`.

**`/cortex/analyze` completes**: File session analysis to `wiki/analyses/`.

**Verification**: Stage `docs/auth.md` and run `/cortex/commit`; confirm wiki pages are in `git diff --cached` before the commit and in the final commit alongside the source file. After a review run with a wiki present, confirm the review report is filed to `wiki/analyses/` (not just `.cortex/history/`).

### Step 8: Self-hosting — run `/cortex/init-wiki` on the Cortex project itself

With all prior steps implemented and the conditional registration in place, run `/cortex/init-wiki` against the Cortex repo to seed its own wiki.

Cortex has substantial existing docs:

- `README.md`
- `docs/` tree (API, security, guides)
- `AGENTS.md`, `CLAUDE.md`
- `.cortex/plans/*.md` (architectural decisions)
- `.cortex/synapse/prompts/*.md` (workflow definitions)

Expected outcome: `.cortex/wiki/` populated with pages across `concepts/`, `entities/`, `decisions/`, `workflows/`; `index.md` has 10+ entries; `/cortex/init-wiki` prompt no longer appears in the prompts list after completion.

**Verification**: Run `/cortex/init-wiki`; confirm wiki has pages; confirm prompt is gone from `list_prompts` on next session.

---

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
- `/cortex/ask` returns answers with citations from wiki pages
- Wiki checks in lint fire correctly when wiki exists; no-op when absent
- Works correctly when Cortex is attached to itself (`.cortex/wiki/` in the Cortex repo)
- 95%+ test coverage on init, ingest-to-wiki, and query flows

## Testing Strategy

- Unit tests for wiki directory structure creation and `index.md` generation
- Unit tests for `wiki_status` in `session()` response
- Integration test: `/cortex/init-wiki` on a project with README + 1 ADR → wiki created with 2+ pages
- Integration test: `/cortex/ingest` with wiki present → page in correct category, index updated
- Integration test: `/cortex/ask` → answer with citations, offer to file
- Self-hosting test: Cortex attached to Cortex → `.cortex/wiki/` created from Cortex's own docs; `/cortex/ask` answers questions about Cortex correctly
- Lint integration: orphaned page detected, index staleness detected

## Partial Progress Log

- 2026-04-11: Step 1 — wiki schema doc, `CortexResourceType.WIKI`, `ensure_default_wiki_layout()` and unit tests — files: `.cortex/wiki/schema.md` (and bundled `src/cortex/wiki/default_wiki_schema.md`), `src/cortex/core/path_resolver.py`, `src/cortex/wiki/__init__.py`, `src/cortex/wiki/layout.py`, `tests/unit/test_wiki_layout.py`, `tests/unit/test_path_resolver.py`
- 2026-04-11: Relocated normative schema from `.cortex/wiki-schema.md` to `.cortex/wiki/schema.md`; bootstrap copies from `src/cortex/wiki/default_wiki_schema.md` — files: `src/cortex/wiki/layout.py`, `src/cortex/wiki/default_wiki_schema.md`, `.cortex/wiki/schema.md`, `pyproject.toml`, `tests/unit/test_wiki_layout.py`, `.cortex/plans/project-wiki-attached-projects.md`, `.cortex/plans/wiki-auto-ingest-git-hooks.md`, `.cortex/memory-bank/progress.md`
- 2026-04-11: Step 2 — `wiki_status` on session brief (`WikiStatusSummary`), `append_session_wiki_init_hint` when `.cortex/wiki/` missing and seed docs exist — files: `src/cortex/tools/session/models.py`, `src/cortex/tools/session/start_models.py`, `src/cortex/tools/session/brief.py`, `src/cortex/tools/session/brief_helpers.py`, `src/cortex/tools/session/brief_extraction_helpers.py`, `src/cortex/tools/session/wiki_status.py`, `tests/tools/test_session_wiki_status.py`, `tests/tools/test_session_start_health_brief.py`
- 2026-04-11: Step 3 — Synapse `/cortex/init-wiki` prompt (`init-wiki.md`) plus manifest entry; unit test for registration — files: `.cortex/synapse/prompts/init-wiki.md`, `.cortex/synapse/prompts/prompts-manifest.json`, `tests/unit/test_wiki_layout.py`
- 2026-04-12: Step 4 — wiki-aware MCP `ingest`: raw under `.cortex/wiki/sources/`, auto summary page + `index.md` row, context prefers wiki sources; `read_recent_ingested_sources_markdown` — files: `src/cortex/wiki/ingest_wiki.py`, `src/cortex/tools/ingest/ingest_handler.py`, `src/cortex/tools/optimization/handlers.py`, `src/cortex/tools/context/recent_ingested_sources_context.py`, `tests/tools/test_ingest_tool.py`, `tests/unit/test_wiki_ingest.py`, `tests/tools/test_recent_ingested_sources_wiki_preference.py`, `tests/tools/test_roadmap_plan_graph_annotate.py`
- 2026-04-12: Step 5 — Synapse `/cortex/ask` prompt (`ask.md`, renamed from `query`) plus manifest entry; icon mapping; unit test for registration — files: `.cortex/synapse/prompts/ask.md`, `.cortex/synapse/prompts/prompts-manifest.json`, `src/cortex/tools/synapse/prompts_content.py`, `tests/unit/test_wiki_layout.py`
- 2026-04-12: Step 6 partial — `file_artifact` mirrors `review_report` and `session_analysis` into `.cortex/wiki/analyses/` with frontmatter + `index.md` row; `append_wiki_catalog_row` — files: `src/cortex/wiki/ingest_wiki.py`, `src/cortex/wiki/artifact_mirror.py`, `src/cortex/tools/files/artifact_operations.py`, `tests/tools/test_file_artifact_operation.py`
- 2026-04-12: Step 7 — `IndexStalenessCheck` + `index_catalog_linked_page_paths()` (wiki pages outside `sources/` not linked from `index.md` pipe table); registered in memory-bank lint — files: `src/cortex/wiki/ingest_wiki.py`, `src/cortex/tools/lint/memory_bank_lint_checks.py`, `src/cortex/tools/lint/lint_memory_bank.py`, `src/cortex/tools/lint/__init__.py`, `tests/unit/tools/lint/test_memory_bank_lint_checks.py`, `tests/unit/test_wiki_ingest.py`
- 2026-04-12: Step 8 — Self-hosting wiki seed: 12 summary pages + raw `sources/` snapshots from README, AGENTS, CLAUDE, and selected `docs/` (ingest pipeline parity); `index.md` catalog — files: `.cortex/wiki/index.md`, `.cortex/wiki/concepts/*`, `.cortex/wiki/workflows/*`, `.cortex/wiki/entities/*`, `.cortex/wiki/decisions/*`, `.cortex/wiki/sources/*`
- 2026-04-12: Markdown lint scope — exclude `.cortex/wiki/sources/` from rumdl collection (worker, `get_all_markdown_files_for_lint`, CI `quality.yml`) so immutable snapshots do not fail MD057; tests — files: `src/cortex/tools/files/markdown_lint_core.py`, `src/cortex/tools/execution/pre_commit_worker.py`, `.github/workflows/quality.yml`, `docs/api/tools.md`, `tests/unit/test_pre_commit_worker_md_collect.py`, `tests/unit/test_markdown_lint_wiki_sources_exclude.py`
- 2026-04-12: Step 6 (commit slice) — Synapse `commit.md` documents the Phase A→B wiki bridge: staged paths → `wiki_ingest_staged_docs` → `git add` written wiki paths; sequential order updated — files: `.cortex/synapse/prompts/commit.md`
- 2026-04-12: Staged wiki ingest idempotency — `IngestSource.stable_ingest_rel`, `slugify_repo_rel_path`, skip identical re-ingest (`ingest_outcome=unchanged`), archive prior raw as `sources/{slug}-v{n}.md`, upsert summary at deterministic `{category}/{slug}.md` with `## Revision` — files: `src/cortex/tools/ingest/slug.py`, `src/cortex/tools/ingest/source_types.py`, `src/cortex/tools/ingest/ingest_handler.py`, `src/cortex/tools/ingest/stable_path_ingest.py`, `src/cortex/wiki/ingest_wiki.py`, `src/cortex/tools/wiki/staged_ingest.py`, `tests/tools/test_ingest_tool.py`, `tests/unit/test_wiki_staged_ingest.py`
- 2026-04-12: Step 3 completion — `wiki_scaffold_present` / `wiki_has_content` in `layout.py`; bulk registration skips `init-wiki.md`; lazy `_register_init_wiki_prompt_if_needed` after startup repair (works when `should_mount_setup` is false); `init_wiki` icon — files: `src/cortex/wiki/layout.py`, `src/cortex/setup/lazy_prompt_registration.py`, `src/cortex/tools/synapse/prompts_registration.py`, `src/cortex/tools/synapse/prompts_content.py`, `tests/unit/test_wiki_layout.py`, `tests/unit/test_lazy_prompt_registration.py`, `tests/tools/test_synapse_prompts.py`
