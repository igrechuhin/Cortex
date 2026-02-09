# Compound Engineering Alignment: Cortex MCP

**Status**: PENDING  
**Created**: 2026-02-08  
**Goal**: Align Cortex with the compound-engineering principle—"tools that make each unit of engineering work easier than the last"—and adopt ideas from [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) to improve communication and output efficiency and reduce recurring friction.

## Context

### User Goal

Cortex MCP should make each unit of work easier than the last: communication and output should become more and more efficient over time. The user reports repeated struggle; the system should compound improvements instead of repeating the same friction.

### Compound-Engineering-Plugin Reference

EveryInc's [compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) (Claude Code) embodies:

- **Workflow**: Plan → Work → Review → Compound (repeat). Each cycle compounds: plans inform future plans, reviews catch issues, patterns get documented.
- **Philosophy**: 80% planning and review, 20% execution. Plan thoroughly, review to catch issues and capture learnings, codify knowledge so it's reusable, keep quality high so future changes are easy.
- **Concrete elements**: Workflow commands (`/workflows:plan`, `/workflows:work`, `/workflows:review`, `/workflows:compound`), many specialized agents and skills, explicit "compound" step to document learnings.

### Cortex Today

- **Strengths**: Memory bank (activeContext = completed, roadmap = future), plans directory, validation, refactoring, load_context, session optimization analysis, commit pipeline.
- **Gaps**: The compound loop is implicit; "compound" (document learnings, update memory bank, reduce future friction) is spread across commit prompt, session optimization, and ad-hoc updates. Recurring issues (roadmap/memory-bank write discipline, markdown lint, async tests, connection closed) suggest learnings are not consistently codified or applied at step start.

### Scope

This plan focuses on **documentation, prompts, and process** so that Cortex's existing tools and memory bank are used in a compound-engineering loop. It does not duplicate session-optimization or commit-pipeline implementation plans; it ties them together under a single narrative and adds explicit "compound" guidance and checklist where missing.

## Goal

1. **State the compound-engineering goal** in project brief and agent-facing docs (CLAUDE.md, AGENTS.md) so every session reinforces "each unit of work makes the next easier."
2. **Make the loop explicit**: Plan → Work → Review → Compound, mapped to Cortex artifacts (plans, implement/commit, review/quality, memory bank + session optimization + learnings).
3. **Codify learnings by default**: Ensure end-of-session and post-commit flows capture what worked and what to do differently next time (session optimization report, memory bank updates, optional learnings note).
4. **Reduce recurring struggle**: Align existing session-optimization and commit-pipeline improvements with the compound loop; add a short "compound checklist" (e.g. in commit or analyze prompt) so learnings from past sessions are applied (e.g. use `manage_file` for memory bank, run markdown lint early, respect task-type token budgets).

## Approach

1. **Docs and narrative**: Update project brief and CLAUDE.md/AGENTS.md with compound-engineering goal and Plan→Work→Review→Compound loop; link to roadmap and memory bank workflow.
2. **Prompt alignment**: Ensure implement, commit, and analyze-session (or unified analyze) prompts reference the loop and the "compound" step (update memory bank, run session optimization, capture learnings).
3. **Compound checklist**: Add a small, actionable checklist (in commit prompt or analyze prompt) that reflects past learnings: memory-bank writes via `manage_file` only, markdown lint scope, token budgets by task type, etc.
4. **No new tools**: Use existing MCP tools and Synapse prompts; no new Phase for this—only content and process changes.

## Implementation Steps

Execute in order. Each step has clear success criteria.

### Step 1: Document Compound-Engineering Goal and Loop in Project Brief and CLAUDE.md

**Tasks**:

1. In **projectBrief.md** (or equivalent project brief used by Cortex):
   - Add a short "Compound Engineering" or "Design Principle" subsection stating: Cortex aims to make each unit of engineering work easier than the last; communication and output should become more efficient over time.
   - Optionally reference the Plan→Work→Review→Compound loop and that completed work lives in activeContext, future work in roadmap, and learnings are captured via session optimization and memory bank updates.

