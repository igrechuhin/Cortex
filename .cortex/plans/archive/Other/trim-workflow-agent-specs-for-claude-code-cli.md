---
title: "Trim Workflow Agent Specs for Claude Code CLI"
component: synapse
work_type: optimize
status: PENDING
priority: High
created: "2026-06-25"
depends_on: []
status: PENDING
---

## Goal

Reduce per-subagent startup token cost by rewriting the 10 cursor-agent `.md` files to be concise Claude Code CLI specs, eliminating Cursor-specific verbosity and prose that is redundant when agents have `Bash`/`Read`/`Edit` tools directly.

## Context

Each workflow subagent starts with 17K+ tokens loaded before doing any work. The `.cortex/synapse/cursor-agents/*.md` files were authored for Cursor's MCP-only context where agents can't run shell commands and need detailed prose instructions on how to call each MCP tool. Now that all agents have `Bash, Read, Edit, Grep` in their `tools:` field, most of that prose is dead weight — the agent can just run the command instead of reading instructions about how to invoke it via MCP. The `inject_tools_into_frontmatter` transform also rewrites bare tool names to `mcp__cortex__` prefixed names, adding token cost. Each agent file currently ranges from 80–200 lines; target is 20–40 lines.

## Scope

**in_scope**

- Rewrite all 10 cursor-agent files in `.cortex/synapse/cursor-agents/`: `commit-preflight`, `commit-phase-a`, `commit-phase-b`, `commit-phase-c`, `commit-final-gate`, `fix-quality`, `fix-coverage`, `fix-tests`, `fix-docs`, `implement-code`
- Keep all required structured output fields (the schema the workflow JS reads via `TESTS_SCHEMA`, `PHASE_A_SCHEMA`, etc.)
- Keep the `tools:` frontmatter field and `name`/`description`
- Preserve step order and decision branches (Branch A/B/C) as short directives, not prose
- Run quality gate to confirm no test regressions

**out_of_scope**

- Changing workflow JS scripts (`fix.wf.js`, `commit.wf.js`, `do.wf.js`)
- Changing `inject_tools_into_frontmatter` transform logic
- Cursor-specific formatting or agent registry changes
- Analyze/review pipeline agents (not used by workflows)

## Approach

For each agent file, replace multi-paragraph MCP-tool-usage instructions with a 3–5 bullet numbered steps that reference the tool by name and expected output field. Remove all "why to call" and "what the tool does" prose — just "call X, extract Y, if Z do W". Remove resume-check boilerplate where the workflow JS already handles retry logic externally. Keep the structured output schema description (the JS reads these fields).

The `inject_tools_into_frontmatter` transform preserves existing `tools:` fields, so no transform changes needed.

## Implementation Steps

1. Measure current token cost: for each of the 10 files, count lines and approximate tokens (characters / 4). Record baseline.
2. Rewrite `commit-preflight.md`: keep preflight checklist as 5 numbered steps (MCP health → git status → snapshot → synapse pre-stage → return schema). Target ≤30 lines.
3. Rewrite `commit-phase-a.md`: autofix → quality gate → parity scripts → return schema. Target ≤25 lines.
4. Rewrite `commit-phase-b.md`: activeContext → progress → roadmap → archive plans → docs gate → return schema. Target ≤25 lines.
5. Rewrite `commit-phase-c.md`: validate timestamps → synapse commit/push → return schema. Target ≤20 lines.
6. Rewrite `commit-final-gate.md`: classify scope → run gate → return schema. Target ≤20 lines.
7. Rewrite `fix-quality.md`: scope-route (markdown_only vs source) → autofix → gate → parity → return schema. Target ≤25 lines.
8. Rewrite `fix-coverage.md`: preflight gate → extract gaps → write tests → verify → return schema. Target ≤25 lines.
9. Rewrite `fix-tests.md`: gate → branch A/B/C → fix → verify → return schema. Target ≤30 lines.
10. Rewrite `fix-docs.md`: roadmap cross-check → activeContext align → docs gate → return schema. Target ≤20 lines.
11. Rewrite `implement-code.md`: read plan → implement step → quality gate → return schema. Target ≤30 lines.
12. Run `sync_cursor_agents()` to propagate changes to `.claude/agents/`.
13. Run `run_quality_gate()` to confirm no test regressions.
14. Measure post-rewrite token cost per file; confirm ≥50% reduction in total agent spec tokens.

## Verification Checklist

- [ ] Each rewritten file has all required structured output fields referenced (grep for schema field names used in workflow JS)
- [ ] Each file has `tools: mcp__cortex__*, Bash, Read, Edit, Grep` in frontmatter
- [ ] `.claude/agents/` files match after sync (no stale copies)
- [ ] `run_quality_gate()` returns `preflight_passed: true`
- [ ] Token reduction ≥50% vs baseline for total agent spec token count

## Dependencies

None — cursor-agents are standalone files, no code imports them.

## Success Criteria

- All 10 agent files rewritten and ≤40 lines each
- Total agent spec tokens reduced by ≥50% from baseline
- `run_quality_gate()` passes with no new failures
- `.claude/agents/` synced and consistent with source

## Testing Strategy

- Existing workflow tests in `tests/workflows/` verify structural contracts of the JS scripts (not agent content), so they continue to pass unchanged
- Manual spot-check: invoke `/cortex/fix` after rewrite and confirm subagent startup token count drops in `/workflows` panel
- No new test files needed — agent content is not unit-tested

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Rewrite removes a required structured output field → JS schema validation fails at runtime | Cross-check each rewrite against the schema constants in the `.wf.js` files before committing |
| Agent too short → misses a required branch (e.g. Branch B coverage redirect) → silent misbehavior | Keep all decision branch labels even as one-liners; run a fix workflow after rewrite to exercise the paths |
| `sync_cursor_agents()` transform mangles tool names in shortened files | Verify `.claude/agents/` output after sync; run import check |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
