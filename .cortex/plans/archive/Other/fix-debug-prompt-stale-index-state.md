---
title: "debug-external-integration.md: Replace static index.corrupted assertion with dynamic verification"
component: cortex/prompts
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-29
depends_on: []
---

## Goal

Remove the static, un-reverifiable claim in `debug-external-integration.md`
Step 4 that `.cortex/index.corrupted` "exists" as a known fact, and replace it
with an instruction to check the actual current state during each debug
session.

The current prompt says "do not re-verify" for this state, which means an
agent in a future session will treat a repaired index as still-corrupted —
potentially skipping `manage_file` reads unnecessarily or, worse, deleting a
healthy index.

## Context

`debug-external-integration.md` Step 4 — "Snapshot TradeWing `.cortex/`
Layout" (current text):

> Known integration facts (do not re-verify, just record):
>
> - `.cortex/index.corrupted` — **exists** (index was corrupted; blocks
>   `manage_file` reads until repaired)

This was accurate at the time the prompt was written but becomes a latent
hazard the moment the index is repaired:

- An agent following "do not re-verify" will skip the glob result for
  `index.corrupted` and assume it is present.
- If it proceeds to "delete it and `index.json`" (from the Notes section), it
  deletes a healthy index, triggering an unnecessary rebuild.
- If it skips `manage_file` reads "because the index is corrupted", it operates
  blind even though the index is healthy.

The "do not re-verify" instruction exists to save tokens by avoiding redundant
checks for stable structural facts. Index health is NOT a stable structural
fact — it changes between sessions.

## Implementation Steps

### Step 1: Classify the "Known integration facts" list

Read the full list under Step 4 "Known integration facts" and categorise each
item as:

- **Stable structural fact** (e.g. submodule present, plans directory
  migrated): safe to keep as "do not re-verify" — these don't change unless
  explicitly modified.
- **Dynamic state** (e.g. index health, file presence that can be repaired):
  must be re-verified each session.

#### Verification Checklist — Step 1

| What to check | Where | Files |
|---------------|-------|-------|
| All "Known integration facts" bullets reviewed | Read Step 4 | `.cortex/prompts/debug-external-integration.md` |
| Classification table produced (stable vs dynamic) | Agent working notes | — |

### Step 2: Split the facts list into stable and dynamic sections

In `.cortex/prompts/debug-external-integration.md`, Step 4, replace the
single "Known integration facts (do not re-verify, just record):" block with
two labelled subsections:

**Stable structural facts (cached — no re-verification needed):**

> These were established by prior migration work and do not change between
> debug sessions unless explicitly modified:
>
> - `.cortex/synapse/` — Synapse git submodule present
> - `.cortex/memory-bank/` — 7 core files migrated; `projectBrief.md` uses
>   camelCase B
> - `.cortex/plans/` — plans migrated from the prior location
> - Legacy links should point to `.cortex/` counterparts
> - `.cortex/config/` — 3 config JSON files should exist
>   (`validation.json`, `optimization.json`, `usage_tracking.json`)
>
> Flag anything that diverges from the above as a new finding.

**Dynamic state (re-verify each session using the Glob output):**

> Check the actual Glob output from this session to determine current state:
>
> - **`.cortex/index.corrupted`** — check for presence in the Glob output.
>   - If present: index was corrupted. Delete both `index.corrupted` and
>     `index.json` from TradeWing `.cortex/`, then call `session()` to
>     trigger rebuild before testing memory bank reads.
>   - If absent: index is healthy. Do NOT attempt to delete or rebuild.
> - **`.cortex/index.json`** — check for presence in the Glob output. If
>   missing (and no `.corrupted` marker): call `session()` to trigger a fresh
>   index build.

#### Verification Checklist — Step 2

| What to check | Where | Files |
|---------------|-------|-------|
| Two-section structure present | Read Step 4 after edit | `.cortex/prompts/debug-external-integration.md` |
| "do not re-verify" no longer applies to `index.corrupted` | Grep `do not re-verify` | `.cortex/prompts/debug-external-integration.md` |
| Stable facts list is complete (all 5 bullets preserved) | Compare before/after | — |
| Dynamic state instructions are unambiguous (if/else branching) | Read new section | — |

### Step 3: Update the Notes section for index repair

The existing **Notes** section at the bottom of the prompt contains:

> **Index repair**: if `.cortex/index.corrupted` is still present, delete it
> and `index.json` from TradeWing `.cortex/`, then call `session()` to trigger
> rebuild before testing memory bank reads.

Update this note to remove the implied assumption that the file is "still
present":

> **Index repair**: if Step 4 dynamic-state check found `.cortex/index.corrupted`
> present in the Glob output, delete both `index.corrupted` and `index.json`
> from TradeWing `.cortex/`, then call `session()` to trigger rebuild before
> testing memory bank reads. If `index.corrupted` was NOT present in the Glob
> output, skip this step entirely.

#### Verification Checklist — Step 3

| What to check | Where | Files |
|---------------|-------|-------|
| Notes section index repair is conditional on Glob output | Read Notes section | `.cortex/prompts/debug-external-integration.md` |
| "still present" assumption removed | Grep `still present` | `.cortex/prompts/debug-external-integration.md` |

### Step 4: Quality gate

Run `fix_quality_issues()` then `run_docs_gate()`. Markdown-only change.

#### Verification Checklist — Step 4

| What to check | Where | Files |
|---------------|-------|-------|
| `docs_phase_passed: true` | `run_docs_gate()` result | — |
| Zero new markdown lint errors | `fix_quality_issues()` output | — |

## Dependencies

- `.cortex/prompts/debug-external-integration.md` (edit target)
- `run_docs_gate()` and `fix_quality_issues()` MCP tools

## Success Criteria

1. Step 4 no longer says "do not re-verify" for `index.corrupted`.
2. `index.corrupted` check is driven by the actual Glob output each session.
3. Stable structural facts remain cached (no unnecessary re-verification
   overhead).
4. Notes section index-repair guidance is conditional, not assumed.
5. `run_docs_gate()` passes with zero markdown errors.
6. No source file changes.

## Testing Strategy

Documentation-only change. Testing:

- `fix_quality_issues()` + `run_docs_gate()` for lint-clean output.
- Manual review: mentally run Step 4 with (a) `index.corrupted` present in
  Glob output and (b) absent — confirm different instructions fire in each case.
- Grep for "do not re-verify" after edit to confirm it is absent from the
  index.corrupted line.

Coverage target: N/A. Docs gate must pass (100%).
