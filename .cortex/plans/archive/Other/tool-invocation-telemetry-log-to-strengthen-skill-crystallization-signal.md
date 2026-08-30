---
title: "Tool-Invocation Telemetry Log to Strengthen Skill-Crystallization Signal"
component: "self-improvement"
work_type: feature
status: PENDING
priority: Medium
created: 2026-07-23
depends_on: []
---

## Goal

Add a lightweight, structured per-session log of MCP tool invocations (tool name, argument shape, outcome, timestamp) that `analyze-session`/`analyze-tools` can read as a first-class evidence source when proposing new Synapse skills/rules via `write_artifact`, instead of relying only on `git log`/`git diff` and experience-store graph queries.

## Context

An external proposal ("Dual-Model Skill Crystallization Pipeline") suggested a telemetry-driven audit pipeline that mines repeated multi-turn tool sequences and compiles them into new deterministic macro tools. Investigation (2026-07-23) found Cortex already has most of this: `write_artifact` (`src/cortex/tools/artifacts/write_artifact.py`) persists skill JSON to `src/cortex/resources/skills/*.json`, and `.cortex/synapse/prompts/post-prompt-hook.md` drives `.claude/agents/analyze-session.md` / `analyze-tools.md`, which read memory-bank files, `git log`/`git diff`, and `pipeline_handoff` graph queries (`preference_pairs`, `repeated_failures`) to recommend rules/skills. The gap: there is no standing tool-invocation telemetry log — pattern detection depends on diff/graph review, which misses repeated tool-call sequences that don't leave a code diff (e.g. an agent always running the same 3 read-only lookups before answering a certain question type).

