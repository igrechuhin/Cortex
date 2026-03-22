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

Eliminate stale path references in contributor documentation (`.cursor/memory-bank` → `.cortex/memory-bank`) and produce a single canonical matrix that clearly separates the human local workflow from the agent MCP-first workflow, so contributors and agents follow consistent, non-conflicting quality paths.

## Context

The Codex audit found two categories of drift:

1. **Stale paths**: `CONTRIBUTING.md` still references `.cursor/memory-bank` in its project structure section, which was the old location before the `.cortex/` migration.
2. **Conflicting workflows**: `CONTRIBUTING.md` prescribes direct `black` + `isort` invocation for quality, while `AGENTS.md` mandates the MCP-first quality path (`run_quality_gate()`, `fix_quality_issues()`). New contributors and agents can follow either path, leading to inconsistent checks and avoidable PR churn.

This plan depends on `fix-roadmap-memory-bank-consistency` being completed first so canonical paths are confirmed before being documented.

## Implementation Steps

### Step 1 — Audit all documentation for stale references

1. Read `CONTRIBUTING.md` in full.
2. Read `AGENTS.md` in full.
3. Grep all `*.md` files under the repo root and `docs/` for `.cursor/memory-bank`, `.cursor/`, `cursor-memory-bank`.
4. Compile a list of all stale references with file + line number.

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| All `.cursor/memory-bank` occurrences found | `**/*.md` | — |
| All `.cursor/` path refs that should be `.cortex/` found | `**/*.md` | — |
| Inventory is complete | Grep output | — |

### Step 2 — Update project structure section in `CONTRIBUTING.md`

1. Replace all `.cursor/memory-bank` path references with `.cortex/memory-bank`.
2. Replace any `.cursor/rules/` or `.cursor/synapse/` references with `.cortex/rules/` or `.cortex/synapse/` as appropriate.
3. Verify the updated structure section matches the actual directory layout on disk (`Glob` on `.cortex/**`).

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| No `.cursor/memory-bank` occurrences remain | `CONTRIBUTING.md` | `CONTRIBUTING.md` |
| Updated paths exist on disk | `.cortex/` directory | — |
| Markdown lint passes | `run_docs_gate()` | — |

### Step 3 — Create canonical workflow matrix

1. In `CONTRIBUTING.md`, replace the existing quality/setup instructions with a two-column matrix:

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
| Matrix present and complete | `CONTRIBUTING.md` | `CONTRIBUTING.md` |
| Old conflicting `black`/`isort` instructions removed | `CONTRIBUTING.md` | — |
| Agent-restriction note present | `CONTRIBUTING.md` | — |
| Markdown lint passes | `run_docs_gate()` | — |

### Step 4 — Add docs consistency test

1. In `tests/unit/` (or `tests/integration/`), add a test that:
   - Reads `CONTRIBUTING.md`.
   - Asserts no `.cursor/memory-bank` substring is present.
   - Asserts the canonical workflow matrix table header row is present (guards against accidental deletion).
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

- Zero `.cursor/memory-bank` references in any `*.md` file in the repository.
- `CONTRIBUTING.md` contains a single canonical human/agent workflow matrix.
- A regression test fails if the stale path or matrix header is removed.
- `run_quality_gate()` and `run_docs_gate()` both pass.

## Testing Strategy (95% coverage target)

- 1 unit test: `test_contributing_md_has_no_stale_cursor_paths` — asserts no `.cursor/memory-bank` in `CONTRIBUTING.md`.
- 1 unit test: `test_contributing_md_has_workflow_matrix` — asserts the matrix table header row is present.
- Both tests are pure file reads; no mocking required.
- Docs gate must pass on all modified `.md` files.