2. In **CLAUDE.md** (and optionally AGENTS.md):
   - Add a subsection (e.g. "Compound Engineering") that states the same goal and maps the loop to Cortex:
     - **Plan**: Plans in `.cortex/plans`, roadmap entries; load context at step start.
     - **Work**: Implement prompt, commit pipeline, code and memory bank updates.
     - **Review**: Pre-commit checks, validation, code review; session optimization analysis at end of session.
     - **Compound**: Update memory bank (activeContext, progress, roadmap), run session optimization, capture what to do differently next time.

3. Ensure memory bank workflow (activeContext = completed, roadmap = future, update after significant changes) is explicitly tied to "compound" so agents treat it as part of the loop.

**Success Criteria**:

- Project brief and CLAUDE.md (and optionally AGENTS.md) contain the compound-engineering goal and loop.
- Wording is reviewable in PR; no hardcoded paths (use semantic names or Cortex tools per systemPatterns).

**Dependencies**: None.

---

### Step 2: Align Implement and Commit Prompts with Plan→Work→Review→Compound

**Tasks**:

1. In the **implement** prompt (or equivalent "execute next roadmap step" prompt):
   - At the start, add one sentence: this step is part of the compound-engineering loop (Plan→Work→Review→Compound); when done, update memory bank and run session optimization if end-of-session.
   - Ensure existing "load context at step start" and "memory bank writes via manage_file only" are present and prominent (per session-optimization-implement-prompt-memory-bank and related plans).

2. In the **commit** prompt:
   - Add a short "Compound" reminder: after commit, update activeContext/progress if not already done; consider running session optimization to capture learnings.
   - Keep existing steps (format, test, memory bank, roadmap, etc.) unchanged; only add the compound reminder and ensure memory-bank write rules (manage_file only, full-content for roadmap) are explicit.

3. Optionally add one line to **analyze-session-optimization** (or unified analyze) prompt: "This analysis is the 'Compound' step of the loop; use it to make the next session easier."

**Success Criteria**:

- Implement and commit prompts reference the loop and the compound step.
- No duplication of existing session-optimization or commit-pipeline implementation details; only narrative and reminders.

**Dependencies**: None. May reference session-optimization-implement-prompt-memory-bank and session-optimization-commit-pipeline-improvements for consistency.

---

### Step 3: Add a Short "Compound Checklist" to Commit or Analyze Prompt

**Tasks**:

1. Define a **compound checklist** (5–10 items) that encodes past learnings so agents apply them every session. Examples (to be finalized in implementation):
   - Memory bank writes: use `manage_file()` only; never StrReplace/Write/ApplyPatch on roadmap or activeContext.
   - Roadmap single-line edits: read full content with `manage_file(read)`, compute updated content, then `manage_file(write, content=...)`.
   - Markdown lint: runs on all markdown (including `.cortex/history/`, `.cortex/reviews/`); run early when editing markdown.
   - Token budgets: use task-type-based budgets in load_context when implementing (per session-optimization-implement-load-context-and-rules-fallback).
   - Connection closed: if fix_markdown_lint or long tool returns -32000, retry once; server uses progress and heartbeat; see troubleshooting doc.

2. Insert the checklist in the **commit** prompt (e.g. before Step 1 or in a "Pre-flight" section) or in the **analyze-session-optimization** prompt (e.g. "Before analyzing, verify these compound practices were followed"). Prefer one canonical place (commit or analyze) to avoid duplication.

3. Keep the checklist short and link to detailed docs (e.g. CLAUDE.md, troubleshooting, session-optimization plans) for full rules.

**Success Criteria**:

- A short compound checklist exists in one prompt (commit or analyze).
- Checklist items are actionable and derived from past session-optimization and commit-pipeline findings.
- Docs or prompts reference the checklist so agents see it at the right time.

**Dependencies**: Step 1 (so the checklist is framed as part of the compound loop). Can be done in parallel with Step 2.

---

### Step 4: Document "Compound" in Memory Bank and Session Optimization Docs

**Tasks**:

1. In **memory bank** documentation (e.g. CLAUDE.md Memory Bank section, or docs in repo):
   - State that updating activeContext (completed work), progress, and roadmap (future work) after significant changes is the **compound** step: it makes the next session easier by keeping context accurate and avoiding duplicate or conflicting entries.

