---
title: "Ingest Tool for Cortex Memory Bank (/cortex/ingest)"
component: memory-bank
work_type: feature
status: PENDING
priority: medium
created: 2026-04-07
depends_on:
  - memory-bank-operations-log.md
  - file-review-reports-into-memory-bank.md
---

## Ingest Tool for Cortex Memory Bank (/cortex/ingest)

## Goal

Add an `ingest` MCP tool and `/cortex/ingest` prompt that takes an external source (markdown file, URL content, plain text) and integrates it into the Cortex memory bank — updating relevant pages, noting contradictions with existing content, and filing a summary page. This gives Cortex the "incremental wiki maintenance" property from Karpathy's LLM-wiki pattern.

## Context

Currently, knowledge enters Cortex's memory bank only through manual `manage_file` writes or structured `update_memory_bank` calls during commit/review pipelines. There is no flow for ingesting external sources: ADRs from upstream repos, design docs, RFC drafts, library changelogs, or research notes.

Karpathy's core insight: instead of re-deriving knowledge at query time (RAG), the LLM **builds and maintains a persistent wiki** incrementally. Each ingest reads the source, extracts key information, integrates it into existing pages, flags contradictions, and files a summary. The wiki compounds.

For Cortex itself, this means: when the team reads a relevant RFC, paper, or upstream library update, they can `/cortex/ingest` it and the memory bank reflects the new knowledge immediately.

## Implementation Steps

### Step 1: Define ingest source types

Create `src/cortex/tools/ingest/source_types.py`:

```python
class SourceType(str, Enum):
    MARKDOWN_FILE = "markdown_file"   # local .md file path
    TEXT = "text"                     # raw text passed directly
    URL = "url"                       # fetched URL (future; requires web tool)
```

Create `IngestSource(type: SourceType, content: str, title: str, tags: list[str] | None)`.

**Verification**: Import `IngestSource`; confirm Pydantic validation works.

### Step 2: Implement `ingest` MCP tool (LLM-driven)

Create `src/cortex/tools/ingest/ingest.py`:

```python
async def ingest(
    source_type: str,
    content: str,         # raw source content
    title: str,           # human-readable title for the summary page
    tags: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> ModelDict
```

The tool is **thin** — it does not perform LLM synthesis itself. It:

1. Validates inputs.
2. Writes the raw source to `.cortex/memory-bank/sources/{slug}.md` (immutable; never modified after initial write).
3. Returns a structured `IngestJob(source_path: str, title: str, slug: str)` telling the calling agent what to do next.

The LLM-driven synthesis (reading existing pages, writing summaries, updating cross-references) happens in the `/cortex/ingest` prompt workflow, not in the tool.

**Verification**: Call `ingest(source_type="text", content="...", title="Test RFC")` → source file created in `.cortex/memory-bank/sources/`.

### Step 3: Create `/cortex/ingest` prompt

Create `.cortex/synapse/prompts/ingest.md` with the following workflow:

**Step 1 — Receive source**: User provides source via `/cortex/ingest <path-or-text>`.

**Step 2 — Store raw source**: Call `ingest()` tool to store the source. Get back `IngestJob`.

**Step 3 — Read and discuss**: Read the source. Summarize key takeaways (2–5 bullet points). Present to user for any steering notes before filing.

**Step 4 — Read index**: Read `cortex://context` to understand existing memory-bank content. Identify which existing pages (techContext, systemPatterns, projectBrief, etc.) the source is relevant to.

**Step 5 — Write summary page**: Call `manage_file(operation="file_artifact", artifact_type="query_result", title="{title} — Ingest Summary", content="...")` with:

- One-paragraph abstract
- Key takeaways (bulleted)
- Links to existing memory-bank pages it relates to
- Any contradictions with existing content (flagged explicitly)
- Open questions / gaps

**Step 6 — Update existing pages**: For each relevant existing page identified in Step 4, append a short cross-reference note. Use `manage_file` for each update.

**Step 7 — Log**: Call `update_memory_bank(operation="log_append", operation_type="ingest", title="{title}")`.

