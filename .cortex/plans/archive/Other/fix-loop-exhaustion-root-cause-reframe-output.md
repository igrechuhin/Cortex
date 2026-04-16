---
title: "Fix-Loop Exhaustion — Root-Cause Reframe Output"
component: "synapse-fix-workflow"
work_type: "docs"
status: "PENDING"
priority: "Medium"
created: "2026-04-16"
depends_on: []
---

## Goal

Add a mandatory post-exhaustion analysis block to the `/cortex/fix` workflow so that when the 3-iteration limit is reached, the agent produces a root-cause hypothesis, a reformulated brief, and an explicit directive to open a new session instead of retrying the same approach.

## Context

When the fix loop hits its 3-iteration limit (enforced in `.cortex/synapse/prompts/fix.md` line 147 and mirrored in `fix-tests.md` / `fix-quality.md`), the agent stops and reports "unresolvable issues" — a flat list of what failed. There is no guidance on *why* it failed or *what the user should do next*.

The insight from ai-coding-kb (battle-tested at Tinkoff Bank): after exhausting iterations, the root problem is almost always the *approach*, not the implementation details. Retrying the same strategy in a new session repeats the same failure. The correct action is to restart with a corrected brief — a concrete restatement of what needs to change in the approach.

Without this prompt change, users either retry blindly (wasting sessions) or manually diagnose what the agent should surface automatically.

## Scope

**in_scope**

- Add a "Post-exhaustion analysis" block to `.cortex/synapse/prompts/fix.md` immediately after the GATE line (currently "After 3 failed fix-and-verify cycles, STOP and report unresolvable issues.").
- Mirror the same block in `.cortex/synapse/cursor-agents/fix-tests.md` after the "Repeat up to 3 iterations. STOP after 3 with unresolvable issue report." statement.
- Mirror the same block in `.cortex/synapse/cursor-agents/fix-quality.md` after the ABORT directive in Step 2.
- Each block requires three outputs: (a) root-cause hypothesis paragraph, (b) reformulated brief with corrected constraint/approach, (c) explicit directive not to retry in the current session.

**out_of_scope**

- Changes to any Python source files, tests, or infrastructure code.
- Changes to other prompts or cursor-agents beyond the three listed above.
- Changes to the iteration limit (remains 3).
- Changes to how failures are detected or reported before the limit is reached.
- Adding the block to `fix-docs.md` (docs target failures are structural/sync issues, not approach failures).

## Approach

The fix is a prompt-only enrichment applied at the exact point where each file currently terminates on exhaustion. In `fix.md`, the GATE line at line 147 currently says "STOP and report unresolvable issues" — the new block is inserted immediately after this sentence. In `fix-tests.md`, the equivalent is the "Repeat up to 3 iterations. STOP after 3 with unresolvable issue report." sentence at line 60. In `fix-quality.md`, the equivalent is the ABORT directive in Step 2.

Each insertion is a standalone fenced section titled `### Post-Exhaustion Analysis (required when limit reached)` containing three mandatory sub-items labeled (a), (b), (c). The explicit directive uses imperative language consistent with the `⛔ GATE` formatting style already used throughout the fix workflow.

The three files share the same conceptual exhaustion point but differ in surrounding text, so each insertion point must be located precisely by reading surrounding lines before editing.

## Implementation Steps

1. Read `.cortex/synapse/prompts/fix.md` lines 145–155 to confirm the exact text of the GATE line and identify the insertion point after "STOP and report unresolvable issues."
2. Insert the Post-Exhaustion Analysis block into `fix.md` immediately after that line (before the `### 🛠️ quality Target` heading).
3. Read `.cortex/synapse/cursor-agents/fix-tests.md` lines 55–65 to confirm the exact text of the iteration-limit sentence and its surrounding context.
4. Insert the Post-Exhaustion Analysis block into `fix-tests.md` immediately after that sentence.
5. Read `.cortex/synapse/cursor-agents/fix-quality.md` lines 25–38 to confirm the ABORT / max-3-iterations line and its position relative to the iteration body.
6. Insert the Post-Exhaustion Analysis block into `fix-quality.md` at the end of the iteration section — positioned so it fires only when all 3 iterations are exhausted (after the iteration body, not inside it).
7. Read all three modified files back in full to self-verify: (a) insertion is at the correct location, (b) all three sub-items are present, (c) no surrounding structure was broken, (d) markdown renders correctly.
8. Run `autofix()` and `run_quality_gate()` to confirm no markdown lint errors were introduced.

