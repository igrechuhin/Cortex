---
title: "fix.md: Explicit submodule-only commit carve-out when submodule_hygiene blocks run_quality_gate"
component: synapse/prompts
work_type: fix
status: PENDING
priority: high
created: 2026-03-29
depends_on: []
---

## Goal

Eliminate the prompt-instruction contradiction in `fix.md` where the blanket
"Do NOT commit or push" rule conflicts with the Submodule-First Fix Routing
section that directs agents to commit inside `.cortex/synapse` when
`submodule_hygiene` blocks `run_quality_gate`.

Agents that encounter this today must reason past the contradiction, do the
right thing, and then explicitly flag it (as happened in the TradeWing session
2026-03-29). Future agents should receive an unambiguous rule.

## Context

`fix.md` lines of interest (from current file):

- **Goals (All Targets)** section: *"Do NOT commit or push as part of this
  command; `/cortex/commit` is responsible for the full pipeline."*
- **Submodule-First Fix Routing** section: directs agent to commit inside the
  dirty submodule before continuing root quality/tests/docs gates.
- **Failure Handling** section: does not address submodule commit outcome.

The session transcript (Cursor, 2026-03-29, TradeWing × Cortex integration)
showed:

1. `run_quality_gate` failed immediately on `submodule_hygiene` (only check
   performed).
2. Agent correctly committed inside `.cortex/synapse`, staged the gitlink, and
   retried — gate passed.
3. Agent appended: *"Optional rule tweak: In `fix.md`, clarify whether a
   submodule-only commit is allowed when `submodule_hygiene` blocks
   `run_quality_gate`, since discarding changes is the only alternative without
   a parent commit."*

Without the carve-out, an agent that literally follows the "no commit" rule
will be stuck: it cannot run quality checks (blocked by `submodule_hygiene`),
cannot discard the submodule changes (they are the work being fixed), and
cannot commit the superproject (that is `/cortex/commit`'s job).

## Implementation Steps

### Step 1: Add explicit exception note under "Goals (All Targets)"

In `.cortex/synapse/prompts/fix.md`, locate the **Goals (All Targets)**
section. After the existing bullet point:

> "Do NOT commit or push as part of this command; `/cortex/commit` is
> responsible for the full pipeline."

Add the following exception bullet:

> **Exception — submodule commit**: A commit *inside* `.cortex/synapse` (or
> another submodule) IS allowed when `submodule_hygiene` blocks
> `run_quality_gate` and the only alternatives are discarding valid in-progress
> submodule changes or leaving the gate permanently broken. The *superproject*
> must NOT be committed. After the submodule commit, stage the updated gitlink
> (`git add .cortex/synapse`) so the next `run_quality_gate` sees a clean,
> in-sync submodule.

#### Verification Checklist — Step 1

| What to check | Where | Files |
|---------------|-------|-------|
| Exception bullet present verbatim | Read `fix.md` after edit | `.cortex/synapse/prompts/fix.md` |
| "Goals" heading still intact | Grep for `## Goals` | `.cortex/synapse/prompts/fix.md` |
| No other text was accidentally removed | Diff length ≈ +8–12 lines | — |

### Step 2: Add a clarifying note in "Submodule-First Fix Routing"

In the same file, locate the **Submodule-First Fix Routing → "clean" semantics
for `/fix`** section. At the end of that section (after the "Interpretation
rule"), add:

> **Submodule commit authority**: The Submodule-First routing in this prompt
> has authority to commit inside a submodule when required. This is not a
> violation of the "No commit" goal because (a) the superproject is not
> committed and (b) without the submodule commit the gate cannot proceed at
> all. See the exception note in **Goals (All Targets)** above.

#### Verification Checklist — Step 2

| What to check | Where | Files |
|---------------|-------|-------|
| Authority note present at end of Submodule-First section | Read `fix.md` | `.cortex/synapse/prompts/fix.md` |
| No new markdown lint violations (trailing spaces, heading levels) | `fix_quality_issues()` | — |

### Step 3: Add `submodule_commit_allowed` guidance to Failure Handling

In the **Failure Handling** section of `fix.md`, there is no entry for
`submodule_hygiene` failures. Add one:

> - **`submodule_hygiene` failure in `run_quality_gate`**: Follow
>   **Submodule-First Fix Routing** above. Commit dirty changes inside the
>   submodule, remove any ephemeral untracked files (e.g. `.cache/`), then
>   `git add <submodule>` in the superproject. Retry `run_quality_gate`.
>   This does NOT violate the "No commit" goal — see exception in **Goals
>   (All Targets)**.

#### Verification Checklist — Step 3

| What to check | Where | Files |
|---------------|-------|-------|
| `submodule_hygiene` entry present in Failure Handling | Grep `submodule_hygiene` in `fix.md` | `.cortex/synapse/prompts/fix.md` |
| Cross-reference to Goals exception is accurate | Read surrounding context | — |

### Step 4: Quality gate

Run `fix_quality_issues()` (auto-fixes markdown lint) then `run_docs_gate()`
to confirm no new violations were introduced. This is a markdown-only change
so `run_quality_gate` (full test run) is NOT required; `run_docs_gate` suffices.

#### Verification Checklist — Step 4

| What to check | Where | Files |
|---------------|-------|-------|
| `docs_phase_passed: true` | `run_docs_gate()` result | — |
| Zero markdown lint errors in `fix.md` | `fix_quality_issues()` + `run_docs_gate()` | — |

## Dependencies

- `.cortex/synapse/prompts/fix.md` (edit target)
- `run_docs_gate()` and `fix_quality_issues()` MCP tools

## Success Criteria

1. `fix.md` "Goals (All Targets)" contains an explicit exception bullet for
   submodule-only commits when `submodule_hygiene` blocks the gate.
2. "Submodule-First Fix Routing" section cross-references the exception and
   asserts the submodule commit authority.
3. "Failure Handling" section contains a `submodule_hygiene` entry with
   remediation steps.
4. `run_docs_gate()` passes with no markdown errors.
5. No changes to any source files (`.py`, `.ts`, etc.).

## Testing Strategy

This is a documentation-only change. Testing is:

- `fix_quality_issues()` + `run_docs_gate()` to confirm zero lint errors.
- Manual review: read the three modified sections in order and confirm the
  contradiction is resolved and the cross-references are consistent.
- Regression: grep `fix.md` for "Do NOT commit" to confirm the base rule is
  still present (not removed, only excepted).

Coverage target: N/A (no executable code changed). Docs gate must pass (100%).