**Step 8 — Report**: List: source stored at, summary page at, pages updated, contradictions found.

Register the prompt so it appears as `/cortex/ingest` in Claude Code / Cursor.

**Verification**: Run `/cortex/ingest` with a test markdown file; confirm source stored, summary filed, relevant pages updated.

### Step 4: Update `cortex://context` to surface recent ingests

1. Add `## Recently Ingested Sources` section listing the 5 most recently modified files under `.cortex/memory-bank/sources/` with their titles.
2. Non-blocking: omit section if `sources/` directory doesn't exist.

**Verification**: After an ingest, `cortex://context` shows the ingested source title under `## Recently Ingested Sources`.

### Step 5: Update memory-bank lint to check sources

In `memory-bank-lint.md` plan's `OrphanedWikiPagesCheck`, extend to also flag:

- Sources in `.cortex/memory-bank/sources/` with no corresponding summary page in the artifact store
- Summary pages that link to source files that don't exist

**Verification**: Seed an orphaned source; lint detects it.

## Dependencies

- `memory-bank-operations-log.md` — for log_append calls (Step 7)
- `file-review-reports-into-memory-bank.md` — for `file_artifact` operation (Step 5)

## Success Criteria

- `ingest()` tool stores raw sources immutably in `.cortex/memory-bank/sources/`
- `/cortex/ingest` prompt produces a summary page, updates relevant existing pages, logs the operation
- Contradictions with existing content are explicitly flagged in the summary page
- `cortex://context` surfaces the 5 most recently ingested sources
- 95%+ test coverage on the `ingest` tool handler

## Testing Strategy

- Unit tests for `ingest` tool: valid inputs, slug collision (auto-increment suffix), immutability check (re-ingest same slug appends `-2`)
- Unit tests for `IngestSource` Pydantic model: type validation, required fields
- Integration test: ingest a test markdown file end-to-end via prompt → all 7 steps complete, files exist
- Integration test: ingest a source that contradicts existing `techContext.md` → summary page contains `## Contradictions` section
- Edge cases: empty content, very large content (>10k tokens — agent reads in chunks), title with special characters (slug sanitization)

## Partial Progress Log

- 2026-04-07: Plan steps 1–2 — `SourceType`/`IngestSource`, `ingest` MCP tool (immutable writes under `.cortex/memory-bank/sources/`), slug collision suffix, unit tests, `MAX_REGISTERED_TOOLS` 11 and inventory/docs — files: `src/cortex/tools/ingest/`, `src/cortex/tools/__init__.py`, `src/cortex/tools/structure/categories.py`, `src/cortex/discovery/tool_registry.py`, `tests/tools/test_ingest_tool.py`, `tests/tools/test_tool_categories_governance.py`, `docs/_generated/tool-inventory.json`, `README.md`, `docs/api/tools.md`, `docs/architecture.md`, `docs/index.md`, `docs/getting-started.md`
- 2026-04-08: Plan step 3 — added and registered `/cortex/ingest` workflow prompt (source receive/store, synthesis workflow, context linking, artifact filing, memory-bank update guidance, operation log, final report) — files: `.cortex/synapse/prompts/ingest.md`, `.cortex/synapse/prompts/prompts-manifest.json`
- 2026-04-08: Plan step 4 — added `## Recently Ingested Sources` in `cortex://context` with top-5 source listing and title fallback, plus dedicated context/resource tests — files: `src/cortex/tools/context/recent_ingested_sources_context.py`, `src/cortex/tools/optimization/handlers.py`, `tests/tools/test_recent_ingested_sources_context.py`, `tests/tools/test_recent_ingested_sources_resource.py`, `tests/tools/test_phase4_optimization.py`
- 2026-04-08: Plan step 5 — extended memory-bank lint source checks to flag orphaned ingest sources and summary pages referencing missing source files; added dedicated unit tests — files: `src/cortex/tools/lint/memory_bank_lint_checks.py`, `tests/unit/tools/lint/test_memory_bank_lint_checks.py`
