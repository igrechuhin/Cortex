---
title: "AI Code Comments and BELIEF Annotations Support in Cortex Rules"
component: rules
work_type: feature
status: PENDING
priority: Low
created: 2026-04-02
depends_on: []
---

## Goal

Surface and enforce `// AI:` code comment conventions and BELIEF annotation patterns from `ai-code-comments.md` and `semantic-code-markup.md` in the ai-coding-kb as a Cortex rule set. Agents should be guided to write and preserve these annotations when editing code, and the quality gate should warn (not fail) when AI-annotated blocks are changed without updating their annotations.

## Context

The KB documents two lightweight patterns that persist agent reasoning inside code:

1. **`# AI:` comments** — inline explanations that survive context loss: `# AI: This branch handles the case where the submodule worktree is dirty; see stash logic above`
2. **BELIEF declarations** — structured blocks documenting AI's assumptions: `# BELIEF: session_config always has a trace_id after Step 1 completes`

These patterns help both human reviewers and future agents understand *why* code was written a certain way — especially important in Cortex where agents frequently modify the same files. Currently there is no rule guidance for these patterns and the quality gate does not check for their presence in critical paths.

## Implementation Steps

### Step 1 — Add `ai-code-comments` rule file

- Create `.cortex/rules/ai-code-comments.md`:
  - `## AI Comment Convention`: When to use `# AI:` prefix (unobvious logic, agent-specific decisions, unexpected deps, optimization warnings)
  - `## BELIEF Declaration Convention`: Format for documenting assumptions about runtime state
  - `## When NOT to use`: Don't annotate self-evident code; max 1 annotation per 10 lines of new agent-written code
  - `## Format`: `# AI: <why, not what>` on its own line before the relevant block
- Verification: File exists with all 4 sections; rules resource includes it.

### Step 2 — Register rule in `cortex://rules` resource

- Update rules resource handler to include `ai-code-comments.md` in its output
- Verification: `cortex://rules` response contains "AI Comment Convention" section.

### Step 3 — Quality gate: BELIEF staleness heuristic

- In the quality gate, after a successful diff, scan changed files for lines matching `# BELIEF:` or `# AI:`
- If a `# BELIEF:` line is in a changed block but the belief text was NOT updated in the diff: emit a `warning`-severity `CritiqueItem` (from the reflection model) — "BELIEF annotation may be stale"
- This is warning-only; it does NOT fail the gate
- Verification: Unit test with fixture diff containing stale BELIEF line confirms warning is emitted.

### Step 4 — `autofix` tool: suggest BELIEF annotation on new public functions

- When `autofix` processes a file that has a new public function with no `# AI:` context comment, suggest adding one
- Output as a `suggestion` in the autofix response (not auto-applied)
- Verification: Unit test with fixture new-function diff checks suggestion appears.

### Step 5 — Synapse prompts: reference AI comment convention

- Add one line to `do.md` and `plan.md` Step 7 (implementation): "For non-obvious logic, add `# AI:` comments explaining agent decisions"
- Verification: Both prompts reference `# AI:` comment guidance.

### Step 6 — Documentation

- Add `docs/guides/ai-code-comments.md` with examples of good/bad annotations from this codebase
- Include real examples from `session_config.py` and `pipeline_handoff.py`
- Verification: File exists with ≥2 real code examples.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `ai-code-comments.md` | `.cortex/rules/` | ai-code-comments.md |
| 2 | `AI Comment Convention` in rules response | rules resource handler | resources.py |
| 3 | `BELIEF` staleness check | quality gate / reflection module | reflection.py or gate handler |
| 4 | `suggestion` for new public functions | autofix handler | autofix.py |
| 5 | `# AI:` reference in do.md | `.cortex/synapse/prompts/do.md` | do.md |
| 5 | `# AI:` reference in plan.md | `.cortex/synapse/prompts/plan.md` | plan.md |
| 6 | `ai-code-comments.md` | `docs/guides/` | ai-code-comments.md |

## Dependencies

- `.cortex/rules/` — new rule file
- `src/cortex/resources.py` — rules resource output
- Quality gate / reflection module — BELIEF staleness check
- `src/cortex/tools/` — autofix suggestion
- `.cortex/synapse/prompts/do.md`, `plan.md` — cross-reference

## Success Criteria

- `# AI:` and BELIEF annotation conventions are documented in the rules resource
- Quality gate emits warning (not failure) when BELIEF annotations appear stale
- Autofix suggests annotations for new public functions
- Both do.md and plan.md reference the convention
- Zero gate regressions
- 95%+ coverage on new BELIEF staleness check code

## Testing Strategy

- Unit tests: `tests/unit/rules/test_ai_code_comments.py` — validate rule file is included in rules resource output
- Unit tests: `tests/unit/tools/evaluation/test_belief_staleness.py` — fixture diffs with stale BELIEF lines
- Unit tests: `tests/unit/tools/test_autofix_suggestions.py` — new function without annotation → suggestion emitted
- 95%+ coverage target on all new code paths
