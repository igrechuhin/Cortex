---
title: "Decompose oversized tool modules by responsibility boundaries"
component: tools
work_type: refactoring
status: PENDING
priority: medium
created: 2026-03-21
depends_on: []
---

## Goal

Split the largest tool modules and functions to comply with the project's 400-line file / 30-line function limits, improving testability and reducing change risk.

## Context

- **Codex review finding #3**: Several core files exceed 500 lines (`pre_commit_tools.py`, `approval_manager.py`, `similarity_engine.py`, `refactoring_engine.py`, `structure/models.py`). Several functions are oversized (`get_link_graph`, `apply_refactoring`, `manage_file`, `validate_links`, `rules`).
- Project convention: files <= 400 logical lines, functions <= 30 logical lines.
- This is a multi-phase effort; this plan defines decomposition targets and the first batch.

## Implementation Steps

### Step 1: Audit current file/function sizes

Run `make check-file-sizes` (or equivalent) and record all files and functions that exceed limits. Prioritize by: (a) frequency of change, (b) number of responsibilities, (c) test coverage gaps.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| File size violations | `make check-file-sizes` output | Violation list |
| Function size violations | `make check-function-sizes` output | Violation list |
| Exemption list | `.cortex/synapse/scripts/` | Size check scripts |

### Step 2: Decompose top-priority module (batch 1)

Pick the highest-impact module from the audit. Split by responsibility boundaries:

- **I/O layer**: File reads, subprocess calls, network.
- **Validation layer**: Input checks, schema enforcement.
- **Orchestration layer**: Workflow coordination, sequencing.
- **Rendering layer**: Output formatting, response construction.

Create new modules within the same package. Preserve public API via `__init__.py` re-exports.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Imports of decomposed module | `src/cortex/` | All importers |
| Re-exports in **init**.py | Target package | `__init__.py` |

### Step 3: Decompose second module (batch 1)

Repeat for the second-highest-priority module.

### Step 4: Update tests and verify

Move/split tests to match new module boundaries. Verify all tests pass and coverage is maintained.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Tests importing old module paths | `tests/` | Affected test files |
| Coverage for new modules | Coverage report | New modules |

### Step 5: Document architecture guardrails

Add a section in `CONTRIBUTING.md` documenting the max file/function size policy, exemption process, and quarterly review cadence.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Size governance docs | `docs/` or `CONTRIBUTING.md` | Relevant doc |

## Dependencies

- None for batch 1. Later batches may depend on batch 1 patterns.

## Success Criteria

- Top 2 oversized modules split to <= 400 logical lines each.
- All oversized functions in those modules split to <= 30 logical lines.
- Public API preserved (no breaking changes for callers).
- All tests pass; coverage maintained.
- Quality gate passes.

## Testing Strategy

- Existing tests transferred to new module boundaries.
- Import-level tests verify re-exports work.
- Target: 95% coverage maintained across split modules.
