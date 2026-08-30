---
title: "fix.md: Surface cortex://rules status:disabled as ⚠️ warning instead of silent skip"
component: synapse/prompts
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-29
depends_on: []
---

## Goal

When `cortex://rules` responds with `status: "disabled"` (rules indexing
turned off in `.cortex/config/optimization.json`), the `/cortex/fix` prompt
currently treats this identically to a connection failure and silently proceeds
without rules. The agent has degraded context but the user receives no signal.

This plan makes the fix prompt distinguish `status: "disabled"` from a
connection failure and surface it as a ⚠️ warning in the final report's
"Next" section, pointing the user to the configuration knob.

## Context

Current `fix.md` Pre-Action Checklist step 1:

> "Read the `cortex://rules` resource (zero-arg, reads task from session
> config). **If resource access fails, proceed without rules** — fix based on
> error output."

The phrase "resource access fails" is ambiguous — it covers both:

- **Connection failure**: server unreachable, MCP disconnect.
  → Silent skip is correct: agent cannot do anything about it.
- **`status: "disabled"`**: server is reachable, rules indexing is turned off
  in config.
  → User CAN fix this; silent skip hides actionable information.

The TradeWing session (2026-03-29) received `cortex://rules returned status:
"disabled"` and buried it in a footnote: *"Optional: `cortex://rules` returned
`status: 'disabled'` — enable rules indexing in `.cortex/config/optimization.json`
if you want that resource populated."* It was mentioned at all only because the
agent's self-audit surfaced it; the prompt gave no instruction to do so.

## Implementation Steps

### Step 1: Differentiate disabled vs failure in "Pre-Action Checklist"

In `.cortex/synapse/prompts/fix.md`, locate **Pre-Action Checklist** step 1.
Replace the current bullet:

```text
If resource access fails, proceed without rules — fix based on error output.
```

With:

```text
If `cortex://rules` returns `status: "disabled"`: proceed without rules AND
record a ⚠️ warning for the final report: "Rules indexing is disabled —
enable it in `.cortex/config/optimization.json` → `rules_indexing.enabled:
true` to get rules-aware fixes." Do NOT surface this inline; add it to the
"Next" section of the final report only.

If resource access fails for any other reason (connection error, timeout):
proceed without rules, no warning needed.
```

#### Verification Checklist — Step 1

| What to check | Where | Files |
|---------------|-------|-------|
| `status: "disabled"` path explicitly distinguished | Read step 1 after edit | `.cortex/synapse/prompts/fix.md` |
| Config key `rules_indexing.enabled` is accurate | Read `.cortex/config/optimization.json` | `.cortex/config/optimization.json` |
| Original "connection failure → silent skip" still present | Grep `connection error` or similar | `.cortex/synapse/prompts/fix.md` |

### Step 2: Add disabled-rules warning to Final Report format

In the **Final report** section of `fix.md`, the `## Next` block currently
says `<remaining failures OR None>`. Add a note that a rules-disabled warning
belongs here:

> If a ⚠️ rules-disabled warning was recorded in step 1 of Pre-Action
> Checklist, include it as the first item under `## Next`.

Add this as a rule bullet under the existing `**Rules**:` section of the
Final report format block.

#### Verification Checklist — Step 2

| What to check | Where | Files |
|---------------|-------|-------|
| Rules-disabled note present in Final report section | Read "Final report" in `fix.md` | `.cortex/synapse/prompts/fix.md` |
| Formatting is consistent with existing rules bullets | Visual diff | — |

### Step 3: Verify the actual config key

Before finalizing the plan text, confirm the exact key name in
`.cortex/config/optimization.json` that controls rules indexing.

Read `.cortex/config/optimization.json` and locate the rules/indexing control.
Update step 1 text above with the accurate key path if it differs.

#### Verification Checklist — Step 3

| What to check | Where | Files |
|---------------|-------|-------|
| Key name in plan matches actual config file | Read `.cortex/config/optimization.json` | `.cortex/config/optimization.json` |

### Step 4: Quality gate

Run `fix_quality_issues()` then `run_docs_gate()`. Markdown-only change;
full test run not required.

#### Verification Checklist — Step 4

| What to check | Where | Files |
|---------------|-------|-------|
| `docs_phase_passed: true` | `run_docs_gate()` result | — |
| Zero new markdown lint errors | `fix_quality_issues()` output | — |

## Dependencies

- `.cortex/synapse/prompts/fix.md` (edit target)
- `.cortex/config/optimization.json` (read for accurate key name)
- `run_docs_gate()` and `fix_quality_issues()` MCP tools

## Success Criteria

1. `fix.md` Pre-Action Checklist step 1 distinguishes `status: "disabled"`
   from connection failures.
2. When rules are disabled, the prompt directs the agent to record a ⚠️
   warning for the "Next" section of the final report (not inline).
3. The config key reference in the warning text is accurate.
4. "Connection failure → silent skip" behavior is preserved.
5. `run_docs_gate()` passes with zero markdown errors.
6. No source file changes.

## Testing Strategy

Documentation-only change. Testing:

- `fix_quality_issues()` + `run_docs_gate()` for lint-clean output.
- Manual review: simulate mentally both the "disabled" and "connection failure"
  paths and confirm each follows the correct instruction branch.
- Grep `fix.md` for `status: "disabled"` to confirm it is present.

Coverage target: N/A. Docs gate must pass (100%).
