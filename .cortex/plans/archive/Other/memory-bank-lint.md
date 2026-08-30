---
title: "Memory Bank Lint (/cortex/lint-wiki)"
component: memory-bank
work_type: feature
status: PENDING
priority: High
created: 2026-04-07
depends_on: []
---

## Memory Bank Lint (/cortex/lint-wiki)

## Goal

Add a `lint_memory_bank` MCP tool (and expose it as `/cortex/lint-wiki` prompt) that health-checks the Cortex memory bank and, when Cortex is attached to a project, the project's `.cortex/wiki/`. The lint pass finds orphaned plans, stale claims, missing cross-references, and unterminated threads — and produces a prioritized report.

## Context

Cortex has `run_quality_gate` for code quality and `run_docs_gate` for doc consistency, but no **knowledge-base health check**. As the memory bank grows (especially once the ingest and wiki features land), it will accumulate:

- Plans in `.cortex/plans/` not referenced in `roadmap.md`
- Claims in `techContext.md` that contradict current code (e.g., "uses Python 3.11" when pyproject says 3.13)
- Orphaned wiki pages with no inbound links
- Concepts mentioned in `activeContext.md` but lacking their own page
- Stale `activeContext.md` entries older than 30 days with no resolution

Karpathy's wiki pattern explicitly calls for a periodic lint operation to keep the knowledge base healthy. This is the Cortex equivalent.

## Implementation Steps

### Step 1: Define lint check taxonomy

Create `src/cortex/tools/lint/memory_bank_lint_checks.py` with a `LintCheck` protocol and the following check implementations:

1. **OrphanedPlansCheck** — plans in `.cortex/plans/*.md` (excluding archive/) not referenced in `roadmap.md`
2. **MissingPlanFilesCheck** — roadmap entries whose `Plan:` path doesn't exist on disk
3. **StaleActiveContextCheck** — `activeContext.md` entries older than 30 days with no corresponding `progress.md` entry
4. **CrossRefCheck** (wiki-only) — `.cortex/wiki/**/*.md` pages mentioned by name in other pages but lacking a corresponding file
5. **OrphanedWikiPagesCheck** (wiki-only) — wiki pages with no inbound links from other wiki pages or memory-bank files
6. **CodeClaimCheck** — configurable list of claims to verify (e.g., Python version in `techContext.md` vs `pyproject.toml`); extensible via `.cortex/config/lint-config.json`

Each check returns a list of `LintFinding(severity: Literal["error","warning","info"], check: str, message: str, file: str | None, line: int | None)`.

**Verification**: Import and instantiate each check class; confirm `LintFinding` is a valid Pydantic model.

### Step 2: Implement `lint_memory_bank` MCP tool

1. Read existing tool registration patterns in `src/cortex/tools/` and `src/cortex/server.py`.
2. Create `src/cortex/tools/lint/lint_memory_bank.py` with:

   ```python
   async def lint_memory_bank(ctx: MCPContext | None = None) -> ModelDict
   ```

3. Tool discovers project root via `resolve_project_root_async()`.
4. Runs all applicable checks (wiki checks only when `.cortex/wiki/` exists).
5. Returns structured `LintReport(findings: list[LintFinding], summary: str, error_count: int, warning_count: int, info_count: int)`.
6. Register tool in `src/cortex/server.py`.

**Verification**: Call `lint_memory_bank({})` via MCP; confirm structured response with correct counts.

### Step 3: Add `/cortex/lint-wiki` prompt

1. Read `src/cortex/setup/prompts.py` for how prompts are registered.
2. Create `.cortex/synapse/prompts/lint-wiki.md` with workflow:
   - Call `lint_memory_bank()`
   - Present findings grouped by severity
   - For each `error`-level finding: propose fix and ask if agent should apply it
   - For each `warning`-level: list with recommended action
   - For each `info`-level: summarize in a collapsible block
3. Register the prompt so it appears as `/cortex/lint-wiki` in Claude Code / Cursor.

**Verification**: Prompt appears in `/cortex/` list; running it on a test memory bank with known issues produces correct findings.

### Step 4: Integrate with `/cortex/analyze`

1. Read `.cortex/synapse/prompts/analyze.md` (or equivalent).
2. Add lint step: after session analysis, call `lint_memory_bank()` and include `error`-level findings in the analyze report under a `## Memory Bank Health` section.
3. Non-blocking: if lint tool unavailable, omit section.

**Verification**: Run `/cortex/analyze`; confirm `## Memory Bank Health` section appears with lint findings.

### Step 5: Add `lint-config.json` support

1. Define schema for `.cortex/config/lint-config.json`:

   ```json
   {
     "code_claim_checks": [
       {"file": "techContext.md", "pattern": "Python 3\\.\\d+", "verify_against": "pyproject.toml"}
     ],
     "stale_threshold_days": 30
   }
   ```

