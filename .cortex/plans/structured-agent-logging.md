---
title: "Structured Agent-Oriented Logging for Cortex MCP Tools"
component: tools/logging
work_type: feature
status: PENDING
priority: medium
created: 2026-04-02
depends_on: []
---

## Goal

Add structured, agent-readable logging to Cortex MCP tool calls so that agents can trace requirement → code → runtime behavior. Inspired by `logging-for-agents.md` from the ai-coding-kb: logs should carry semantic fields (event, component, traceId, requirementId) and annotations that describe *what* and *why*, enabling agents to link failing test output back to the plan entry and source location.

## Context

Currently Cortex MCP tools emit plain text or minimal structured output. When a quality gate fails or an autofix errors, the agent only gets the raw error text. The KB insight: agents navigate codebases and diagnose problems far more effectively when logs carry semantic coordinates — block IDs, requirement IDs, component names — rather than bare stack traces. This is especially relevant for `run_quality_gate`, `autofix`, and `pipeline_handoff` where the agent needs to correlate gate failures with the active plan step.

## Implementation Steps

### Step 1 — Define LogEvent Pydantic model

- Create `src/cortex/tools/logging/models.py` with `LogEvent(BaseModel)`:
  - `event: str` — short event ID (e.g. `quality_gate.failed`, `autofix.applied`)
  - `level: Literal["debug","info","warn","error"]`
  - `component: str` — tool name / module path
  - `trace_id: str | None` — session or pipeline trace
  - `requirement_id: str | None` — active plan step reference
  - `commit_hash: str | None` — git HEAD at time of log
  - `message: str`
  - `details: dict[str, str | int | bool] | None`
- Verification: `from cortex.tools.logging.models import LogEvent` works; pyright passes.

### Step 2 — Logging helper

- Create `src/cortex/tools/logging/logger.py`: `emit(event: LogEvent) -> None` writes JSON line to stderr (no file I/O) — MCP clients see structured output.
- Add `format_for_agent(events: list[LogEvent]) -> str` — returns markdown table for inclusion in tool response text.
- Verification: Unit test `tests/unit/tools/logging/test_logger.py` checks JSON output shape.

### Step 3 — Instrument `run_quality_gate` tool

- Import `emit` from logging helper.
- On gate failure: emit `quality_gate.failed` event with `component="run_quality_gate"`, `requirement_id` from session config active step, `details` = `{check: name, error: short_msg}`.
- On gate success: emit `quality_gate.passed`.
- Append `format_for_agent` table to tool response text when events present.
- Verification: Integration test validates structured fields appear in response.

### Step 4 — Instrument `autofix` tool

- On each fix applied: emit `autofix.applied` with `component`, `details={"file": path, "fix_type": name}`.
- On fix error: emit `autofix.error` with error message.
- Verification: Integration test confirms events are emitted.

### Step 5 — Instrument `pipeline_handoff` write/read

- Emit `pipeline_handoff.write` / `pipeline_handoff.read` with `trace_id` = handoff key.
- Verification: Unit test checks emit calls in both branches.

### Step 6 — Session trace_id propagation

- Read `trace_id` from session config (or generate UUID at session start, persist to session config).
- All emitted events carry the same `trace_id` for the session lifetime.
- Verification: `session()` response includes `trace_id` field.

### Step 7 — Documentation

- Add `docs/guides/agent-logging.md` explaining the log schema and how agents should interpret it.
- Verification: File exists with schema table and example log output.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `class LogEvent` | `src/cortex/tools/logging/` | models.py |
| 2 | `def emit` | `src/cortex/tools/logging/logger.py` | logger.py |
| 3 | `quality_gate.failed` in emit call | `src/cortex/tools/execution/` | relevant gate file |
| 4 | `autofix.applied` in emit call | `src/cortex/tools/` | autofix handler |
| 5 | `pipeline_handoff.write` | `src/cortex/tools/session/` | pipeline_handoff.py |
| 6 | `trace_id` in session config | `src/cortex/core/session_config.py` | session_config.py |
| 7 | `agent-logging.md` exists | `docs/guides/` | agent-logging.md |

## Dependencies

- `src/cortex/core/session_config.py` — read active plan step + trace_id
- `src/cortex/tools/session/pipeline_handoff.py` — handoff instrumentation

## Success Criteria

- All 4 instrumented tools emit structured LogEvent JSON on stderr
- `format_for_agent` output is included in tool response text when events exist
- `trace_id` propagates through an entire pipeline session
- 95%+ coverage on new `tools/logging/` module
- No regressions in existing tests

## Testing Strategy

- Unit tests (AAA pattern): `tests/unit/tools/logging/` — test LogEvent validation, emit output shape, format_for_agent markdown table
- Integration tests: `tests/integration/test_agent_logging.py` — call quality gate on a failing project, verify structured event appears in response
- 95%+ coverage target on new module
- Existing gate/autofix tests must pass unchanged (logging is additive, non-breaking)
