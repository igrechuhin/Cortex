---
title: Compress Cortex Synapse Prompts and Memory Bank Files
component: cortex/setup
work_type: feature
status: PENDING
priority: High
created: 2026-04-07
depends_on: []
---

## Goal

Reduce cold-start token cost by compressing Cortex's own synapse prompts
(`.cortex/synapse/prompts/`, `.cortex/synapse/cursor-agents/`) and memory bank
files (`.cortex/memory-bank/`) into compact prose. Target: ≥35% token reduction
per file with zero information loss, validated structurally before overwriting.

**Scope**: Cortex internal files only. User-facing CLI output and tool result
strings are excluded — those must stay readable.

**Inspired by**: [caveman](https://github.com/JuliusBrussee/caveman) — the
arXiv paper it cites (2604.00025) shows brevity-constrained LLMs retain or
improve accuracy; the compress+validate pipeline is the actionable pattern.

---

## Context

Every session that attaches Cortex loads synapse prompts and memory bank files
into context. The cost is paid on every session start across every project. Even
a 35% reduction compounding across hundreds of sessions is material.

Current file set (approximate sizes at plan creation):

- `.cortex/synapse/prompts/` — ~15 prompt files, ~8–40 KB each
- `.cortex/synapse/cursor-agents/` — 2 agent files
- `.cortex/memory-bank/` — activeContext, roadmap, progress, and archived entries

Compression rules (derived from caveman + Cortex conventions):

- Drop: articles (a/an/the), filler phrases ("in order to", "please note that",
  "it is important to", "make sure to"), hedging ("may", "might", "could be"),
  pleasantries, redundant preambles.
- Keep verbatim: code blocks (fenced or inline), file paths, CLI commands,
  URLs, Pydantic model names, tool names, MCP resource URIs, error messages,
  YAML frontmatter, section headings, numbered/bulleted list structure.
- Keep readable: sentences should remain grammatically intact enough for a human
  to read without friction. This is not caveman-speak; it is tight technical
  prose. No abbreviation of domain terms.

---

## Implementation Steps

### Step 1: Structural validator (`src/cortex/tools/compress/validate.py`)

Write a `ValidationResult` model and `validate_compressed(original: str, compressed: str) -> ValidationResult`.

Checks:

- Heading count and order preserved (extract `#`-prefixed lines).
- All fenced code blocks in original appear verbatim in compressed.
- URL set equality (regex `https?://\S+`).
- File path set equality (regex `\.cortex/[^\s]+` and `src/[^\s]+`).
- Bullet/numbered list item count within ±15% tolerance.
- Compressed token count < original (use `len(text.split())` as proxy; real
  tiktoken not required).

Returns `ValidationResult(is_valid: bool, errors: list[str], warnings: list[str],
token_ratio: float)`.

**Verification checklist**:

- Search: `class ValidationResult` in `src/cortex/tools/compress/`
- Re-read: `validate.py` after writing
- Test: `tests/unit/test_compress_validate.py` — zero/one/many errors, code block
  preservation, URL equality, heading order

### Step 2: File-type classifier (`src/cortex/tools/compress/detect.py`)

Write `FileType = Literal["natural_language", "code", "config", "unknown"]` and
`detect_file_type(path: Path) -> FileType`.

Logic:

- `.md` → `natural_language`
- `.py`, `.ts`, `.js` → `code`
- `.json`, `.yaml`, `.toml` → `config`
- Otherwise: count code-line ratio; if >60% → `code`, else `natural_language`

Only `natural_language` files are eligible for compression.

**Verification checklist**:

- Search: `def detect_file_type` in `src/cortex/tools/compress/`
- Test: `tests/unit/test_compress_detect.py` — extension lookup, fallback heuristic

### Step 3: Compress pipeline (`src/cortex/tools/compress/compress.py`)

Write `compress_file(path: Path, *, dry_run: bool = False) -> CompressResult`.

Pipeline:

1. `detect_file_type(path)` — skip non-`natural_language` files.
2. Read original content.
3. Write backup: `path.with_suffix(path.suffix + ".original")`.
4. Call `claude --print` via `subprocess.run` with the compress prompt (see
   Step 4). Capture stdout as compressed content.
5. `validate_compressed(original, compressed)`.
6. If valid: overwrite `path` with compressed content (skip if `dry_run`).
   Return `CompressResult(success=True, token_ratio=..., backup_path=...)`.
7. If invalid: call `claude --print` with a targeted fix prompt (include
   `validation_result.errors`). Re-validate. Retry up to 2 times.
8. If still invalid after 2 retries: restore original from backup. Return
   `CompressResult(success=False, errors=...)`.

`CompressResult`: Pydantic `BaseModel` with `success`, `token_ratio`, `errors`,
`warnings`, `backup_path`, `skipped_reason`.

**Verification checklist**:

- Search: `def compress_file` in `src/cortex/tools/compress/compress.py`
- Re-read after writing
- Test: `tests/unit/test_compress_pipeline.py` — happy path, validation failure
  → retry → success, 2 retries exhausted → restore, dry_run skip

### Step 4: Compress prompt (`src/cortex/tools/compress/prompts.py`)

Write `build_compress_prompt(original: str) -> str` and
`build_fix_prompt(original: str, compressed: str, errors: list[str]) -> str`.

Compress prompt rules (inline, no external file dependency):

- Compress the following Markdown technical documentation.
- Drop: articles, filler phrases, hedging, pleasantries, redundant preambles.
- Keep verbatim (exact byte-for-byte): all fenced code blocks, inline code,
  file paths, CLI commands, URLs, tool/model names, section headings,
  YAML frontmatter.
- Keep readable: compact technical prose, not abbreviation-speak. A human
  should read it without friction.
- Target: ≥35% token reduction. Do not truncate sections.
- Output the compressed document only — no commentary, no preamble.

**Verification checklist**:

- Search: `def build_compress_prompt` in `src/cortex/tools/compress/prompts.py`

### Step 5: Batch runner (`src/cortex/tools/compress/batch.py`)

Write `compress_directory(root: Path, *, glob: str = "**/*.md", dry_run: bool = False) -> list[CompressResult]`.

- Collect files matching glob under root.
- Skip `*.original.*` backup files.
- Call `compress_file` on each. Collect results.
- Log per-file outcome (path, token_ratio, success/skip/error).
- Return all results.

**Verification checklist**:

- Search: `def compress_directory` in `src/cortex/tools/compress/batch.py`
- Test: `tests/unit/test_compress_batch.py` — skip backup files, collect all results

### Step 6: Compress the actual Cortex files (one-time run)

Run `compress_directory` on:

- `.cortex/synapse/prompts/` — all `.md` files
- `.cortex/synapse/cursor-agents/` — all `.md` files
- `.cortex/memory-bank/` — `activeContext.md`, `progress.md` (skip `roadmap.md`
  — it has rigid format constraints that compression could violate)

Validate each result. Commit originals to git before running (safety net beyond
the `.original` backups).

**Verification checklist**:

- `git diff --stat` to confirm files changed
- Re-read compressed versions, check no section headings are missing
- Run `run_quality_gate()` — all tests must pass after compression

### Step 7: `__init__.py` and module export

Expose `compress_file`, `compress_directory`, `ValidationResult`, `CompressResult`,
`detect_file_type` from `src/cortex/tools/compress/__init__.py`.

---

## Dependencies

- `subprocess` (stdlib) — for `claude --print` calls
- No new third-party packages

---

## Success Criteria

- `ValidationResult` model passes all structural invariant checks on real synapse files.
- `compress_file` achieves ≥35% token reduction (word-count proxy) on at least
  3 of 5 sampled synapse prompt files.
- All backups created before overwrite; restore path tested and working.
- `.cortex/synapse/prompts/` and `cursor-agents/` compressed without heading or
  code-block loss.
- `run_quality_gate()` green after compression.

---

## Testing Strategy

Target: 95% coverage of `src/cortex/tools/compress/`.

| File | Tests |
|------|-------|
| `validate.py` | Heading count/order, code block exact match, URL set equality, bullet ±15% |
| `detect.py` | Extension lookup, heuristic fallback, backup file skip |
| `compress.py` | Happy path, validation fail → retry → success, 2 retries → restore, dry_run |
| `batch.py` | Multi-file collection, backup skip, result aggregation |
| `prompts.py` | Prompt string contains required rule keywords |

Use `tmp_path` fixtures. Mock `subprocess.run` for pipeline tests to avoid real
`claude --print` invocations in CI.

## Partial Progress Log

- 2026-04-08: Implemented Step 1 structural validator and tests — files: src/cortex/tools/compress/**init**.py, src/cortex/tools/compress/validate.py, tests/unit/test_compress_validate.py
- 2026-04-08: Implemented Step 2 file-type classifier and tests — files: src/cortex/tools/compress/detect.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_detect.py
- 2026-04-08: Implemented Step 3 compress pipeline and tests — files: src/cortex/tools/compress/compress.py, src/cortex/tools/compress/prompts.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_pipeline.py
- 2026-04-08: Implemented Step 5 batch runner and tests — files: src/cortex/tools/compress/batch.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_batch.py
- 2026-04-08: Implemented Step 4 prompt behavior hardening and prompt tests — files: src/cortex/tools/compress/prompts.py, tests/unit/test_compress_prompts.py
- 2026-04-08: Implemented safe Step 6 targeting helper and tests — files: src/cortex/tools/compress/batch.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_batch.py
- 2026-04-08: Implemented Step 5 per-file outcome logging and tests — files: src/cortex/tools/compress/batch.py, tests/unit/test_compress_batch.py
- 2026-04-08: Implemented Step 7 export contract verification test — files: tests/unit/test_compress_exports.py
- 2026-04-08: Hardened batch reliability with continue-on-error exception handling and logging for one-time compression runs — files: src/cortex/tools/compress/batch.py, tests/unit/test_compress_batch.py
- 2026-04-08: Extended file-type extension coverage to classify `.yml` as config with dedicated regression test — files: src/cortex/tools/compress/detect.py, tests/unit/test_compress_detect.py
- 2026-04-08: Added compression batch summary metrics and validation helpers for Step 6 verification (>=35% target attainment reporting) — files: src/cortex/tools/compress/batch.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_batch.py
- 2026-04-08: Added structured success-criteria verification for Step 6 (minimum successful sample and >=35% target-hit threshold) with regression tests — files: src/cortex/tools/compress/batch.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_batch.py
- 2026-04-08: Hardened Step 6 verification to fail when compression failures exceed explicit budget and track failed file count — files: src/cortex/tools/compress/batch.py, tests/unit/test_compress_batch.py
- 2026-04-08: Added end-to-end Step 6 integration helper and verification report model with configurable threshold checks — files: src/cortex/tools/compress/batch.py, src/cortex/tools/compress/**init**.py, tests/unit/test_compress_batch.py
- 2026-04-08: Propagated per-file path identity into compression results (including batch exception fallback) for actionable Step 6 reporting — files: src/cortex/tools/compress/compress.py, src/cortex/tools/compress/batch.py, tests/unit/test_compress_batch.py
- 2026-04-08: Added explicit missing-target reporting for Step 6 orchestration to surface absent required compression targets as skipped outcomes — files: src/cortex/tools/compress/batch.py, tests/unit/test_compress_batch.py
