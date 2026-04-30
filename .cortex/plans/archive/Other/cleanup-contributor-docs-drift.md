---
title: "Resolve contributor documentation drift and conflicting quality workflow instructions"
component: docs
work_type: cleanup
status: PENDING
priority: medium
created: 2026-03-22
depends_on:
  - fix-roadmap-memory-bank-consistency
sources:
  - "Codex audit: Contributor Documentation Drift / Instruction Conflicts (Medium-High)"
---

## Goal

Eliminate stale Memory Bank path references in contributor documentation (canonical: `.cortex/memory-bank/`; remove documentation that implied the pre-migration IDE path) and produce a single canonical matrix that clearly separates the human local workflow from the agent MCP-first workflow, so contributors and agents follow consistent, non-conflicting quality paths.

## Context

The Codex audit found two categories of drift:

1. **Stale paths**: [contributing.md](../../docs/development/contributing.md) still described Memory Bank under `.cursor/` in the project structure section instead of `.cortex/memory-bank/`.
2. **Conflicting workflows**: The contributing guide prescribed direct `black` + `isort` invocation for quality, while `AGENTS.md` mandates the MCP-first quality path (`run_quality_gate()`, `fix_quality_issues()`). New contributors and agents can follow either path, leading to inconsistent checks and avoidable PR churn.

This plan depends on `fix-roadmap-memory-bank-consistency` being completed first so canonical paths are confirmed before being documented.

## Implementation Steps

### Step 1 — Audit all documentation for stale references

1. Read `docs/development/contributing.md` in full.
2. Read `AGENTS.md` in full.
3. Grep all `*.md` files under the repo root and `docs/` for legacy Memory Bank path patterns, stray `cursor-memory-bank`, and incorrect `.cursor/` directory docs.
4. Compile a list of all stale references with file + line number.

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| All legacy contiguous IDE Memory Bank path occurrences found | `**/*.md` | — |
| All `.cursor/` path refs that should be `.cortex/` found | `**/*.md` | — |
| Inventory is complete | Grep output | — |

### Step 2 — Update project structure section in contributing guide

1. Replace pre-migration Memory Bank path references with `.cortex/memory-bank`.
2. Replace any `.cortex/synapse/rules/` references with `.cortex/synapse/rules/` (or MCP rules resource) as appropriate.
3. Verify the updated structure section matches the actual directory layout on disk (`Glob` on `.cortex/**`).

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| No legacy contiguous IDE Memory Bank path remains | `docs/development/contributing.md` | same |
| Updated paths exist on disk | `.cortex/` directory | — |
| Markdown lint passes | `run_docs_gate()` | — |

### Step 3 — Create canonical workflow matrix

1. In `docs/development/contributing.md`, replace the existing quality/setup instructions with a two-column matrix:

   | Task | Human (local) | Agent (MCP) |
   |---|---|---|
   | Format code | `uv run black src/ tests/` | `fix_quality_issues()` |
   | Lint/type-check | `uv run ruff check src/` + `uv run pyright src/` | `run_quality_gate()` |
   | Run tests | `uv run pytest` | `run_quality_gate()` |
   | Fix all quality issues | `uv run black src/ && uv run ruff check --fix src/` | `fix_quality_issues()` |
   | Validate docs/memory bank | `uv run rumdl check --fix .` | `run_docs_gate()` |

2. Add a note: "Agents MUST use the MCP column. Direct formatter/linter invocation by agents is a governance violation per `AGENTS.md`."
3. Remove the old conflicting instructions.

#### Verification Checklist — Step 3

| What to check | Search scope | Files to re-read |
|---|---|---|
| Matrix present and complete | `docs/development/contributing.md` | same |
| Old conflicting `black`/`isort` instructions removed | same | — |
| Agent-restriction note present | same | — |
| Markdown lint passes | `run_docs_gate()` | — |

### Step 4 — Add docs consistency test

1. In `tests/unit/`, add tests that:
   - Read `docs/development/contributing.md`.
   - Assert no legacy contiguous IDE Memory Bank path substring is present (same literal the regression suite uses in code).
   - Assert the canonical workflow matrix table header row is present (guards against accidental deletion).
   - Optionally scan all `*.md` files for that legacy substring.
2. The test must be deterministic and fast (< 1s, no filesystem side effects beyond reading).

#### Verification Checklist — Step 4

| What to check | Search scope | Files to re-read |
|---|---|---|
| Test file created | `tests/unit/` | New test file |
| Test passes | `run_quality_gate()` | — |
| Test name follows `test_functionality_when_condition` convention | New test file | — |

### Step 5 — Run quality gate and update memory bank

1. Call `run_quality_gate()` — must pass with zero errors.
2. Call `run_docs_gate()` — must pass with zero violations.
3. Update `activeContext.md` with a completed entry for this plan.

## Dependencies

- `fix-roadmap-memory-bank-consistency` must be completed first (canonical paths confirmed before documenting them).

## Success Criteria

- Zero occurrences in any `*.md` file of the legacy contiguous IDE Memory Bank path substring enforced by the regression test.
- Contributing guide contains a single canonical human/agent workflow matrix.
- Regression tests fail if the stale path or matrix header is removed.
- `run_quality_gate()` and `run_docs_gate()` both pass.

## Testing Strategy (95% coverage target)

- Unit tests: `test_contributing_md_has_no_stale_cursor_paths_when_checked` — asserts contributing guide clean; optional repo-wide markdown scan.
- Unit test: `test_contributing_md_has_workflow_matrix_when_rendered` — asserts the matrix table header row is present.
- Both tests are pure file reads; no mocking required.
- Docs gate must pass on all modified `.md` files.