2. In **session optimization** (or unified analyze) documentation:
   - State that running session optimization at end of session is the **Compound** step of the loop: it captures mistake patterns, root causes, and recommendations so the next session can avoid repeating them.

3. If a "learnings" or "what to do differently" artifact exists (e.g. in reviews or progress), document it as part of compound; if not, note that session optimization report and memory bank updates are the primary compound artifacts.

**Success Criteria**:

- Memory bank and session optimization docs explicitly call out their role in the compound loop.
- No new tools or new files required unless the team decides to add a dedicated learnings file later.

**Dependencies**: Step 1.

---

### Step 5: Cross-Check with Existing Session-Optimization and Commit-Pipeline Plans

**Tasks**:

1. List existing plans that reduce recurring friction: session-optimization-implement-prompt-memory-bank, session-optimization-commit-pipeline-improvements, session-optimization-implement-load-context-and-rules-fallback, session-optimization-roadmap-full-content-enforcement, and related.

2. For each, ensure the plan title or description (or a one-line note in the plan) references "compound engineering" or "make next session easier" so that when those plans are implemented, they are clearly part of this alignment.

3. Optionally add a "Related plans" section in this plan (compound-engineering-alignment-cortex.md) listing those plans so implementers and agents see the full set.

**Success Criteria**:

- No duplicate work; existing plans remain the source of implementation details.
- This plan and the listed plans are mutually consistent and referenced where useful.

**Dependencies**: None.

## Dependencies

- **Session optimization and commit pipeline plans**: This plan does not implement their steps; it adds narrative, checklist, and doc alignment. Implementation of async test validation, markdown lint scope, memory-bank write quality, etc., remains in those plans.
- **Unified analyze prompt**: If a unified "analyze" prompt is introduced (per merge-analyze-prompts blocker or similar), the compound checklist and "Compound step" wording should be merged into that prompt.

## Success Criteria (Overall)

- Compound-engineering goal and Plan→Work→Review→Compound loop are stated in project brief, CLAUDE.md, and optionally AGENTS.md.
- Implement and commit prompts (and analyze/session-optimization) reference the loop and the compound step.
- A short compound checklist is present in commit or analyze prompt and reflects past learnings.
- Memory bank and session optimization docs describe their role in the compound loop.
- Existing session-optimization and commit-pipeline plans are cross-referenced; no conflicting guidance.

## Testing Strategy

- **Documentation and prompts**: No new code paths; changes are to Markdown and prompt content.
- **Verification**: (1) Manual review of project brief, CLAUDE.md, AGENTS.md, and Synapse prompts for consistency and clarity. (2) Integration test or script that loads implement and commit prompt content and asserts presence of keywords (e.g. "compound", "manage_file", "memory bank") if such tests already exist; otherwise add a minimal sanity check. (3) No new unit tests for MCP tools unless a new config or tool is added later.
- **Regression**: Ensure existing prompt and doc tests (if any) still pass; ensure no hardcoded paths are introduced (per systemPatterns).

## Risks & Mitigation

- **Scope creep**: Resist adding new tools or new phases. Limit to docs, prompts, and one short checklist.
- **Checklist bloat**: Keep the compound checklist to 5–10 items; link to detailed docs for the rest.
- **Duplicate content**: Reuse existing session-optimization and commit-pipeline wording where possible; this plan adds framing, not replacement.

## Timeline

- Steps 1–4: 1–2 days (docs and prompt edits). Step 5: 0.5 day (cross-check and references). Total estimate: 2–3 days.

## Notes

- EveryInc compound-engineering-plugin is Claude Code (agents, commands, skills); Cortex is MCP (tools, prompts, memory bank). This plan adapts the **philosophy and workflow structure**, not the plugin format.
- "Struggling over and over" is addressed by making the compound loop and past learnings (checklist) explicit so that each session applies them; ongoing implementation of session-optimization and commit-pipeline plans addresses root causes (e.g. async test checks, markdown lint scope, memory-bank write quality).
