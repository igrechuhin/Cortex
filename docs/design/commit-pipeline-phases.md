# Commit Pipeline Phases

Canonical phase definitions for the `/cortex/commit` pipeline.

## Overview

The commit pipeline is organized into four sequential phases. Each phase
has a clear scope, defined inputs and outputs, and explicit failure
semantics. The pipeline stops at the first phase that fails and
recommends targeted helper commands instead of attempting open-ended
debugging.

```text
Phase A          Phase B             Phase C              Phase D
Preflight  --->  Docs & Memory  ---> Git Operations  ---> Session
Checks           Bank Sync           & Commit              Analysis
```

## Phase A: Preflight Checks

**Scope**: Ensure the codebase is clean (no lint, type, format, quality
or test failures) before touching documentation or making commits.

**Pre-requisite**: Rules must be loaded (via `rules()` MCP tool or
direct file read) before any code-modifying step runs.

### Phase A — Steps Included

| Step | Name | Agent | Description |
|------|------|-------|-------------|
| 0 | Fix Errors | error-fixer | Auto-fix lint and format errors |
| 0.5 | Quality Preflight | quality-checker | Fail-fast quality gate |
| 1 | Code Formatting | code-formatter | Format all source files |
| 1.5 | Markdown Linting | markdown-linter | Fix markdown lint errors |
| 2 | Type Checking | type-checker | Verify type safety (zero errors and warnings) |
| 3 | Code Quality | quality-checker | Lint, file sizes, function lengths |
| 4 | Test Execution | test-executor | Run tests; 100% pass rate and >=90% coverage |

### Phase A — Inputs

- Working tree with staged and unstaged changes.
- Loaded rules context (coding standards, testing standards).

### Phase A — Outputs

- Clean codebase: zero lint errors, zero type errors/warnings, zero
  quality violations, all tests passing with coverage >= 90%.
- Structured JSON results from `execute_pre_commit_checks()` for each
  check category.

### Phase A — Failure Semantics

- **Any check fails**: Stop the pipeline. Do not proceed to Phase B.
- **Recommended recovery**: Use targeted helper commands such as
  `/cortex/fix_tests`, `/cortex/fix_quality`, or the
  `fix_quality_issues()` MCP tool to resolve specific failures, then
  re-run `/cortex/commit`.
- **Zero-errors policy**: Pre-existing errors are not acceptable.
  Every error (new or old) must be fixed before the pipeline can
  advance.

### Phase A — Execution Order

Steps 0 through 4 run **strictly sequentially**. Each step depends on
the previous step completing successfully (e.g., formatting must happen
before type checking, quality must pass before tests run).

---

## Phase B: Documentation and Memory Bank Sync

**Scope**: Ensure all memory bank files, roadmap, plans, and timestamps
are up-to-date and internally consistent before committing.

### Phase B — Steps Included

| Step | Name | Agent | Description |
|------|------|-------|-------------|
| 5 | Memory Bank Updates | memory-bank-updater | Update activeContext, progress, roadmap |
| 6 | Roadmap Updates | memory-bank-updater | Update roadmap with completed items |
| 7 | Plan Archiving | plan-archiver | Archive completed plans |
| 8 | Archive Validation | plan-archiver | Verify no completed plans remain unarchived |
| 9 | Timestamp Validation | timestamp-validator | Verify YYYY-MM-DD timestamp format |
| 10 | State Verification | (orchestration) | Verify roadmap = future work, activeContext = completed work |

### Phase B — Inputs

- Clean codebase from Phase A (all checks passing).
- Current memory bank file contents (read via `manage_file()`).

### Phase B — Outputs

- Updated memory bank files reflecting current session work.
- All completed plans archived to correct directories.
- Timestamps validated.
- Roadmap and activeContext in consistent state (no overlap).

### Phase B — Failure Semantics

