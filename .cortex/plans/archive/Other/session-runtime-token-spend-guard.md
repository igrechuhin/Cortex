---
title: "Session Runtime Token-Spend Guard"
component: "session-tools"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-07-20"
depends_on: []
---

## Goal

Add a runtime token-spend guard to `session()` that tracks the actual tokens
consumed by tool-call activity *within the current session* and warns when
spend crosses a configurable threshold — distinct from the existing
`token_budget_status`, which only measures the static on-disk size of memory
bank files (`tools/session/health.py:determine_token_budget_status`) and says
nothing about how expensive the running session itself has become.

## Context

`session()` already reports `token_budget_status` (healthy/warning/over_budget)
computed purely from the byte size of the 7 required memory-bank files
(`tools/session/health.py:32-43`). That check cannot detect a session that
has become expensive through its own activity — large `manage_file` reads,
repeated large tool outputs, etc. Separately, `core/session_logger.py`
already persists a per-session JSON log (`context-session-<id>.json`, keyed
by the `CORTEX_SESSION_ID` env var) but only for `load_context` calls
(`LoadContextLogEntry`), and nothing reads that log back into `session()`'s
health output today.

This gap was scoped down from a broad "guard session cost efficiency" ask.
The user selected the "runtime spend tracking + warning" mechanism
(informational cost reports and tool-call/subagent-count caps were
explicitly deferred — see Out of Scope) via `AskUserQuestion` during plan
creation on 2026-07-20.

## Scope

**in_scope**

- New `SessionSpendStatus` enum and `SessionSpendSummary` model in
  `tools/session/models.py`, following the existing `TokenBudgetStatus` /
  `SessionHealthSummary` pattern.
- New `determine_spend_status()` helper in `tools/session/health.py`
  mirroring `determine_token_budget_status()`, using a new
  `DEFAULT_SESSION_SPEND_BUDGET` constant in `core/constants.py`.
- Extend `core/session_logger.py`'s `SessionLog` model with a
  `cumulative_spend_tokens: int` field and a `record_spend_tokens()`
  function that increments and persists it, reusing the existing
  `_get_session_log_path` / `_load_session_log` / `_save_session_log`
  helpers (no new storage mechanism).
- Instrument a bounded, high-signal set of call sites to feed the spend
  tracker: `manage_file` read/write responses (already compute token counts
  via `MetadataIndex`) and `session()`'s own brief `token_count` field. Do
  not instrument every MCP tool in this plan.
- Wire the accumulated spend into `calculate_health_summary()` /
  `SessionBrief` as a new `spend: SessionSpendSummary` field.
- New `add_spend_suggestions()` helper in
  `tools/session/brief_extraction_helpers.py`, called from
  `generate_session_suggestions()`, mirroring
  `add_budget_and_missing_suggestions()` — appends a warning suggestion
  (never blocks) when spend status is `warning` or `over_budget`.
- Unit tests covering: threshold boundaries, log accumulation across
  multiple recorded calls, suggestion text generation, and safe defaults
  when no session log exists yet or the log file is corrupted/missing.

**out_of_scope**

- True LLM API dollar-cost tracking (actual Anthropic usage/billing
  data) — the MCP server has no visibility into that.
- Any enforcement/blocking of tool calls; this plan is warn-only, matching
  the existing `token_budget_status` behavior.
- Tool-call-count or subagent-spawn-count caps (a distinct axis the user
  explicitly deferred in favor of token-based tracking).
- Instrumenting every MCP tool call site — only the bounded set listed
  above.
- Auto-triggered compaction/checkpointing — the guard only surfaces a
  suggestion; the user/agent decides whether to call
  `session(operation="compact")`.
- Cross-session aggregate reporting or `/cortex/analyze` integration.

## Approach

Mirror the existing static `token_budget_status` mechanism exactly, but for
runtime spend instead of file size, so the change is additive and low-risk:
a new enum/model pair, a new threshold function, a small extension to the
existing per-session JSON log (which already has session-scoped identity via
`CORTEX_SESSION_ID`), and a new suggestion helper wired into the existing
`generate_session_suggestions()` composition point. Because
`core/session_logger.py` already solves session identity and persistence for
`load_context` tracking, this plan extends that file rather than building a
parallel mechanism. Instrumentation is deliberately narrow at first (two call
sites) to keep the change reviewable and to validate the approach before any
future plan considers wider instrumentation.

## Implementation Steps

1. Add `DEFAULT_SESSION_SPEND_BUDGET` (and a `MAX_SESSION_SPEND_BUDGET` if a
   ceiling is useful) to `core/constants.py`, next to the existing
   `DEFAULT_TOKEN_BUDGET` / `MAX_TOKEN_BUDGET`.
2. Add `SessionSpendStatus` enum and `SessionSpendSummary` model to
   `tools/session/models.py`, matching the field style of
   `TokenBudgetStatus` / `SessionHealthSummary`.
3. Add `determine_spend_status(cumulative_tokens: int, budget: int) ->
   SessionSpendStatus` to `tools/session/health.py`, unit-testable in
   isolation like `determine_token_budget_status`.
