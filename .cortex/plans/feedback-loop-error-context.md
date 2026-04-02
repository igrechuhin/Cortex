---
title: "Feedback Loop: Pipe Quality Gate Errors Back into Agent Context"
component: tools/session
work_type: feature
status: PENDING
priority: high
created: 2026-04-02
depends_on: []
---

## Goal

Implement an automatic feedback loop that pipes quality gate and test failure context back into the agent's next-step context via `pipeline_handoff`, inspired by `feedback-loops.md` from the ai-coding-kb. When a gate fails, the structured error summary (file, line, error type, fix suggestion) is written to handoff state so the `/cortex/do` prompt reads it at the top of the next iteration — reducing the agent's need to re-read all error output from scratch.

## Context

The KB identifies iterative development with small steps as a core principle: "Verify-then-trust with automatic guardrails." Currently when `run_quality_gate` fails, the agent receives a raw text block of errors and must manually parse which files to fix. If the agent's context is already large, important error details get lost. The fix: after a gate failure, write a structured `GateFeedback` object to `pipeline_handoff` under a reserved key (`_gate_feedback`). The `/cortex/do` prompt then reads this at Step 1 and highlights the top-N errors before the agent starts making edits. This closes the feedback loop automatically.

## Implementation Steps

### Step 1 — Define GateFeedback model

- Create `src/cortex/tools/session/gate_feedback.py`:
  - `GateError(BaseModel)`: `file: str`, `line: int | None`, `check: str`, `message: str`, `fix_suggestion: str | None`
  - `GateFeedback(BaseModel)`: `gate: Literal["quality","docs"]`, `run_id: str`, `timestamp: str`, `errors: list[GateError]`, `top_files: list[str]` (deduplicated file paths), `summary: str`
- Verification: pyright passes; model imports cleanly.

### Step 2 — Quality gate: write GateFeedback on failure

- After gate checks complete and ≥1 check failed: parse error output into `list[GateError]`
- Write `GateFeedback` to `pipeline_handoff(operation="write", key="_gate_feedback", value=feedback.model_dump_json())`
- On gate success: clear `_gate_feedback` from handoff state (`pipeline_handoff(operation="clear", key="_gate_feedback")`)
- Verification: Integration test calls gate on failing project, reads handoff, confirms `_gate_feedback` key present and parseable.

### Step 3 — `run_docs_gate`: same feedback loop

- Apply same write-on-failure / clear-on-success pattern to `run_docs_gate`
- Use `gate="docs"` in the `GateFeedback` model
- Verification: Integration test for docs gate confirms feedback written on failure.

### Step 4 — Update `/cortex/do` prompt: read gate feedback at Step 1

- In `do.md`, after `session()` call (Step 1): add instruction to read `_gate_feedback` from `pipeline_handoff`
- If feedback present: display `GateFeedback.summary` and `top_files` as the first context block before reading the plan
- Format: `> ⚠️ Gate failed on previous run: <summary>. Top files: <top_files>`
- Verification: `do.md` contains `_gate_feedback` read instruction.

### Step 5 — `/cortex/do` prompt: iteration limit guard

- Add a note: if gate has failed ≥5 times on the same `run_id` prefix, pause and surface to user (matches KB rule: <5 iterations continue, 5+ restart fresh)
- Store iteration count in `pipeline_handoff` under `_gate_iterations`
- Verification: `do.md` contains iteration guard reference.

### Step 6 — `session()` tool: surface active gate feedback

- If `_gate_feedback` key exists in handoff: include a `gate_feedback_summary` field in `session()` response
- Agents see the summary at session start without an extra tool call
- Verification: Unit test mocks handoff state with `_gate_feedback`, confirms `session()` includes it.

### Step 7 — Documentation

- Add `docs/guides/feedback-loops.md` explaining the `_gate_feedback` key, GateFeedback schema, and iteration guard
- Verification: File exists with GateFeedback JSON example.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `class GateFeedback` | `src/cortex/tools/session/gate_feedback.py` | gate_feedback.py |
| 2 | `_gate_feedback` write call | quality gate handler | gate handler file |
| 2 | clear on success | quality gate handler | gate handler file |
| 3 | `gate="docs"` | docs gate handler | docs gate file |
| 4 | `_gate_feedback` read in do.md | `.cortex/synapse/prompts/do.md` | do.md |
| 5 | `_gate_iterations` in do.md | `.cortex/synapse/prompts/do.md` | do.md |
| 6 | `gate_feedback_summary` in session | `src/cortex/tools/session/` | session handler |
| 7 | `feedback-loops.md` | `docs/guides/` | feedback-loops.md |

## Dependencies

- `src/cortex/tools/session/pipeline_handoff.py` — write/read/clear handoff state
- Quality gate handler — write feedback on failure
- `run_docs_gate` handler — same pattern
- `.cortex/synapse/prompts/do.md` — read feedback at Step 1
- `session()` tool — surface summary

## Success Criteria

- `GateFeedback` is written to handoff on every gate failure
- Handoff is cleared on gate success
- `/cortex/do` reads and displays feedback summary before plan steps
- Iteration guard prevents infinite loops (≥5 failures → pause)
- `session()` includes feedback summary when present
- 95%+ coverage on new `gate_feedback.py` module
- Zero regressions in gate/handoff tests

## Testing Strategy

- Unit tests (AAA): `tests/unit/tools/session/test_gate_feedback.py` — model validation, serialization
- Integration tests: `tests/integration/test_gate_feedback_loop.py` — failing gate writes feedback; passing gate clears it; session reads it
- Parametric: multiple error types (type error, lint, test failure) all produce valid GateError entries
- 95%+ coverage target on new module
