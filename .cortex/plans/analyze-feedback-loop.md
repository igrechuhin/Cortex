---
title: "Analyze Feedback Loop: Post-Prompt Self-Improvement"
component: synapse
work_type: feature
status: IN_PROGRESS
priority: high
created: 2026-03-31
depends_on: []
---

## Analyze Feedback Loop: Post-Prompt Self-Improvement

## Goal

Every Cortex prompt (`.cortex/synapse/prompts/*.md` and `.cortex/prompts/*.md`) should automatically invoke `/cortex/analyze` at the end of its execution. The analyze prompt, in turn, should produce actionable artifacts from its findings — creating or improving Skills, Plans, and Rules based on what happened in the session.

This closes the self-improvement loop: every task session feeds back into the system's knowledge base.

## Context

Currently `analyze.md` runs on-demand as an end-of-session command. It produces a session report and optionally creates an improvements plan (Step 9), but only if recommendations exist. There is no mechanism to:

1. Trigger analysis automatically after other prompts complete.
2. Route analysis findings to the right artifact type (Skills vs Plans vs Rules).
3. Distinguish between the three output modes based on findings.

The proposed change has two parts:

- **Part A — Trigger**: Each prompt's final step invokes `analyze.md` (or a lightweight "post-prompt hook") after its own work is done.
- **Part B — Router**: `analyze.md` gains a findings-router step that maps findings to one of three artifact types: Skill update, Plan creation/update, or Rule creation/update.

## Implementation Steps

### Step 1 — Audit existing prompts for "final step" insertion points

1. Read each prompt in `.cortex/synapse/prompts/`: `commit.md`, `fix.md`, `review.md`, `create-plan.md`, `implement-next-roadmap-step.md`.
2. Read each prompt in `.cortex/prompts/`: `debug-external-integration.md`, `populate-tiktoken-cache.md`, `validate-roadmap-sync.md`.
3. For each prompt, identify:
   - The final mandatory step before the "Final report" section.
   - Whether it already has any analysis/self-improvement step.
   - Whether the prompt is long-running (commit, implement) or short (validate-roadmap-sync) — this affects hook weight.

#### Step 1 findings (2026-03-31)

- **`.cortex/synapse/prompts/commit.md`**:
  - Final mandatory step before `## Final report`: **Step 16: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after the commit pipeline completes, with a recursion guard for `analyze.md`.
  - Classified as **long-running** (full commit pipeline with multiple phases and gates).
- **`.cortex/synapse/prompts/fix.md`**:
  - Final mandatory step before `## Final report`: **Step 10: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after the fix workflow completes, with a recursion guard.
  - Classified as **long-running** (multi-phase fix pipeline across quality/tests/docs).
- **`.cortex/synapse/prompts/review.md`**:
  - Final mandatory step before `## Final report`: **Step 13: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after the review report, with a recursion guard.
  - Classified as **long-running** (full code review, scoring, and issue tracker workflow).
- **`.cortex/synapse/prompts/create-plan.md`**:
  - Final mandatory step before `## Final report`: **Step 10: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after plan creation, with a recursion guard.
  - Classified as **short** (single-plan creation and roadmap registration).
- **`.cortex/synapse/prompts/implement-next-roadmap-step.md`**:
  - Final mandatory step before `## Final report`: **Step 6: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after the implement pipeline, with a recursion guard.
  - Classified as **long-running** (multi-phase implement pipeline with quality/docs/fix).
