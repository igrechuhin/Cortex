# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

- Constitutional Layer for Projects — Continue remaining implementation after Step 1 foundation (`ConstitutionDoc`, canonical constitution path plumbing, and unit coverage) is complete. PENDING.

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

### Features & Enhancements

#### Planning & Brainstorming (High Priority)

- Plan: [Constitutional Layer for Projects](../plans/constitutional-layer.md) — Add a constitution document to memory bank; plan tool checks new plans against immutable architectural principles and flags violations. PENDING.
- Plan: [NEEDS CLARIFICATION Markers in Plans](../plans/needs-clarification-markers.md) — Embed `[NEEDS CLARIFICATION: <reason>]` markers inline during plan creation; gate implementation on resolution of blocking markers. PENDING.
- Plan: [Explore-Before-Commit Workflow (/cortex/explore)](../plans/explore-before-commit-workflow.md) — Lightweight brainstorming phase before `/cortex/plan`; produces a decision log without committing a plan; transitions to `/cortex/plan` when direction is chosen. PENDING.
- Plan: [Session Goal Anchoring with Drift Detection](../plans/session-goal-anchoring.md) — Write a session goal note at session start; detect and warn when agents touch out-of-scope files; end-of-session drift report. PENDING.
- Plan: [Context-Scoped Instruction Assembly](../plans/context-scoped-instruction-assembly.md) — Assemble scoped context packets for `implement-code`: relevant plan + upstream dependencies + task-type-filtered rules. PENDING.

#### Planning & Brainstorming (Medium Priority)

- Plan: [Delta Specs for Plans](../plans/delta-specs-for-plans.md) — Track plan revisions with explicit `ADDED/MODIFIED/REMOVED/RENAMED` delta entries; never silently overwrite history. PENDING.
- Plan: [Parallel Task Markers [P]](../plans/parallel-task-markers.md) — Mark independent implementation steps with `[P]`; orchestrator spawns concurrent `implement-code` agents in isolated worktrees. PENDING.
- Plan: [Schema-Defined Workflow Variants](../plans/schema-defined-workflow-variants.md) — Define custom Cortex pipeline variants in `.cortex/schemas/` (fast-path, compliance, data-science); active schema selected from session config. PENDING.
- Plan: [Artifact Graph for Plan Dependencies](../plans/artifact-graph-plan-dependencies.md) — Enforce `depends_on` field; compute real-time READY/BLOCKED/DONE graph; unblock plans automatically when dependencies complete. PENDING.

#### Planning & Brainstorming (Low Priority)

- Plan: [Fast-Forward vs. Step-by-Step Planning Modes](../plans/fast-forward-vs-step-by-step-modes.md) — Add `--ff` (one-shot) and `--step` (one section at a time, human-reviewed) modes to `/cortex/plan`. PENDING.
