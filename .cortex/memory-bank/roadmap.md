# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

- **Cleanup Function-Length Exclusions in Constants** - PENDING - Remove ad-hoc test-file exclusions from FUNCTION_LENGTH_EXCLUDED_PATHS and replace with explicit checker policy + tests. Plan: .cortex/plans/cleanup-function-length-exclusions-in-constants.md

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

#### Knowledge Base & Wiki (High Priority)

- Plan: [Memory Bank Lint (/cortex/lint-wiki)](../plans/memory-bank-lint.md) — Health-check tool for orphaned plans, missing plan files, stale activeContext entries, orphaned/unlinked wiki pages, and code-claim verification; exposed as `/cortex/lint-wiki` prompt and integrated into `/cortex/analyze`. PENDING.
- Plan: [File Review Reports into Memory Bank](../plans/file-review-reports-into-memory-bank.md) — File review and analyze artifacts as named pages in `.cortex/memory-bank/reviews/` and `analyses/`; cross-reference from `activeContext.md`; surface 5 most recent in `cortex://context`. PENDING.
- Plan: [Ingest Tool for Cortex Memory Bank (/cortex/ingest)](../plans/memory-bank-ingest-tool.md) — MCP `ingest` tool + `/cortex/ingest` prompt to integrate external sources into the memory bank; flags contradictions with existing content; updates cross-references; logs to the operations log. Depends on memory-bank-operations-log, file-review-reports. PENDING.

#### Token Efficiency (High Priority)

- Plan: [Compress Cortex Synapse Prompts and Memory Bank Files](../plans/compress-synapse-memory-files.md) — One-time compression of `.cortex/synapse/prompts/`, `cursor-agents/`, and `memory-bank/` files using a validate-before-overwrite pipeline; targets ≥35% token reduction per file. PENDING.
- Plan: [Agent-Internal Brevity Rule for Sub-Agent Communication](../plans/agent-internal-brevity-rule.md) — Add `## Agent-Internal Communication` brevity rule to `cortex://rules`; update sub-agent prompts and `pipeline_handoff` field docstrings; user-facing output excluded. PENDING.

### Features & Enhancements

#### Token Efficiency (Medium Priority)

- Plan: [compress_memory_bank MCP Tool and Token Budget Tracking](../plans/compress-memory-bank-mcp-tool.md) — MCP tool to compress attached-project memory files; token-budget metric in `/cortex/analyze` flags files >500 words as compression candidates. Depends on compress-synapse-memory-files. PENDING.

#### Claude Code Harness Improvements (High Priority)

- Plan: [Conditional Hook Execution DSL](../plans/hook-conditional-dsl.md) — Write `matcher` entries with wildcard glob sub-patterns (`FileEdit(/src/*)`, `Bash(git *)`) so hooks only fire on matching tool+pattern. PENDING.
- Plan: [Once Flag on Hooks](../plans/hook-once-flag.md) — Write `"once": true` hook entries that auto-remove after first execution; cleanup leftover once-hooks on session deregister. PENDING.
- Plan: [Prompt and Agent Hook Types](../plans/hook-prompt-agent-types.md) — Extend `HookEntry` to support `"type": "prompt"` and `"type": "agent"` entries for LLM-based post-edit verification. PENDING.
- Plan: [File State Cache and Rollback](../plans/file-state-cache-rollback.md) — Snapshot file contents before pipeline edits; restore on failure via `pipeline_handoff(operation="rollback")`; cleanup on session deregister. PENDING.
- Plan: [Per-Tool Structured Progress Types](../plans/structured-progress-types.md) — Replace plain string `ctx.report_progress()` calls with typed Pydantic models serialized as JSON for richer Cursor MCP UI rendering. PENDING.

#### Planning & Brainstorming (High Priority)

- Plan: [NEEDS CLARIFICATION Markers in Plans](../plans/needs-clarification-markers.md) — Embed `[NEEDS CLARIFICATION: <reason>]` markers inline during plan creation; gate implementation on resolution of blocking markers. PENDING.
- Plan: [Explore-Before-Commit Workflow (/cortex/explore)](../plans/explore-before-commit-workflow.md) — Lightweight brainstorming phase before `/cortex/plan`; produces a decision log without committing a plan; transitions to `/cortex/plan` when direction is chosen. PENDING.
- Plan: [Session Goal Anchoring with Drift Detection](../plans/session-goal-anchoring.md) — Write a session goal note at session start; detect and warn when agents touch out-of-scope files; end-of-session drift report. PENDING.
- Plan: [Context-Scoped Instruction Assembly](../plans/context-scoped-instruction-assembly.md) — Assemble scoped context packets for `implement-code`: relevant plan + upstream dependencies + task-type-filtered rules. PENDING.

#### Planning & Brainstorming (Medium Priority)

- Plan: [Delta Specs for Plans](../plans/delta-specs-for-plans.md) — Track plan revisions with explicit `ADDED/MODIFIED/REMOVED/RENAMED` delta entries; never silently overwrite history. PENDING.
- Plan: [Parallel Task Markers [P]](../plans/parallel-task-markers.md) — Mark independent implementation steps with `[P]`; orchestrator spawns concurrent `implement-code` agents in isolated worktrees. PENDING.
- Plan: [Schema-Defined Workflow Variants](../plans/schema-defined-workflow-variants.md) — Define custom Cortex pipeline variants in `.cortex/schemas/` (fast-path, compliance, data-science); active schema selected from session config. PENDING.
- Plan: [Artifact Graph for Plan Dependencies](../plans/artifact-graph-plan-dependencies.md) — Enforce `depends_on` field; compute real-time READY/BLOCKED/DONE graph; unblock plans automatically when dependencies complete. PENDING.

#### Wiki for Attached Projects (High Priority)

- Plan: [Project Wiki for Attached Projects (.cortex/wiki/)](../plans/project-wiki-attached-projects.md) — Full `.cortex/wiki/` knowledge base for attached projects: `init-wiki`, `query`, per-category pages, wiki index page, wired into review/analyze/commit pipelines; works when Cortex is attached to itself. Depends on memory-bank-ingest-tool, file-review-reports, memory-bank-lint. PENDING.
- Plan: [Auto-Ingest from Git Hooks (Wiki Auto-Update)](../plans/wiki-auto-ingest-git-hooks.md) — Post-commit hook auto-ingests changed doc files matching configurable glob patterns; idempotent (update vs create); registers via `/cortex/init-wiki`. Depends on project-wiki-attached-projects, hook-conditional-dsl. PENDING.

#### Planning & Brainstorming (Low Priority)

- Plan: [Fast-Forward vs. Step-by-Step Planning Modes](../plans/fast-forward-vs-step-by-step-modes.md) — Add `--ff` (one-shot) and `--step` (one section at a time, human-reviewed) modes to `/cortex/plan`. PENDING.
