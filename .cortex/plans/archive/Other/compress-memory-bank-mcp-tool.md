---
title: compress_memory_bank MCP Tool and Token Budget Tracking
component: cortex/tools
work_type: feature
status: PENDING
priority: Medium
created: 2026-04-07
depends_on:
  - .cortex/plans/compress-synapse-memory-files.md
---

## Goal

Expose a `compress_memory_bank()` MCP tool that projects attached to Cortex
can call to compress their own memory bank files (e.g. `CLAUDE.md`, project
`.cortex/memory-bank/*.md`). Add a token-budget metric to `/cortex/analyze`
that surfaces compression opportunities automatically.

This brings the caveman compress-pipeline value to every project Cortex is
attached to, as a first-class Cortex capability — not a separate CLI install.

**Scope boundary**: The tool compresses project memory files. It does not
compress source code, test files, or user-visible documentation. User-facing
output strings from MCP tools remain readable.

**Inspired by**: caveman's `caveman-compress` CLI (`/caveman-compress CLAUDE.md`)
and its compress+structural-validate pipeline.

---

## Context

Projects attach Cortex to get AI workflow benefits. Their own `CLAUDE.md` and
`.cortex/memory-bank/` files are loaded on every session — but they accumulate
verbose prose over time. There is currently no Cortex mechanism to help projects
reduce this load.

The compress pipeline from `compress-synapse-memory-files` plan (Step 1–5) is
reusable: `compress_file()`, `compress_directory()`, `ValidationResult`,
`CompressResult`. This plan wraps that pipeline as an MCP tool and adds
token-budget surfacing to the analyze pipeline.

---

## Implementation Steps

### Step 1: MCP tool handler (`src/cortex/tools/memory_compress_tool.py`)

Write `compress_memory_bank_tool(project_root: Path | None = None) -> CompressMemoryBankResult`.

Logic:

1. Resolve `project_root` (use `resolve_project_root_async()` pattern from
   `project_root_resolver.py` if called with `None`).
2. Target paths (compress all, in order):
   - `{project_root}/CLAUDE.md` — if exists
   - `{project_root}/.cortex/memory-bank/*.md` — all `.md` files, skip
     `roadmap.md` (rigid format) and `*.original.*` backups
   - `{project_root}/.claude/CLAUDE.md` — if exists
3. For each target: call `compress_file(path, dry_run=False)`.
4. Aggregate into `CompressMemoryBankResult`.

`CompressMemoryBankResult`: Pydantic `BaseModel`:

```python
class FileCompressResult(BaseModel):
    path: str
    success: bool
    token_ratio: float      # compressed/original word count ratio
    errors: list[str]
    skipped_reason: str | None

class CompressMemoryBankResult(BaseModel):
    files_processed: int
    files_compressed: int
    files_skipped: int
    files_failed: int
    results: list[FileCompressResult]
    average_token_ratio: float  # across successful compressions
    total_words_saved: int      # proxy metric
```

**Verification checklist**:

- Search: `class CompressMemoryBankResult` in `src/cortex/tools/`
- Re-read `memory_compress_tool.py` after writing
- Test: `tests/unit/test_memory_compress_tool.py` — happy path (mock
  `compress_file`), CLAUDE.md missing (skip), roadmap.md excluded

### Step 2: Register tool on MCP server (`src/cortex/server.py`)

Register `compress_memory_bank` tool alongside existing `manage_file` etc.
Use the same zero-arg-safe pattern: default all params to `None`/sensible
fallbacks (Cursor strips args).

Tool description (shown in Cursor MCP panel):

```text
Compress project memory files (CLAUDE.md, .cortex/memory-bank/*.md) to
reduce session token cost. Creates .original backups; validates structural
integrity before overwriting. Returns per-file compression ratios.
```

**Verification checklist**:

- Search: `compress_memory_bank` in `server.py`
- Confirm tool appears in `list_tools()` output (integration test or manual)

