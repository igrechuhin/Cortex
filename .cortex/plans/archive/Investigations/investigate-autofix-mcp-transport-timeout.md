---
title: Investigate autofix MCP transport timeout
component: quality-gates
work_type: investigation
status: DONE
priority: Blocker
created: 2026-09-17
execution: agent
---

## Goal

Make autofix completion observable within the MCP client deadline without losing running work.

## Context

During repair-existing-plan-registration-update, autofix({}) timed out at 30000ms with unknown outcome. Its detached worker completed successfully in about 28 seconds. The mounted quality endpoint also timed out, while a fresh-process invocation of the current code returned a bounded resumable handle and later a terminal result. Investigate both autofix's unbounded polling and whether the mounted MCP server requires a reload after source changes. Recovered evidence: `.cortex/.session/plan-registration-repair-evidence.json`.

## Scope

**in_scope**: autofix transport lifetime and outcome recovery.
**out_of_scope**: registration behavior and unrelated formatting changes.

## Approach

Trace the actual autofix execution and reuse existing bounded-job reporting where appropriate.

## Implementation Steps

1. Capture timeout and worker completion evidence.
2. Repair outcome reporting without duplicate work or lost failures.
3. Verify delayed execution through the real MCP transport.

## Verification Checklist

- [x] Client returns before its deadline.
- [x] Running and completed outcomes remain retrievable.
- [x] No overlapping mutation workers.

## Dependencies

Existing autofix and quality job infrastructure.

## Success Criteria

Slow autofix returns a bounded observable outcome instead of a transport timeout.

## Testing Strategy

Focused job lifecycle tests and an actual transport smoke.

## Risks and Mitigation

Do not restart unknown in-flight mutation work; recover its state first.

## Change History

- 2026-09-17: Recovered the original 28.092-second worker completion. Replaced autofix's 960-second request polling and synchronous postprocessing with a 20-second bounded coordinator; finalization now belongs to the durable worker. Retained undelivered success/error/legacy outcomes and guarded quality/fix overlap.
- 2026-09-17: Focused lifecycle suite passed (42 tests). Real stdio MCP smoke used a 30-second client deadline and a 35-second injected finalization delay: worker duration 64.871 seconds; pending responses 20.034, 20.126, and 20.029 seconds; terminal delivery 5.094 seconds. A fresh MCP server resumed PID 4804; the quality gate returned the same live job in 0.029 seconds. Evidence: `.cortex/.session/autofix-transport-evidence.json`.
- 2026-09-17: Confirmed fresh servers expose the bounded autofix description while the already-mounted server retains its earlier description. Source updates require MCP reload; persisted workers and outcomes survive reconnect.
- 2026-09-17: Full quality and docs gates passed: 8,104 tests passed, 4 skipped, 91.8% repository coverage; formatting, lint, spelling, and type checks clean. Replaced obsolete wrapper-lock assertions with real coordinator concurrency coverage; retained failed-gate detail coverage in persisted-envelope tests. The gate driver now uses MCP roots rather than a fallback-root environment override. Added and verified poll-timeout and completed-outcome/lock-contention recovery cases (11 autofix lifecycle tests passing). Gate evidence: `.cortex/.session/autofix-final-gate-evidence.json`.
- 2026-09-17: Updated the real quality-gate workflow smoke to resume `running` handles before asserting terminal success or failure. The deterministic two-second request budget passed against real detached workers (17.39 seconds for both outcomes). Autofix coordinator coverage reached 98.11%.