4. Extend `SessionLog` in `core/session_logger.py` with
   `cumulative_spend_tokens: int = Field(default=0, ge=0, ...)` and add
   `record_spend_tokens(project_root: Path, tokens: int) -> int` that loads
   the log, increments the field, saves it, and returns the new total.
5. Call `record_spend_tokens()` from the `manage_file` read/write result
   path (wherever token counts are already computed via `MetadataIndex`) and
   from `session()`'s own brief-building path, passing the already-computed
   token counts — no new token-counting logic, only recording an existing
   number.
6. In `calculate_health_summary()` (`tools/session/health.py`), read the
   current session's cumulative spend via `read_session_log()` /
   `get_session_log_path()`, compute `SessionSpendSummary` via
   `determine_spend_status()`, and add it to `SessionHealthSummary` (or a
   sibling field on `SessionBrief` if `SessionHealthSummary` should stay
   file-size-only — decide during implementation and document the choice
   with an `# AI:` comment).
7. Add `add_spend_suggestions()` to
   `tools/session/brief_extraction_helpers.py` and call it from
   `generate_session_suggestions()`, appending a warning message only for
   `warning` / `over_budget` states (never for `healthy`).
8. Write unit tests for steps 2–7 (see Testing Strategy) under the existing
   test modules for these files (e.g. alongside
   `tests/tools/test_session_start_tool_wrapper.py` and a session_logger
   test module).
9. Run `run_quality_gate()` and fix any type/lint/format issues.
10. Update `activeContext.md` / `progress.md` via `update_memory_bank()`
    once implemented (handled by `/cortex/commit`, not this plan step).

## Verification Checklist

- After step 2: `rg "SessionSpendStatus|SessionSpendSummary"
  src/cortex/tools/session/models.py` returns the new definitions.
- After step 4: `rg "cumulative_spend_tokens|record_spend_tokens"
  src/cortex/core/session_logger.py` returns the new field/function; re-read
  the full file to confirm `SessionLog.model_dump()` round-trips the new
  field (no `extra="forbid"` breakage on old log files missing the field —
  confirm a default is supplied).
- After step 5: `rg "record_spend_tokens"` across `src/cortex/tools` to
  confirm both call sites (manage_file, session start) are wired.
- After step 6: re-read `tools/session/health.py` and
  `tools/session/models.py` together to confirm `SessionBrief`/
  `SessionHealthSummary` exposes the new spend field end-to-end.
- After step 7: `rg "add_spend_suggestions"
  src/cortex/tools/session/brief_extraction_helpers.py` confirms the helper
  exists and is called from `generate_session_suggestions`.
- After step 8: run the new/updated test files directly and confirm all
  assertions pass before running the full quality gate.

## Dependencies

None. This plan is additive to existing session-tools modules and does not
depend on other pending plans (`content-preserving-wal-as-of.md` is
unrelated).

## Success Criteria

- `session()` output includes a new spend/session-cost field that reflects
  actual accumulated tool-output tokens for the current `CORTEX_SESSION_ID`,
  not just static memory-bank file size.
- A session whose recorded spend crosses the configured warning/over-budget
  threshold produces a corresponding entry in `session_suggestions`, and a
  session below threshold does not.
- No existing `session()` or `manage_file()` test regresses; new tests pass.
- No tool call is blocked or altered in behavior by this change — purely
  additive telemetry and warning text.

## Testing Strategy

Target 95% coverage on all new/changed code, AAA pattern, deterministic
(no real clock/network dependency — use injected/fixed token counts and a
temp project root for log file I/O):

- Unit: `determine_spend_status()` at exact boundary values (just under,
  at, and just over warning/over_budget thresholds).
- Unit: `record_spend_tokens()` accumulates correctly across multiple calls
  and persists via a temp `project_root` fixture; verify it tolerates a
  missing/absent log file (creates one) and a log file predating this field
  (backward-compatible default of 0).
- Unit: `add_spend_suggestions()` emits the expected message for `warning`
  and `over_budget`, and emits nothing for `healthy`.
- Integration: `calculate_health_summary()` / `session()` end-to-end
  produces the new field with a non-zero value after a synthetic
  `record_spend_tokens()` call in a temp project.
- Negative: corrupted/invalid session log JSON is handled without raising
  (falls back to a fresh log), matching existing `_load_session_log`
  error-tolerance expectations — add an explicit test if none currently
  covers this path.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Double-counting tokens if both `manage_file` and `session()` instrumentation paths overlap for the same call | Instrument only the two named call sites; add a unit test asserting a single `manage_file` call increments spend exactly once |
| Backward compatibility break for existing `context-session-*.json` log files without the new field | Field ships with `default=0`; add a test loading a fixture log file that predates the field |
| Threshold too aggressive, causing suggestion noise every session | Default budget chosen generously (document the chosen constant with an `# AI:` comment on why); warn-only design means false positives cost a suggestion line, not a blocked action |
| Scope creep into instrumenting every MCP tool | Explicitly bounded in Scope/Implementation Steps to two call sites; any wider instrumentation is a follow-up plan |
