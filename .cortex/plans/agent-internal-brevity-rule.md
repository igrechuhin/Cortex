---
title: Agent-Internal Brevity Rule for Sub-Agent Communication
component: cortex/core
work_type: improvement
status: PENDING
priority: medium
created: 2026-04-07
depends_on: []
---

## Goal

Add a brevity rule to `cortex://rules` that scopes compact prose to
**agent-internal** communication: sub-agent result summaries, inter-phase
`pipeline_handoff` payloads, and `think()` scratchpad output. User-facing
output from Cortex tools remains human-friendly and readable — this rule
applies only to text that other agents consume, not text the user reads.

**Target**: ≥40% token reduction in sub-agent result payloads with no loss
of decision or error information.

**Inspired by**: caveman's March 2026 arXiv finding that brevity constraints
retain or improve LLM accuracy; applied selectively to agent-to-agent channels
where readability is not required.

---

## Context

Cortex sub-agents (implement-code, fix-tests, fix-quality, review-*, etc.)
return result summaries that get loaded into the orchestrator's context. These
summaries are prose written for another LLM, not for a human reader. They
habitually include filler ("I have successfully completed", "As requested",
"It is worth noting that"), hedging, and verbose recaps of steps taken.

The `think()` tool scratchpad similarly tends to be verbose when not
constrained — reasoning steps that could be 3 words are 30.

The `pipeline_handoff` free-text fields (`context`, `summary`) carry the same
overhead.

None of these are shown directly to the user. Compressing them saves context
without degrading UX.

**Constraint**: User-facing text (MCP tool result strings shown in the Cursor
chat, `/cortex/analyze` reports, `cortex://context` resource content) must
remain compact but fully readable. The brevity rule must clearly demarcate
scope.

---

## Implementation Steps

### Step 1: Add brevity rule to the rules system

Locate the rules source file(s) that feed `cortex://rules`. Likely
`src/cortex/core/rules.py` or `.cortex/synapse/rules/`.

Read `cortex://rules` resource to confirm current rule set and format.

Add a new rule section `## Agent-Internal Communication`:

```text
## Agent-Internal Communication

When writing output consumed by another agent (not shown to the user):
- Drop: articles, filler openers ("I have", "As requested", "It is worth
  noting"), hedging ("may", "might", "could"), step recaps already visible
  in tool history.
- Keep verbatim: file paths, function names, error messages, test names,
  type names, CLI commands, MCP tool names.
- Keep readable: sentences must be grammatically complete. No abbreviation
  of domain terms. A human reading the output should understand it without
  effort — just without filler.
- Applies to: sub-agent result summaries, pipeline_handoff free-text fields
  (context, summary), think() scratchpad output.
- Does NOT apply to: MCP tool result strings shown in Cursor chat,
  /cortex/analyze reports, cortex://context resource content, or any other
  text the user reads directly.
```

**Verification checklist**:

- Search: `Agent-Internal Communication` in the rules source
- Read `cortex://rules` resource after change — confirm new section present
- Confirm existing user-facing rule sections are unchanged

### Step 2: Add brevity guidance to sub-agent prompts

For each agent in `.cortex/synapse/cursor-agents/` (implement-code.md,
shared-defaults.md), add a one-line callout at the top of the "Final report"
or "Result" section:

```text
<!-- AI: brevity rule applies — agent-internal output, not user-facing -->
```

And inline in the result format instructions:

```text
Write the result summary in compact technical prose: no filler openers,
no step recaps, no hedging. File paths, error messages, and type names
verbatim. See cortex://rules §"Agent-Internal Communication".
```

**Verification checklist**:

- Read each modified agent file after change
- Confirm `cortex://rules` reference is present in result instructions

### Step 3: Add brevity guidance to `pipeline_handoff` docstring

In `src/cortex/core/pipeline_handoff.py` (or wherever the tool is defined),
add to the `context` and `summary` field docstrings:

```python
context: str = Field(
    default="",
    description=(
        "Free-text context for the next phase. "
        "Write in compact technical prose (see cortex://rules "
        "§'Agent-Internal Communication'): no filler, no hedging, "
        "file paths and error messages verbatim."
    ),
)
```

Same for `summary`.

**Verification checklist**:

- Search: `Agent-Internal Communication` in `pipeline_handoff.py`
- Run `run_quality_gate()` — no type errors

### Step 4: Measure baseline vs. post-rule token usage

Add a benchmark script `scripts/benchmark_brevity.py`:

1. Load 5 recent `pipeline_handoff` payloads from test fixtures or
   `.cortex/memory-bank/` snapshots.
2. Count tokens (word-count proxy: `len(text.split())`).
3. Print per-payload word count and average.

Run before and after deploying the rule to a real session to confirm the
target ≥40% reduction. This is a manual validation step, not a CI test.

**Verification checklist**:

- `scripts/benchmark_brevity.py` exists and runs without error

---

## Dependencies

- No new packages
- Requires: existing rules system is file-based and editable
- Must not break: any existing rule references in tests

---

## Success Criteria

- `cortex://rules` resource includes `## Agent-Internal Communication` section.
- Sub-agent prompt files reference the new rule in their result format instructions.
- `pipeline_handoff` field docstrings reference the new rule.
- `run_quality_gate()` green after all changes.
- Manual benchmark shows ≥40% word-count reduction in at least 3 of 5 sampled
  `pipeline_handoff` payloads after one real session using the rule.

---

## Testing Strategy

Target: 95% coverage of any new code added.

| Scope | Tests |
|-------|-------|
| Rules source change | Grep-based: `test_rules_content.py` — assert `Agent-Internal Communication` section present in rendered rules; assert `User-facing` exclusion note present |
| `pipeline_handoff` docstrings | `test_pipeline_handoff_schema.py` — assert `context` and `summary` field descriptions contain brevity reference |
| Sub-agent prompt files | File-read assertions in `test_cursor_agents_content.py` — check brevity callout present in result sections |

No mocking needed — these are string/schema assertions on file content.
