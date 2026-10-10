---
title: "Live Context Occupancy Telemetry"
component: "session-tools"
work_type: feature
status: DONE
priority: High
created: 2026-10-10
depends_on: []
execution: agent
---

## Goal

Surface the live harness context-window occupancy (used tokens vs context limit) in `session()` health output and suggestions, so the agent gets an external token-spend reminder grounded in real usage — closing the gap the archived `session-runtime-token-spend-guard` plan left open.

## Context

Context Language Models (arXiv 2609.37725) shows agents manage their own context well but need an external reminder about token spend. Cortex today has two partial mechanisms, neither of which is that reminder:

- `tools/session/health.py:51-78` (`determine_spend_status`, `SessionSpendSummary`) tracks only Cortex-recorded tool-output tokens (`record_spend_tokens`, `core/session_logger.py:215`) — not how full the actual conversation context is.
- `tools/analysis/token_budget.py:43-63` is a static per-file word-count hint (>500 words) rendered only when explicitly requested; it measures memory-bank file size, not session context.

The MCP server cannot observe the harness context window on its own, and hook payloads cannot carry it: documented Stop/PreCompact hook inputs expose `transcript_path` but no usage snapshot (https://code.claude.com/docs/en/hooks). The verified producer is the status line: the statusline command receives session JSON on stdin at session start and after every assistant message, including `context_window.total_input_tokens` and `total_output_tokens` (tokens currently in the context window, input includes cache reads/writes), `context_window_size` (200k default, 1M extended), pre-calculated `used_percentage`, and `current_usage` per-call breakdown, plus `session_id` (https://code.claude.com/docs/en/statusline). This plan adds a statusline producer that tees those fields into a Cortex snapshot, and `session()` renders it. It deliberately does NOT reuse the word-count hint as an occupancy proxy — file size and live context usage are different quantities and must stay distinct fields.

Predecessor: archived `session-runtime-token-spend-guard` (implemented, DONE) established the pattern this plan mirrors: enum/model pair, threshold helper, session-log persistence, suggestion helper.

## Scope

**in_scope**

- New `ContextOccupancyStatus` enum and `ContextOccupancySummary` model (used_tokens, limit_tokens, as_of, status) in `tools/session/models.py`.
- New `determine_occupancy_status()` helper and wiring into `calculate_health_summary()` / `SessionBrief` health block in `tools/session/health.py`.
- Persistence: new project-scoped snapshot store `tools/session/context_usage_store.py` over `.cortex/.cache/session/context-usage.json` — atomic writes, tolerant reads — shared by the external producer process and the MCP server.
- Statusline producer: a documented `jq` tee script wired into the harness `statusLine` setting; extracts `context_window` fields plus `session_id` from stdin JSON, writes the snapshot store, passes stdin through unchanged so existing statusline output is preserved.
- New constants in `core/constants.py`: default context window, warn/critical occupancy percentages.
- New `add_occupancy_suggestions()` in `tools/session/brief_extraction_helpers.py`, called from `generate_session_suggestions()`.
- Unit and integration tests for all of the above.

**out_of_scope**

- Task-aware context self-editing / context surgery (separate follow-up topic; this plan only supplies the telemetry that would trigger it).
- Any enforcement, blocking, or auto-triggered compaction — warn-only, matching the existing spend guard.
- Transcript-file parsing as a usage source (hook payloads expose `transcript_path` but no usage; transcript parsing stays a possible later channel, out of this plan).
- Harnesses without a statusline JSON channel; other token-accounting changes (`compress_memory_bank`, `token_budget.py`) stay untouched.

## Approach

Mirror the implemented spend-guard pattern, but for harness-reported context occupancy instead of Cortex-recorded tool-output tokens: an enum/model pair, a threshold function, a project-scoped snapshot file written by a statusline producer script (the only verified harness source of live context-window data) and read by `calculate_health_summary()`, and a suggestion helper appended at the existing composition point. Two invariants distinguish it from the predecessor: (1) occupancy is only ever reported from a harness-produced snapshot — no snapshot means `UNAVAILABLE`, never an estimate or a repurposed file-size number; (2) every snapshot carries `as_of`, and TTL-stale data renders as UNAVAILABLE rather than silently wrong. This keeps the change additive, warn-only, and honest about data provenance.

## Implementation Steps

1. Add `DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000`, `CONTEXT_OCCUPANCY_WARN_PERCENT = 80`, `CONTEXT_OCCUPANCY_CRITICAL_PERCENT = 95`, `CONTEXT_USAGE_STALE_AFTER_SECONDS = 900` to `core/constants.py` next to `DEFAULT_SESSION_SPEND_BUDGET`, with an `# AI:` comment stating the window default is a fallback when the payload carries no `context_window_size`.
2. Add `ContextOccupancyStatus` (HEALTHY / WARNING / CRITICAL / UNAVAILABLE) and `ContextOccupancySummary` to `tools/session/models.py`, plus an empty-summary factory returning `UNAVAILABLE` (mirroring `empty_spend_summary`).
3. Add `determine_occupancy_status(used_tokens: int, limit_tokens: int) -> ContextOccupancyStatus` to `tools/session/health.py` with boundary behavior at exactly 80% and 95%.
4. Add `tools/session/context_usage_store.py`: well-known path `.cortex/.cache/session/context-usage.json`, schema `{session_id, used_tokens, limit_tokens, used_percentage, as_of, source}`; atomic `record_context_usage(project_root, snapshot)` (temp file + rename) and tolerant read (missing/corrupted → None). The store is project-scoped because the statusline producer process cannot reach the MCP server's `CORTEX_SESSION_ID`.
5. Add statusline payload parsing: `used_tokens = context_window.total_input_tokens + total_output_tokens`, `limit_tokens = context_window.context_window_size` (payload wins; constant is fallback), `as_of` stamped at write time (statusline JSON carries no clock), `# BELIEF:` annotations on payload-shape assumptions. Payload without `context_window` → no write, status stays UNAVAILABLE.
6. Ship the producer script and wiring docs: `jq` tee script under `scripts/` plus the documented `statusLine` settings snippet; capture one real statusline payload on this host (temporary statusLine command dumping stdin to a file, one Claude Code turn) and commit it as the test fixture — host-produced, not synthetic.
7. Wire `calculate_health_summary()` to read the latest snapshot via the store's tolerant read (TTL-stale → UNAVAILABLE), build `ContextOccupancySummary`, and expose it as a new health field distinct from `spend` and `token_budget_status`.
8. Add `add_occupancy_suggestions()` to `tools/session/brief_extraction_helpers.py` and call it from `generate_session_suggestions()`: warning at >=80% and critical at >=95% with actual used/limit numbers and an action hint (`compress_memory_bank` / `session(operation="compact")`); no suggestion for HEALTHY or UNAVAILABLE.
9. Write tests (see Testing Strategy) in the existing session test modules; run the focused suites, then `run_quality_gate()`.

## Verification Checklist

- After step 1: `rg "CONTEXT_OCCUPANCY|DEFAULT_CONTEXT_WINDOW" src/cortex/core/constants.py` returns the three constants.
- After step 2: `rg "ContextOccupancy" src/cortex/tools/session/models.py` returns enum, model, and UNAVAILABLE factory.
- After step 3: re-read `tools/session/health.py`; boundary unit test asserts 79.9%→HEALTHY, 80%→WARNING, 95%→CRITICAL.
- After step 4: `rg "record_context_usage|context_usage_store" src/cortex/tools/session/context_usage_store.py` returns read/write helpers; test covers corrupted-store tolerance and atomic replace.
- After step 5: unit test feeds the pinned host-produced statusline fixture and asserts one snapshot write with `used = total_input + total_output` and payload `context_window_size`; payload without `context_window` writes nothing.
- After step 6: the committed fixture originates from a real Claude Code statusline capture on this host (temporary statusLine command dumping stdin to a file, one Claude Code turn), and the producer script passes the fixture through without altering statusline output.
- After step 7: `session()` zero-arg brief in a temp project without snapshots shows occupancy UNAVAILABLE; after a synthetic record, shows used/limit and correct status.
- After step 8: `rg "add_occupancy_suggestions" src/cortex/tools/session/brief_extraction_helpers.py` confirms helper + call site; suggestion text absent for HEALTHY/UNAVAILABLE.
- After step 9: focused suites pass; full quality gate clean.

## Dependencies

None pending. Builds on the archived, implemented `session-runtime-token-spend-guard` plan (pattern and persistence substrate); supersedes none of it.

## Success Criteria

- `session()` health exposes a context-occupancy field that reports real used/limit tokens once a statusline-produced snapshot exists for the project.
- Without any recorded snapshot, the field reports UNAVAILABLE — never a fabricated, estimated, or file-size-derived number.
- Verification includes at least one host-produced statusline payload as a fixture; telemetry is never validated solely with synthetic JSON.
- An occupancy suggestion appears in `session_suggestions` iff status is WARNING or CRITICAL, and existing spend/token-budget suggestions are unchanged.
- `compress_memory_bank` and `token_budget.py` behavior is untouched; no tool call is blocked; all existing tests pass.

## Testing Strategy

Target 95% coverage on new/changed code, AAA pattern, deterministic (temp project roots, the pinned host-produced fixture plus synthetic edge payloads, no network):

- Unit: `determine_occupancy_status()` boundaries (79.9%, 80%, 94.9%, 95%, 100%), zero-limit guard.
- Unit: `record_context_usage()` persists latest-wins snapshot atomically; read tolerates missing/corrupted store and returns None.
- Unit: statusline parsing — host fixture writes snapshot with `used = total_input + total_output`; payload `context_window_size` overrides the constant; payload lacking `context_window` writes nothing; fixture's `used_percentage` cross-checked against the computed ratio to pin schema understanding.
- Unit: `add_occupancy_suggestions()` emits for WARNING/CRITICAL with used/limit in text, silent for HEALTHY/UNAVAILABLE.
- Integration: end-to-end `session()` brief before/after a fixture-driven snapshot shows UNAVAILABLE → populated transition.
- Negative: stale snapshot (`as_of` older than a TTL) rendered as UNAVAILABLE, not as live data.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Statusline JSON schema drifts across Claude Code versions; extraction breaks silently | Tolerant extraction with `# BELIEF:` annotations; missing `context_window` → no write + UNAVAILABLE (fail-visible, not fail-wrong); the host-produced fixture pins the verified shape from the documented schema |
| Occupancy confused with the existing spend guard or file-size hint | Distinct field names and docstrings; suggestion text always names used/limit; `token_budget.py` untouched |
| Stale snapshot reported as current | `as_of` timestamp on every snapshot; stale render as UNAVAILABLE |
| 200k default wrong for the active model | Payload limit override wins when present; constant documented as fallback |
| Reminder noise every session once hot | Warn-only suggestion line; thresholds at 80/95 chosen above normal operating range, mirroring the spend guard's noise rationale |
| Statusline not configured on a host; telemetry never populates | Producer ships as a documented one-line `statusLine` snippet; UNAVAILABLE is the honest default, not an error |