- **Timestamp violations**: Block commit; fix timestamps and re-validate.
- **Unarchived completed plans**: Block commit; archive plans first.
- **State inconsistency (roadmap/activeContext overlap)**: Fix inline
  by moving completed items from roadmap to activeContext, then proceed.
- **Memory bank write errors**: Block commit; investigate MCP tool
  health.

### Phase B — Execution Order

Steps 5-8 run **strictly sequentially** (they modify shared files).

Steps 9, 10, and 11 (Phase C) form a **parallel validation block**:
they are logically independent (read-only validators plus submodule
handling) and may run concurrently when the platform supports it. All
three must complete before Phase C's final gate (Step 12).

### Safe Update Tools

Memory bank updates use dedicated safe-update MCP tools to avoid
corruption from full-content writes:

- `remove_roadmap_entry()` for removing completed roadmap bullets.
- `append_progress_entry()` for adding progress entries.
- `append_active_context_entry()` for adding completed work entries.
- `complete_plan()` for combined roadmap removal, progress/activeContext
  update, and plan archival.

---

## Phase C: Submodule and Git Operations

**Scope**: Handle Synapse submodule state, run a final sanity check
(re-verification of all code quality), then commit and push.

### Phase C — Steps Included

| Step | Name | Agent | Description |
|------|------|-------|-------------|
| 11 | Submodule Handling | (orchestration) | Commit and push Synapse submodule changes |
| 12 | Final Validation Gate | (orchestration) | Mandatory re-verification of all checks |
| 13 | Commit Creation | (orchestration) | Stage changes, generate message, git commit |
| 14 | Push Branch | (orchestration) | Push to remote |

### Step 12 Sub-steps

The final validation gate re-runs all checks to catch issues introduced
during Phase B (documentation updates, new files, code changes):

| Sub-step | Check | Tool Call |
|----------|-------|-----------|
| 12.0 | Markdown re-validation | `fix_markdown_lint(check_all_files=True)` |
| 12.1 | Format fix + check + CI parity | `execute_pre_commit_checks(checks=["format"])` then `checks=["format_ci_parity"]` |
| 12.2 | Type check | `execute_pre_commit_checks(checks=["type_check"])` |
| 12.3 | Quality (lint + type_check) | `execute_pre_commit_checks(checks=["quality"])` |
| 12.4 | Test naming | `execute_pre_commit_checks(checks=["test_naming"])` |
| 12.5 | Markdown lint (all files) | `fix_markdown_lint(check_all_files=True)` |
| 12.6 | Quality re-check (sizes, lengths) | `execute_pre_commit_checks(checks=["quality"])` |
| 12.7 | Tests with coverage | `execute_pre_commit_checks(checks=["tests"])` |

### Phase C — Inputs

- Updated memory bank and documentation from Phase B.
- Synapse submodule state.

### Phase C — Outputs

- Git commit containing all changes (including submodule pointer update).
- Changes pushed to remote.

### Phase C — Failure Semantics

- **Submodule has uncommitted changes after Step 11**: Block commit.
- **Any Step 12 check fails**: Block commit. Fix issues, re-run Step 12
  from the beginning. Any code change during Step 12 requires re-running
  format and quality checks.
- **Step 12 is MANDATORY**: Cannot be skipped, bypassed, or assumed
  to have passed.
- **Zero-errors policy applies**: All checks in Step 12 use the same
  zero-errors tolerance as Phase A.

### Phase C — Execution Order

Step 11 runs after the parallel block (Steps 9-10-11) completes.
Steps 12.0 through 12.7 run **strictly sequentially** within Step 12.
Steps 13 and 14 run sequentially after Step 12 passes.

### Git Write Preconditions

Before `git add`, `git commit`, or `git push`:

1. User explicitly requested commit (via `/cortex/commit`).
2. All validation gates (Steps 0-12) passed.
3. Step 12.2 type check was executed and returned success with 0 errors.

---

## Phase D: Session Analysis