## Verification Checklist

- **fix.md insertion**: `Grep` for "Post-Exhaustion Analysis" in `.cortex/synapse/prompts/fix.md`; confirm it appears after the GATE line and before `### 🛠️ quality Target`.
- **fix-tests.md insertion**: `Grep` for "Post-Exhaustion Analysis" in `.cortex/synapse/cursor-agents/fix-tests.md`; confirm it appears after the iteration-limit sentence.
- **fix-quality.md insertion**: `Grep` for "Post-Exhaustion Analysis" in `.cortex/synapse/cursor-agents/fix-quality.md`; confirm it appears after the ABORT line and outside the iteration body.
- **Three sub-items**: `Grep` for labels "(a)", "(b)", "(c)" in each file to confirm all three analysis components are present.
- **Explicit directive text**: `Grep` for "Do NOT retry in this session" in all three files to confirm the directive is present verbatim.
- **Markdown lint**: run `run_quality_gate()` after all edits; confirm zero markdown lint errors in the three modified files.
- **Files to re-read after changes**: `.cortex/synapse/prompts/fix.md`, `.cortex/synapse/cursor-agents/fix-tests.md`, `.cortex/synapse/cursor-agents/fix-quality.md`.

## Dependencies

- No other plans depend on this.
- The three target files are in the `.cortex/synapse` submodule — confirm the submodule worktree is clean before editing, per `submodule_hygiene` rules in the fix workflow itself.

## Success Criteria

- Searching for "Post-Exhaustion Analysis" returns exactly one match in each of the three files.
- Each match contains sub-items (a) root-cause hypothesis, (b) reformulated brief, (c) explicit directive.
- The string "Do NOT retry in this session" is present in all three files.
- `run_quality_gate()` returns no markdown lint failures after edits.
- No other sections of the three files were modified (diff is confined to the insertion points only).

## Testing Strategy

Target: validation via grep/read assertions — this is prompt-only work with no executable unit tests.

- **Positive case**: after inserting the block, `Grep` for "Post-Exhaustion Analysis" in each file returns exactly one match at the correct location.
- **Structural case**: read each file in full after edit and confirm surrounding headings and step numbers are intact.
- **Content case**: `Grep` for "(a)", "(b)", "(c)" within the inserted block in each file to confirm all three required outputs are present.
- **Directive case**: `Grep` for "Do NOT retry in this session" across the three files to confirm exact wording.
- **Lint case**: `run_quality_gate()` exits clean; `autofix()` returns no markdown changes needed after the manual edits.
- **Negative case**: confirm `fix-docs.md` was NOT modified (search for "Post-Exhaustion Analysis" returns no match in that file).

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Submodule worktree is dirty when edits are attempted | Check `git status .cortex/synapse` before any edits; stash or commit submodule changes first per fix.md submodule exception rules |
| Insertion disrupts surrounding markdown structure | Read 10 lines before and after each insertion point; self-verify with full file read-back after each edit |
| Markdown lint violations introduced by the new block | Use consistent ATX heading style (`###`) matching existing file style; run `autofix()` after each file edit |
| "ABORT" line in fix-quality.md is inside an iteration body, making placement ambiguous | Read Step 2 in full to locate the outer iteration boundary; place block outside the iteration body |
| Wording diverges across the three files | Draft the canonical block text once and copy verbatim; adjust only surrounding connective text |