### Step 3: Token budget metric in analyze pipeline

Locate the analyze pipeline source (likely `.cortex/synapse/prompts/` or
`src/cortex/tools/analysis/`).

Add a `## Token Budget` section to the analyze output:

1. Walk `{project_root}/CLAUDE.md`, `.cortex/memory-bank/*.md`.
2. For each file: compute word count.
3. Flag files where word count > 500 as "compression candidate".
4. Output table:

```text
| File | Words | Status |
|------|-------|--------|
| CLAUDE.md | 1240 | ⚠ compression candidate (>500) |
| activeContext.md | 380 | ✓ |
```

5. If any candidates: append recommendation:

   ```text
   Run compress_memory_bank() to reduce session token cost.
   ```

Write `src/cortex/tools/analysis/token_budget.py`:

- `TokenBudgetEntry(path: str, word_count: int, is_candidate: bool)`
- `compute_token_budget(project_root: Path) -> list[TokenBudgetEntry]`
- `format_token_budget_report(entries: list[TokenBudgetEntry]) -> str`

**Verification checklist**:

- Search: `class TokenBudgetEntry` in `src/cortex/tools/analysis/`
- Search: `compression candidate` in `token_budget.py`
- Test: `tests/unit/test_token_budget.py` — threshold boundary (499/500/501),
  empty dir, mixed candidates/clean

### Step 4: Surface token budget in `cortex://analysis` resource

Update the `cortex://analysis` resource handler to include the token budget
report in its output (after existing session analysis sections).

The resource content format:

```text
## Token Budget

{format_token_budget_report(entries)}
```

**Verification checklist**:

- Search: `token_budget` in the analysis resource handler
- Integration test: `tests/integration/test_analysis_resource.py` — confirm
  `## Token Budget` section present in resource output

### Step 5: `/cortex/analyze` Synapse prompt update

In `.cortex/synapse/prompts/analyze-compact.md` (or whichever prompt drives
`/cortex/analyze`), add Step 8 after the existing tools-optimization step:

```text
**Step 8 — Token Budget**: Read the token budget section from
`cortex://analysis`. Flag any memory bank file over 500 words as a
compression candidate. If candidates exist, emit a recommendation to run
`compress_memory_bank()`. Append to the session-optimization report.
```

**Verification checklist**:

- Read the modified prompt file after change
- Confirm Step 8 references `compress_memory_bank()`

---

## Dependencies

- `compress-synapse-memory-files` plan — reuses `compress_file()`,
  `compress_directory()`, `ValidationResult`, `CompressResult` from
  `src/cortex/tools/compress/`
- Existing project root resolver (`project_root_resolver.py`)
- Existing MCP server registration pattern (`server.py`)

---

## Success Criteria

- `compress_memory_bank()` MCP tool registered and callable (zero-arg safe).
- Calling the tool on a project with a large `CLAUDE.md` returns
  `CompressMemoryBankResult` with `success=True` and `token_ratio < 0.75`.
- `cortex://analysis` resource includes `## Token Budget` section.
- `/cortex/analyze` run on a project with a 700-word `CLAUDE.md` flags it
  as a compression candidate.
- `run_quality_gate()` green after all changes.

---

## Testing Strategy

Target: 95% coverage of `src/cortex/tools/memory_compress_tool.py` and
`src/cortex/tools/analysis/token_budget.py`.

| File | Tests |
|------|-------|
| `memory_compress_tool.py` | Mock `compress_file`: happy path, CLAUDE.md absent, roadmap.md excluded, all files fail |
| `token_budget.py` | Word count threshold (499/500/501), empty dir, mixed files, report format string |
| `server.py` registration | Assert `compress_memory_bank` in tool list |
| Analysis resource | Assert `## Token Budget` in rendered resource output |

Use `tmp_path` for file creation. Mock `compress_file` and `resolve_project_root_async`
in unit tests.