**Why**: Repeated read-only tool sequences (the exact case in the original proposal's example — "git status → git diff → grep") are invisible to git-diff-based analysis and only partially visible to the experience-store graph, so `analyze-tools`'s consolidation candidates are currently under-informed for this specific pattern class.

**How to apply**: This plan is an extension of the existing skill-crystallization pipeline, not a replacement. It should not introduce a second, competing recommendation path.

## Scope

**in_scope**:

- A structured, append-only per-session telemetry log capturing MCP tool name, a redacted/shape-only argument summary (no secrets, no full payload text), outcome (success/error), and timestamp for each tool call — reusing the existing WAL append pattern (`src/cortex/memory/wal.py`, `wal_hooks.py`) rather than inventing a new storage mechanism.
- A read accessor (e.g. `memory_wal(operation="tool_telemetry")` or equivalent) that `analyze-tools`/`analyze-session` can call to retrieve the current session's tool-call sequence.
- Updating `.cortex/synapse/agents/analyze-tools.md` (and `.claude/agents/analyze-tools.md` mirror) to reference the new telemetry accessor as an additional evidence source for consolidation-candidate detection, alongside existing `pipeline_handoff` graph queries.
- Redaction rules ensuring no argument payload content (file contents, secrets, user text) is persisted — tool name + arg key names + outcome only.

**out_of_scope**:

- Building a new "Audit LLM" background model profile or cron-based auditor — `analyze-session`/`analyze-tools` already serve this role and should be extended, not duplicated.
- Automatic (unsupervised) skill creation — `write_artifact` calls remain agent/human-reviewed, per existing design.
- Cross-session telemetry aggregation or a dedicated SQLite audit table — session-scoped JSONL via the existing WAL pattern is sufficient for this slice.
- Any change to `write_artifact`'s validation or allowlisted write paths.

## Approach

Reuse `src/cortex/memory/wal.py`'s append-only JSONL pattern to add a session-scoped tool-invocation log, written from the same interception point used by existing MCP tool dispatch (wherever tool calls are currently logged for `query_usage`/anomaly detection, to avoid a second instrumentation site). Expose a read operation for `analyze-tools`/`analyze-session` to consume. Update the two Synapse agent prompt files to cite the new evidence source. Keep the change additive: no existing recommendation logic is removed, only a new input is made available.

## Implementation Steps

1. Identify the existing MCP tool-dispatch interception point already used for `query_usage(query_type="anomalies")` telemetry (grep `src/cortex` for where tool calls are currently recorded) and confirm whether it can be extended rather than duplicated.
2. Add a redacted tool-invocation record model (Pydantic `BaseModel`, no `Any`) capturing tool name, arg key names (not values), outcome, and timestamp.
3. Extend the WAL append path (`src/cortex/memory/wal.py` / `wal_hooks.py`) or the existing dispatch interception point to persist one record per MCP tool call for the current session.
4. Add a read accessor exposed via `memory_wal()` or `pipeline_handoff()` (whichever existing tool already serves session-scoped reads) returning the current session's tool-call sequence.
5. Update `.cortex/synapse/agents/analyze-tools.md` and its `.claude/agents/` / `.cursor/agents/` mirrors to reference the new accessor as an additional consolidation-candidate signal.
6. Add unit tests for the telemetry record model, the append path, and the read accessor (AAA pattern).
7. Run `run_quality_gate()` and confirm no regression in existing `analyze-tools`/`analyze-session` tests.

## Verification Checklist

- Step 1: search `src/cortex/tools` for existing tool-dispatch/telemetry interception; confirm single-source-of-truth before adding a second one.
- Step 3: re-read `src/cortex/memory/wal.py` after edits to confirm append-only invariants (no in-place mutation) are preserved.
- Step 5: re-read `.cortex/synapse/agents/analyze-tools.md` and both mirrors to confirm they stay in sync (per `memory-bank-workflow.mdc` link/sync rules).
- Step 7: re-run `run_quality_gate()` after tests are added; confirm coverage threshold is met.

## Dependencies

- None. Builds on existing `src/cortex/memory/wal.py` and `analyze-tools`/`analyze-session` agents; no other pending plan blocks this.

## Success Criteria

- A tool-invocation telemetry log exists, is session-scoped, append-only, and contains no secret/payload content.
- `analyze-tools` (or `analyze-session`) demonstrably reads the new log and cites it as evidence in at least one recommendation path (verified via test or manual run).
- No duplicate telemetry interception point is introduced.
- `run_quality_gate()` passes with the new code covered.

## Testing Strategy

Target 95% coverage on new code. Unit tests (AAA pattern) for: telemetry record model validation (redaction — arg values never persisted), WAL append behavior (append-only, ordering preserved), read accessor (returns correct session-scoped slice, empty-session edge case). Integration test: simulate a short tool-call sequence and confirm the read accessor surfaces it to a stubbed `analyze-tools` call. Negative case: malformed/oversized argument payloads are truncated/redacted, not persisted verbatim.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Accidental secret/PII leakage into the telemetry log via argument values | Redact to arg key names only; never persist argument values; add a test asserting no value-shaped data appears in log records |
| Duplicate telemetry interception competing with existing `query_usage` anomaly tracking | Step 1 explicitly requires locating and reusing the existing interception point before adding new instrumentation |
| Telemetry log grows unbounded within a long session | Scope to session-lifetime JSONL consistent with existing WAL session-scoping; no new retention policy needed for this slice |
| `analyze-tools`/`analyze-session` prompt drift between `.claude/agents/`, `.cortex/synapse/agents/`, and `.cursor/agents/` mirrors | Update all three locations in the same change; verify via `memory-bank-workflow.mdc` link-validation expectations |

## Review Follow-Up Gaps

- [ ] Tool-invocation telemetry mislabels cancelled MCP tool calls as successful: `_run_tool_with_telemetry()` in `src/cortex/core/mcp_stability.py` unconditionally calls `record_tool_invocation_success()` after `with_mcp_stability()` returns, but `with_mcp_stability()` returns `CANCELLED_RESPONSE_JSON` as a normal (non-exception) value on `asyncio.CancelledError` -- the sibling `UsageTracker` path (`record_usage_finish`) correctly records `success=False`/`error_type='CancelledError'` for this same case, so the new telemetry log is inconsistent with the established mechanism it was explicitly modeled on. (evidence: `src/cortex/core/mcp_stability.py:_run_tool_with_telemetry`, `src/cortex/core/mcp_stability.py:CANCELLED_RESPONSE_JSON`)

## Partial Progress Log

- 2026-07-23: Implemented all 7 plan steps -- `ToolInvocationEntry` model + `ToolInvocationLog` append-only JSONL class reusing `wal_atomic_write_bytes` (`src/cortex/memory/wal.py`); `wal_arg_keys_from_kwargs` + `try_wal_record_tool_invocation` redaction/append helpers (`src/cortex/memory/wal_hooks.py`); `src/cortex/core/mcp_tool_telemetry.py` hooking into the existing `mcp_tool_wrapper` dispatch interception point (`src/cortex/core/mcp_stability.py`, same site `UsageTracker`/`query_usage` anomalies telemetry already uses); `memory_wal(operation="tool_invocations")` read accessor (`src/cortex/tools/memory/wal_tool.py`); updated `.cortex/synapse/cursor-agents/analyze-tools.md` + `.claude/agents/analyze-tools.md` + `.cursor/agents/analyze-tools.md` (verified in sync) to cite the new accessor as an additional consolidation-candidate evidence source. 20 tests added, coverage ~91%, `run_quality_gate()` green. Review gate found the cancellation-mislabeling gap above (not yet fixed) — files: src/cortex/core/mcp_stability.py, src/cortex/core/mcp_tool_telemetry.py, src/cortex/memory/wal.py, src/cortex/memory/wal_hooks.py, src/cortex/tools/memory/wal_tool.py, tests/memory/test_wal.py, tests/memory/test_wal_hooks.py, tests/tools/memory/test_wal_tool.py, tests/unit/test_mcp_tool_telemetry.py, tests/unit/test_mcp_stability_tool_invocation_telemetry.py, .cortex/synapse/cursor-agents/analyze-tools.md, .claude/agents/analyze-tools.md, .cursor/agents/analyze-tools.md

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
