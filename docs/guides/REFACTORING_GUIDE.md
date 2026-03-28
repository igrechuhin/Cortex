# Refactoring guide

Repo-level refactoring notes. Prompt-orchestration and Synapse-specific refactoring detail lives under `.cortex/synapse/prompts/` (see `REFACTORING_GUIDE.md` and `REFACTORING_SUMMARY.md` there).

## Appendix: Synapse prompt inventory

Step 1 inventory for [synapse-prompt-final-report-standardization](../../.cortex/plans/archive/Other/synapse-prompt-final-report-standardization.md). **Primary** rows are registered via `prompts-manifest.json` under `.cortex/synapse/prompts/` or `.cortex/prompts/`. **Archived** Synapse files are not manifest entrypoints but remain in the tree for reference. Step 2 canonical **final-report** section order and deltas: [synapse-final-report-templates.md](synapse-final-report-templates.md).

| Prompt / command path | Category | Notes |
| --- | --- | --- |
| `.cortex/synapse/prompts/commit.md` | pipeline | Primary MCP prompt `Commit`; Phase A / B / Step 12 |
| `.cortex/synapse/prompts/fix.md` | pipeline | Primary MCP prompt `Fix`; quality / tests / docs targets |
| `.cortex/synapse/prompts/implement-next-roadmap-step.md` | pipeline | Primary MCP prompt `Implement`; handoff, subagent, gates |
| `.cortex/synapse/prompts/review.md` | single-shot | Primary MCP prompt `Review`; one review report artifact |
| `.cortex/synapse/prompts/analyze.md` | single-shot | Primary MCP prompt `Analyze`; end-of-session analysis report |
| `.cortex/synapse/prompts/create-plan.md` | meta | Primary MCP prompt `Plan`; plans dir + roadmap registration |
| `.cortex/prompts/validate-roadmap-sync.md` | single-shot | Project MCP prompt; roadmap sync validation |
| `.cortex/prompts/populate-tiktoken-cache.md` | single-shot | Project MCP prompt; offline tiktoken cache |
| `.cortex/prompts/debug-external-integration.md` | single-shot | Project MCP prompt; external integration diagnostics |
| `.cortex/synapse/prompts/archive/analyze-session-optimization.md` | single-shot | Archived; superseded by `analyze.md`; not manifest-registered |
| `.cortex/synapse/prompts/archive/analyze-context-effectiveness.md` | single-shot | Archived; merged into `analyze.md`; not manifest-registered |
| `.cortex/synapse/prompts/archive/docs-sync.md` | single-shot | Archived; not manifest-registered |
| `.cortex/synapse/prompts/archive/fix-quality.md` | pipeline | Archived; fix workflow; superseded by `fix.md` |
| `.cortex/synapse/prompts/archive/fix-tests.md` | pipeline | Archived; fix workflow; superseded by `fix.md` |
| `.cortex/synapse/prompts/REFACTORING_GUIDE.md` | meta | Maintainer reference; not MCP-registered |
| `.cortex/synapse/prompts/REFACTORING_SUMMARY.md` | meta | Maintainer reference; not MCP-registered |
| `CLAUDE.md` | meta | Workspace agent rules; not an MCP prompt |
| `.cursor/agents/implement-code.md` | pipeline | Cursor subagent; implement pipeline step 2 (code + quality gate) |
| `.cursor/agents/shared-defaults.md` | meta | Shared agent conventions; reference for subagents |
| `.cursor/commands/` | — | **Absent in this repo** (2026-03-28); no parallel Cursor command markdown. `.cortex/synapse/cursor-agents/implement-code.md` syncs to `.cursor/agents/implement-code.md` and points at the shared final-report template `docs/guides/synapse-final-report-templates.md`. |

Categories follow the plan: **pipeline** (multi-phase with quality gates), **single-shot** (one main outcome), **meta** (planning / memory-bank / standards-only).