2. `CodeClaimCheck` reads this config if present; no-ops if absent.
3. Document the config format in `docs/guides/lint-config.md`.

**Verification**: Create a `.cortex/config/lint-config.json` with one check; confirm it runs and detects a seeded mismatch.

## Dependencies

- None required, but richer results after `memory-bank-operations-log.md` plan is implemented (log entries help date-stamp findings)
- Wiki checks are no-ops until `project-wiki-attached-projects.md` plan is implemented

## Success Criteria

- `lint_memory_bank({})` returns structured `LintReport` via MCP
- `/cortex/lint-wiki` prompt is callable and produces readable grouped output
- `/cortex/analyze` includes `## Memory Bank Health` section
- OrphanedPlansCheck correctly identifies plans missing from roadmap
- MissingPlanFilesCheck correctly identifies roadmap entries pointing to non-existent files
- 95%+ test coverage on all check classes and the tool handler

## Testing Strategy

- Unit tests per check class using fixture memory-bank directories
- Integration test: seed `.cortex/plans/` with an orphaned plan → lint detects it
- Integration test: seed `roadmap.md` with a missing plan path → lint detects it
- Integration test: `.cortex/wiki/` absent → wiki checks return empty findings (no error)
- Integration test: `.cortex/wiki/` present with an orphaned page → OrphanedWikiPagesCheck fires
- Test `lint-config.json` loading: valid config, missing config, malformed config

## Partial Progress Log

- 2026-04-07: Implemented lint taxonomy foundation plus `OrphanedPlansCheck` and `MissingPlanFilesCheck` with unit tests — files: src/cortex/tools/lint/**init**.py, src/cortex/tools/lint/memory_bank_lint_checks.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py
- 2026-04-07: Implemented `StaleActiveContextCheck` with date-threshold/progress resolution logic and unit tests — files: src/cortex/tools/lint/memory_bank_lint_checks.py, src/cortex/tools/lint/**init**.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py
- 2026-04-07: Implemented `CrossRefCheck` (wiki-only missing-page references) and unit tests for missing refs and missing-wiki no-op behavior — files: src/cortex/tools/lint/memory_bank_lint_checks.py, src/cortex/tools/lint/**init**.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py
- 2026-04-07: Implemented `OrphanedWikiPagesCheck` (wiki-only inbound-link validation) and unit tests for orphaned page detection, wiki-linked pages, memory-bank-linked pages, and missing-wiki no-op — files: src/cortex/tools/lint/memory_bank_lint_checks.py, src/cortex/tools/lint/**init**.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py
- 2026-04-07: Implemented `CodeClaimCheck` with `.cortex/config/lint-config.json` support and no-op handling for missing/malformed config, plus unit tests — files: src/cortex/tools/lint/memory_bank_lint_checks.py, src/cortex/tools/lint/**init**.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py
- 2026-04-07: Implemented Step 2 MCP tool slice by adding `lint_memory_bank` with structured `LintReport` aggregation/counts, plus unit tests and tool registration wiring — files: src/cortex/tools/lint/lint_memory_bank.py, src/cortex/tools/lint/**init**.py, src/cortex/tools/**init**.py, src/cortex/tools/structure/categories.py, tests/unit/tools/lint/test_lint_memory_bank.py, docs/_generated/tool-inventory.json, README.md
- 2026-04-07: Implemented Step 3 prompt-registration slice by adding `.cortex/synapse/prompts/lint-wiki.md`, registering it in `prompts-manifest.json` and prompt icon mapping, plus structural integration tests — files: .cortex/synapse/prompts/lint-wiki.md, .cortex/synapse/prompts/prompts-manifest.json, src/cortex/tools/synapse/prompts_content.py, tests/integration/test_lint_wiki_prompt_structural.py
- 2026-04-07: Integrated Step 4 analyze flow by calling `lint_memory_bank()` non-blockingly in `/cortex/analyze`, emitting `## Memory Bank Health` in reports, and adding integration coverage for prompt/tool wiring — files: .cortex/synapse/prompts/analyze.md, src/cortex/tools/synapse/prompts_content.py, tests/integration/test_analyze_context_effectiveness_prompt.py, tests/tools/test_prompts_agents.py
- 2026-04-07: Wired Step 5 `stale_threshold_days` config through `lint_memory_bank`, documented `.cortex/config/lint-config.json` in `docs/guides/lint-config.md`, and added configured-threshold unit coverage — files: src/cortex/tools/lint/lint_memory_bank.py, src/cortex/tools/lint/memory_bank_lint_checks.py, tests/unit/tools/lint/test_lint_memory_bank.py, docs/guides/lint-config.md