- **`.cortex/prompts/debug-external-integration.md`**:
  - Final mandatory step before completion: **Step 7: Post-Prompt Hook (Self-Improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` for debug sessions, with a recursion guard.
  - Classified as **short-to-medium** (debug context loader for TradeWing–Cortex integration).
- **`.cortex/prompts/populate-tiktoken-cache.md`**:
  - Final mandatory step before completion: **Step 5: Post-prompt hook (self-improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after cache population, with a recursion guard.
  - Classified as **short** (one-off cache population workflow).
- **`.cortex/prompts/validate-roadmap-sync.md`**:
  - Final mandatory step before completion: **Step 5: Post-prompt hook (self-improvement)**.
  - Already includes a self-improvement step: invokes `.cortex/synapse/prompts/post-prompt-hook.md` after roadmap validation, with a recursion guard.
  - Classified as **short** (focused validation workflow).

**Verification checklist**:

- What to search for: `## Step [N]` patterns, `## Final report`, `## Success Criteria` in each prompt file.
- Search scope: `.cortex/synapse/prompts/*.md`, `.cortex/prompts/*.md`.
- Files to re-read: each prompt file individually.

### Step 2 — Design the post-prompt hook

Current state (2026-03-31):

- **Option B — Shared hook file** has already been implemented as `.cortex/synapse/prompts/post-prompt-hook.md`.
- The hook runs `analyze.md`-style **Steps 4–9** in a lightweight form and is registered in `prompts-manifest.json` with `type: "hook"`.

Original design options (kept for context):

**Option A — Inline invocation**: Each prompt's final step adds: `After writing the final report, invoke the analyze post-prompt hook by reading \`.cortex/synapse/prompts/analyze.md\` and executing its Steps 4–9 (skip Steps 1–3 since MCP is already healthy).`

**Option B — Shared hook file**: Extract a lightweight `post-prompt-hook.md` (Steps 4–9 of analyze, stripped of health-check preamble) and reference it from each prompt's final step.

**Recommendation / status**: Option B (shared hook) — **implemented**. Remaining work is to refine usage patterns (for example, which prompts should invoke the hook by default), conventions for how callers summarize the hook result, and test coverage around the router behavior.

**Verification checklist**:

- What to search for: any existing `post-prompt` references in prompts or manifests.
- Search scope: `.cortex/synapse/prompts/`, `.cortex/prompts/`, `prompts-manifest.json`.
- Files to re-read: `prompts-manifest.json` (both), `analyze.md`.

### Step 3 — Add findings router to analyze.md

Current state (2026-03-31, revised):

- `analyze.md` already contains **Steps 9a/9b/9c** implementing a three-way router for Skills, Plans, and Rules.
- The post-prompt hook reuses the same routing semantics via its own **Step 9: Improvements Router and Minimal Final Report**.
- **Final report template updated (2026-03-31)**: Added `Skill updated` and `Rule created` rows to the `## Output` table alongside the existing `Plan created` row. Updated `**Rules**` annotation to explain when each row applies. Updated `## Success Criteria` to enumerate all three router outputs instead of listing only "Improvements plan created if recommendations exist".

Original design for the router (for reference):

```text
IF findings include tool/workflow usage patterns or sequences → update/create Skill in .cortex/resources/skills/
IF findings include bugs, missing features, agent improvements → create/update Plan in .cortex/plans/
IF findings include recurring rule violations or new coding standards → create/update Rule in .cortex/synapse/rules/
Multiple output types are not mutually exclusive — emit all that apply.
```

Concrete additions to `analyze.md` (now implemented):

1. **Step 9a — Skill Router**: If optimization report contains tool sequence improvements, inverted usage patterns, or missing skill definitions → update or create Skills under `.cortex/resources/skills/` accordingly.
2. **Step 9b — Plan Router**: If report contains actionable bugs, feature gaps, or agent/script improvements → create/register a plan via `plan(operation="create", ...)` and `plan(operation="register", ...)`.
3. **Step 9c — Rule Router**: If report contains recurring violations of a pattern not yet in rules, or a new standard worth enforcing → create or update rule files under `.cortex/synapse/rules/` and keep `rules-manifest.json` in sync.

**Verification checklist**:

- What to search for: `## Step 9` in `analyze.md`, skill JSON structure in `.cortex/resources/skills/core.json`, rule structure in `.cortex/synapse/rules/general/coding-standards.mdc`.
- Search scope: `analyze.md`, `skills/*.json`, `rules/general/*.mdc`, `rules-manifest.json`.
- Files to re-read: `analyze.md` (full), `skills/core.json`, `rules/general/coding-standards.mdc`.

### Step 4 — Create post-prompt-hook.md

Current state (2026-03-31):

- `.cortex/synapse/prompts/post-prompt-hook.md` already exists with:
  - Clear scope as a lightweight post-prompt hook (non-standalone).
  - Steps 4–9 mirroring the analysis/report/compaction flow from `analyze.md` (health check handled by the caller).
  - A minimal final report section that summarizes which artifacts (Skill/Plan/Rule) were produced.

Remaining work for this step is primarily **docs/usage alignment**:

- Make sure callers use a consistent pattern for recording the hook’s artifact summary in their own final reports.
- Keep the hook description DRY with respect to `analyze.md` so future router changes only need to be made in one place conceptually.

**Verification checklist**:

- What to search for: Steps 4–9 in `analyze.md` (exact text to copy).
- Search scope: `analyze.md`.
- Files to re-read: `post-prompt-hook.md` after writing.

### Step 5 — Update each prompt with hook invocation

Current state (2026-03-31, revised):

- All prompts listed in Step 1 already include a **Post-Prompt Hook (Self-Improvement)** step that invokes `.cortex/synapse/prompts/post-prompt-hook.md`.
- **Recursion guard removed from callers (2026-03-31)**: The copy-pasted "Guard against recursion: When the active prompt is `/cortex/analyze`..." text in all 7 caller prompts was misleading — callers are never `analyze.md`, so this guard never fired. It was removed from `commit.md`, `fix.md`, `review.md`, `create-plan.md`, `implement-next-roadmap-step.md`, `debug-external-integration.md`, `populate-tiktoken-cache.md`, and `validate-roadmap-sync.md`. The guard remains in `post-prompt-hook.md` where it actually belongs.
- **`commit.md` Step 15 corrected (2026-03-31)**: Stale `analyze(target="context")` / `analyze(target="usage_patterns")` calls referencing a non-existent MCP tool were removed from Step 15 (Cleanup). Step 15 now only clears the pipeline state. Analysis is correctly delegated to Step 16 (Post-Prompt Hook). Sequential execution order updated to include Step 16. Success Criteria updated to reference the post-prompt hook instead of "Analyze executed".

Original design for that step (kept as reference for future prompts):

```text
## Step N: Post-Prompt Hook (Self-Improvement)

After writing the final report, invoke the post-prompt hook:
Read `.cortex/synapse/prompts/post-prompt-hook.md` and execute it.
This step is non-blocking: if the hook fails, record the failure in the final report Next section and continue.
```

**Verification checklist**:

- What to search for: `## Final report` in each prompt (insertion point is one step before).
- Search scope: each prompt file.
- Files to re-read: each modified prompt file after editing.

### Step 6 — Register post-prompt-hook.md in prompts manifests

Current state (2026-03-31):

- `prompts-manifest.json` already contains an entry for `post-prompt-hook.md` with `type: "hook"` and the expected keywords.

Remaining work:

1. Keep the manifest description aligned with the router semantics in `analyze.md` and `post-prompt-hook.md` (Skills, Plans, Rules).
2. Extend tests or trace-based checks so that future manifest edits do not accidentally drop or misclassify the hook.

**Verification checklist**:

- What to search for: existing entries format in `prompts-manifest.json`.
- Search scope: `.cortex/synapse/prompts/prompts-manifest.json`.
- Files to re-read: manifest after writing.

### Step 7 — Update rules-manifest.json format documentation

If Step 3 produces any new rules, verify `rules-manifest.json` schema accepts new entries without breakage. Add a "created_by: analyze-feedback-loop" metadata field convention to new rule files.

**Verification checklist**:

- What to search for: `rules-manifest.json` schema, existing rule `.mdc` frontmatter fields.
- Search scope: `.cortex/synapse/rules/rules-manifest.json`, any `.mdc` file.
- Files to re-read: `rules-manifest.json`.

### Step 8 — Validate end-to-end

1. Manually trace a simulated `fix.md` run: confirm the hook invocation step is present, confirm it would trigger `analyze.md`'s Steps 4–9, confirm findings would route to at least one artifact type.
2. Verify no circular trigger: `analyze.md` itself does NOT invoke the post-prompt hook — confirmed. The recursion guard lives in `post-prompt-hook.md` (Caller guard section) and skips execution when the calling prompt is `/cortex/analyze`. `analyze.md` has no post-prompt hook step itself, so there is no recursive path.

**Current state (2026-03-31)**: Circular reference verified absent. `analyze.md` → no hook call. `post-prompt-hook.md` → guard skips if caller is `analyze.md`. All other prompts → call the hook → hook runs Steps 4–9, then stops (no further hook calls).

**Verification checklist**:

- What to search for: any recursive hook reference in `analyze.md` or `post-prompt-hook.md`.
- Search scope: both files.
- Files to re-read: both after Step 4–5 modifications.

## Dependencies

- No code changes required — purely prompt/config file changes.
- Requires understanding of `.cortex/resources/skills/*.json` schema for Step 3a.
- Requires understanding of `.mdc` rule format for Step 3c.

## Success Criteria

1. `post-prompt-hook.md` exists with all required sections and no circular reference. **(Design+implementation: COMPLETE; usage alignment: PARTIAL.)**
2. Every prompt in `.cortex/synapse/prompts/` (except `analyze.md` and `post-prompt-hook.md`) and `.cortex/prompts/` has a hook invocation step. **(As of 2026-03-31: COMPLETE for audited prompts.)**
3. `analyze.md` Step 9 is replaced by Steps 9a/9b/9c with clear routing logic for Skills, Plans, and Rules. **(Router semantics implemented in `analyze.md` and reused by the hook.)**
4. `prompts-manifest.json` includes `post-prompt-hook.md` with an accurate description of the hook/router behavior. **(Present; keep description in sync with router semantics.)**
5. Manual trace confirms no circular invocation.
6. No existing prompt behavior is changed — hook is additive and non-blocking.

**Design alignment note (2026-03-31, updated)**: The full feedback loop is now correctly implemented and aligned:

- Core design (post-prompt hook, manifest, Skill/Plan/Rule router in `analyze.md`): COMPLETE
- Caller prompt updates (all 8 prompts): COMPLETE
- Recursion guard cleanup (removed misleading copy-paste from callers, guard correctly in hook): COMPLETE
- `commit.md` Step 15 stale `analyze()` calls removed: COMPLETE
- `analyze.md` final report template updated for 9a/9b/9c: COMPLETE
- Circular reference verification: COMPLETE

No blocking remaining work. Remaining items are hardening/testing (see Testing Strategy).

## Testing Strategy

Since these are prompt/markdown files (not runnable code), testing is trace-based:

1. **Structural tests** (95% coverage target for testable surface):
   - Verify all 8 prompts have the hook step (grep for `post-prompt-hook.md` reference).
   - Verify `analyze.md` has Steps 9a, 9b, 9c (grep for `Skill Router`, `Plan Router`, `Rule Router`).
   - Verify `post-prompt-hook.md` exists and does NOT reference itself or `analyze.md` recursively.
   - Verify `prompts-manifest.json` includes `post-prompt-hook` entry.

2. **Dry-run trace** (manual):
   - Simulate a `fix.md` session with mock findings → confirm artifact routing produces a plan (9b).
   - Simulate a `commit.md` session with tool usage patterns → confirm skill update (9a).
   - Simulate a session with a recurring rule violation → confirm rule creation (9c).

3. **Regression check**:
   - Confirm existing prompts' core logic is unchanged (diff each file, core steps untouched).
   - Confirm `analyze.md` Steps 1–8 are unchanged.
