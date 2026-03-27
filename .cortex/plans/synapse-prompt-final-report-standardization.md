---
title: Structured Final Reports for Cortex Synapse Prompts
component: prompts
work_type: improvement
status: PENDING
priority: medium
created: 2026-03-27
depends_on: []
---

## Goal

Make user-visible outcomes of Cortex Synapse prompts (and related Cursor commands) predictable and scannable by defining and enforcing a **single canonical final-report structure** per prompt family. Today, the same workflow (for example `/cortex/commit`) can end with success summaries that differ in headings, ordering, emoji usage, and depth; pipeline-style prompts also vary in how phases and tool results are surfaced. This plan standardizes those **agent-to-user narrative reports** (distinct from MCP JSON tool payloads; see archived Phase 75 for tool response shape).

## Context

- Synapse prompts live under `.cortex/synapse/prompts/` (`commit.md`, `implement-next-roadmap-step.md`, `fix.md`, `analyze.md`, `create-plan.md`, `review.md`, archives).
- Cursor command definitions may wrap or duplicate workflow steps; alignment is needed so users see the same report skeleton whether the agent follows a command file or a Synapse prompt.
- Existing related work: archived `phase-75-unify-response-format.md` (MCP tool JSON); `phase-90-agent-session-verbosity.md` (anti-pause); user preference for scan-friendly emoji status (✅/⚠️/❌) in AGENTS.md.

## Implementation Steps

### Step 1 — Inventory and classify

- Enumerate all user-facing prompt entrypoints (Synapse `*.md` + any repo `CLAUDE.md` / Cursor command markdown that defines end-of-run reporting).
- Tag each as **pipeline** (multi-phase with quality gates), **single-shot** (one main outcome), or **meta** (plan/memory-bank only).
- Deliverable: short table in plan or `REFACTORING_GUIDE.md` appendix listing prompt → category → required report sections.

**Verification checklist**: What to search for | `grep` / list `prompts/*.md` | Re-read `REFACTORING_GUIDE.md`

### Step 2 — Define canonical templates

- Specify one **base** final-report template (fixed section order, optional sub-bullets):
  - Status line (✅ success / ⚠️ partial / ❌ failed + one-line summary)
  - Scope / prompt name
  - What ran (high-level; for pipelines, phase list with pass/fail)
  - Key results (artifacts, commit hash, files touched — prompt-specific)
  - Memory bank / roadmap (if applicable: what was updated)
  - Blockers / follow-ups (or explicit "None")
- Define **delta** blocks for: commit (Phase A/B/Step 12), implement (handoff, subagent), fix (diagnosis note pointer), analyze (session optimization path), create-plan (plan path + roadmap registration), review (scores table).
- Document anti-patterns: process-only summaries ("I ran the pipeline"), inconsistent emoji, burying failures below success text.

**Verification checklist**: Template doc exists | Search `Final Report` / `## Final` in prompts | Re-read new shared snippet or guide section

### Step 3 — Apply to Synapse prompts

- Add a **mandatory "Final report (required format)"** section near the end of each primary prompt, embedding the base template + delta for that prompt.
- Prefer a **single included fragment** (if Synapse supports includes) or a **copy-paste canonical block** maintained in one source file referenced by all prompts to reduce drift.
- Ensure commit and other long pipelines repeat the same outer skeleton every time, with only inner rows changing.

**Verification checklist**: Each primary prompt references the same section order | Grep each file for `Final report` | Re-read `commit.md`, `implement-next-roadmap-step.md`, `fix.md`, `analyze.md`, `create-plan.md`, `review.md`

### Step 4 — Align Cursor commands

- Update Cursor command markdown under `.cursor/commands` or equivalent so command instructions point agents to the same final-report template as the matching Synapse prompt (no duplicate conflicting formats).

**Verification checklist**: Command files mention the shared format | List `.cursor/commands` | Re-read command files touching commit/implement/plan

### Step 5 — Regression tests

- Extend or add prompt alignment tests (similar to `test_commit_workflow_prompt_alignment.py`) to assert presence of required headings or stable markers for **final report** sections, without brittle full-text equality where possible (semantic / structural checks per archived reduce-prompt-alignment-fragility plan).

**Verification checklist**: Tests fail if a required section is removed | `pytest` on new/updated tests | Re-read test file(s)

## Dependencies

- None blocking; coordinate wording with Phase 75-style work only at the level of naming ("tool JSON" vs "user-facing report").

## Success Criteria

- Running the same prompt twice with similar outcomes produces **the same section layout and heading names** (content may differ).
- Pipeline prompts always show phase-level pass/fail in a predictable place.
- Documentation distinguishes MCP response shape (JSON) from user-facing final report (markdown).

## Testing Strategy (95% coverage target)

- **New code** (test helpers, parsers for required headings): target **≥95% line coverage** for new modules.
- **Prompt files**: validated by structural tests (required sections present), not by executing LLM.
- **Integration**: optional smoke — run one dry checklist that a sample agent completion matches the template (manual or scripted string check in tests).

## Risks

- Over-rigid templates may fight legitimate prompt-specific nuance — mitigate with "delta" blocks and explicit optional subsections.
- Duplication vs includes — prefer one authoritative snippet file to avoid Synapse drift.