**Scope**: Run end-of-session analysis after a successful commit.

The Analyze (End of Session) prompt (`analyze.md`) uses a lightweight phase model: (1) Context & rules load — memory bank and rules via `manage_file()` and `rules()`; (2) Analysis & insights — `analyze_context_effectiveness()`, session data, usage stats; (3) Outputs & plans — write report to reviews directory (path from `get_structure_info()`), optionally run Create Plan for improvement recommendations. Paths resolved via Cortex MCP; no hardcoded `.cortex/` paths.

### Phase D — Steps Included

| Step | Name | Agent | Description |
|------|------|-------|-------------|
| 15 | Analyze | (orchestration) | Run Analyze (End of Session) prompt |

### Phase D — Inputs

- Successful commit and push from Phase C.

### Phase D — Outputs

- Context effectiveness analysis saved to reviews directory.
- Optional improvements plan created if patterns detected.

### Phase D — Failure Semantics

- **Analysis failure**: Non-blocking for the commit (commit already
  succeeded). Log the error and report to user.

### Phase D — Execution Order

Runs only after Phase C completes successfully (commit created and
pushed).

---

## Step-to-Phase Mapping

Complete mapping of every existing commit step to its canonical phase:

| Step | Phase | Category |
|------|-------|----------|
| Pre-Step: Load Rules | A (prerequisite) | Rules context |
| 0: Fix Errors | A | Code fixes |
| 0.5: Quality Preflight | A | Code quality |
| 1: Code Formatting | A | Code formatting |
| 1.5: Markdown Linting | A | Documentation quality |
| 2: Type Checking | A | Type safety |
| 3: Code Quality | A | Code quality |
| 4: Test Execution | A | Testing |
| 5: Memory Bank Updates | B | Documentation sync |
| 6: Roadmap Updates | B | Documentation sync |
| 7: Plan Archiving | B | Plan management |
| 8: Archive Validation | B | Plan management |
| 9: Timestamp Validation | B | Validation |
| 10: State Verification | B | Validation |
| 11: Submodule Handling | C | Git operations |
| 12: Final Validation Gate | C | Re-verification |
| 13: Commit Creation | C | Git operations |
| 14: Push Branch | C | Git operations |
| 15: Analyze | D | Session analysis |

---

## Invariants Preserved

The following invariants from the current pipeline are preserved across
all phases:

1. **Zero-errors policy**: Any error (lint, type, format, quality, test)
   blocks the commit. No exceptions for pre-existing errors.
2. **Coverage threshold**: Tests must achieve >= 90% coverage.
3. **Memory bank contracts**: activeContext = completed work only;
   roadmap = future/upcoming work only; no overlap.
4. **Submodule cleanliness**: Synapse submodule must be clean (committed
   and pushed) before parent commit.
5. **Final gate is mandatory**: Step 12 cannot be skipped; it catches
   issues introduced during Phases A-B.
6. **Sequential state-changing steps**: Steps 0-8 and 12-14 are strictly
   sequential. Steps 9-11 may run in parallel (read-only validators plus
   submodule handling).
7. **User-initiated only**: Commits and pushes only happen when
   explicitly requested via `/cortex/commit`.

---

## Future Work (Steps 2-6 of This Plan)

This document serves as the foundation for subsequent plan steps:

- **Step 2**: Introduce phase-level MCP tools or helpers that
  encapsulate phase logic (e.g., `run_preflight_checks`,
  `sync_docs_and_memory_bank`).
- **Step 3**: Refactor `/cortex/commit` prompt to orchestrate phase
  tools instead of micromanaging individual checks.
- **Step 4**: Add focused helper commands for common failure modes
  (`/cortex/fix_tests`, `/cortex/fix_quality`, `/cortex/docs_sync`).
- **Step 5**: Slim and centralize rules to reduce prompt size.
- **Step 6**: Update existing session-optimization plans and AGENTS.
