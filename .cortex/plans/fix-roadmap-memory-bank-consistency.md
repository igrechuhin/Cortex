---
title: "Reconstruct roadmap backlog and enforce docs-gate consistency invariant"
component: memory-bank
work_type: fix
status: PENDING
priority: high
created: 2026-03-22
depends_on: []
sources:
  - "Codex audit: Planning & Memory-Bank Consistency (High)"
---

## Goal

Restore deterministic planning by eliminating the state mismatch between an empty `roadmap.md` and a `progress.md` that contains PARTIAL entries and ongoing initiatives. Add a docs-gate check that fails when this inconsistency recurs.

## Context

The Codex audit found that `roadmap.md` has no active blockers, work items, or pending plans, while `activeContext.md` and `progress.md` still reference ongoing/partial initiatives and future work. The project's own implement workflow selects the next step from the first PENDING roadmap item; an empty roadmap causes no-op planning sessions and breaks automation.

Additionally, there is no automated invariant preventing the roadmap from drifting empty while progress remains incomplete — meaning the drift can silently recur after each fix cycle.

## Implementation Steps

### Step 1 — Audit the current memory bank state

1. Read all 7 core memory bank files:
   - `projectBrief.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`
   - `roadmap.md`, `activeContext.md`, `progress.md`
2. Extract all PARTIAL entries from `progress.md`.
3. Extract all future-work references from `activeContext.md`.
4. Classify each item as:
   - **Needs roadmap entry** — incomplete, has clear next action
   - **Can be closed** — work was actually completed, just not marked
   - **Stale** — no longer relevant, safe to remove

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| All 7 files read | `.cortex/memory-bank/` | All 7 core files |
| PARTIAL entries inventoried | `progress.md` | — |
| Future-work refs inventoried | `activeContext.md` | — |

### Step 2 — Reconstruct prioritized roadmap backlog

1. For each "Needs roadmap entry" item from Step 1, create a roadmap entry with:
   - Section: Blockers / Active Work / Future Enhancements / Pending plans (appropriate)
   - Entry text: concise description, owner if known, success criteria
2. Use `plan(operation="register", ...)` for plan-backed items.
3. Use `update_memory_bank(operation="roadmap_add", ...)` for non-plan backlog items.
4. Minimum target: 3 concrete pending items with success criteria in the roadmap.

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| Roadmap has ≥3 pending items | `roadmap.md` | `.cortex/memory-bank/roadmap.md` |
| No entry duplicated in activeContext | `activeContext.md` | — |
| All entries have success criteria | `roadmap.md` | — |

### Step 3 — Reconcile `progress.md` PARTIAL entries

1. For each PARTIAL entry classified as "Can be closed" in Step 1, update `progress.md` to mark it COMPLETED with a timestamp.
2. For each PARTIAL entry that needs a roadmap item, confirm the roadmap entry from Step 2 exists, then leave `progress.md` as-is (PARTIAL is correct).
3. For stale entries, remove from `progress.md`.

#### Verification Checklist — Step 3

| What to check | Search scope | Files to re-read |
|---|---|---|
| No orphaned PARTIAL without roadmap entry | `progress.md` + `roadmap.md` | Both files |
| Timestamps on newly-closed entries are real | `date` command | `progress.md` |

### Step 4 — Add docs-gate invariant: non-empty roadmap when PARTIAL progress exists

1. Identify where the docs gate validation logic lives (grep for `docs_gate` or `run_docs_gate` in `src/cortex/`).
2. Add a new check: if `progress.md` contains any PARTIAL entries, `roadmap.md` must contain at least one pending item — otherwise gate fails.
3. Write the check as a pure helper function (`_check_roadmap_progress_consistency(progress_content: str, roadmap_content: str) -> list[str]`) returning a list of violation strings.
4. Register the check in the docs-gate runner.
5. Write unit tests: (a) no PARTIAL + empty roadmap → passes; (b) PARTIAL entries + empty roadmap → fails with descriptive message; (c) PARTIAL entries + non-empty roadmap → passes.

#### Verification Checklist — Step 4

| What to check | Search scope | Files to re-read |
|---|---|---|
| Helper function ≤30 lines | New helper file | — |
| Unit tests cover all 3 cases | `tests/unit/` | New test file |
| `run_docs_gate()` includes new check | `src/cortex/` docs-gate module | — |
| Pyright passes | `uv run pyright src/` | — |

### Step 5 — Run quality gate and validate links

1. Call `run_quality_gate()` — must pass with zero errors.
2. Validate all memory bank links after changes.
3. Update `activeContext.md` with a completed entry for this plan.

## Dependencies

- None (self-contained to memory bank files and docs-gate module).

## Success Criteria

- `roadmap.md` contains ≥3 prioritized pending items with success criteria.
- No PARTIAL `progress.md` entry is without a corresponding roadmap item.
- `run_docs_gate()` fails when `progress.md` has PARTIAL entries and `roadmap.md` is empty.
- `run_quality_gate()` passes: zero errors, coverage ≥ 91%.

## Testing Strategy (95% coverage target)

- Unit tests for `_check_roadmap_progress_consistency`: 3 cases (see Step 4).
- Integration test: call `run_docs_gate()` with a synthetic memory bank where PARTIAL exists and roadmap is empty — assert non-zero violation count.
- Regression: existing docs-gate tests must continue to pass unchanged.
