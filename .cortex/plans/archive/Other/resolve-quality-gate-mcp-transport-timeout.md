---
title: "Resolve quality-gate MCP transport timeout"
component: quality-gate
work_type: investigation
status: DONE
priority: Blocker
created: 2026-09-17
depends_on: []
execution: agent
---

## Goal

Make the detached quality gate return an observable job handle or final result before the MCP transport deadline.

## Context

On 2026-09-17, run_quality_gate({}) timed out at receive after 30000ms with unknown outcome while verifying the two requested plans. Detached result files exist; do not duplicate workers or report a pass without reading them.

## Scope

**in_scope**

- Trace transport timeout versus detached worker completion and expose reliable result retrieval.
**out_of_scope**
- Unrelated gate failures, plugin behavior, and broad orchestration redesign.

## Approach

Inspect the existing worker/result protocol and request timeout configuration. Reuse the existing detached job contract; prefer returning a handle promptly over increasing all tool timeouts.

## Implementation Steps

1. Recover the specific worker outcome without retrying the gate.
2. Reproduce the response-deadline mismatch with a bounded slow check.
3. Fix the responsible return/poll boundary and verify completed, running, and failed outcomes.

## Verification Checklist

- [x] Trace handler, detached worker, and polling callsites; the former `test_timeout + 60` wait exceeded the client's hard deadline.
- [x] Fresh MCP client with a 30-second deadline received running responses in 20.04–20.13 seconds and preserved terminal check/markdown failures.
- [x] Repeated calls retained job `5738f00f2f71`; live and completed envelopes retained PID 18200. Regression coverage confirms one spawn despite `force_fresh`.
- [x] 69 focused regressions passed; full suite passed 8,092 tests with 91.61% overall coverage. The new bounded-job helper reached 98.28% coverage. Scoped Pyright reported zero errors.
- [x] Synchronous preflight waiting remains unchanged; live checks block auto-fix mutation; stale completed results cannot satisfy a fresh gate.
- [x] Follow-up regressions distinguish infrastructure contention, polling timeout, and worker errors from completed check failures; none records check feedback or fitness.
- [x] Worker marker publication is explicit and independent of the generic atomic writer's host arguments. Commit Phase A uses the bounded public tool; timeout and troubleshooting guidance covers retryable infrastructure states.
- [x] Follow-up verification: 78 focused regressions and 8,099 full-suite tests passed; scoped Pyright reported zero errors.

## Dependencies

- Existing detached pre-commit worker and MCP transport configuration.

## Success Criteria

- Slow gate execution has a timely observable response and a recoverable final result.
- Transport timeout never becomes a false success.

## Testing Strategy

Use a bounded regression for the response boundary with negative worker failure and delayed completion cases; target 95% changed-code coverage and AAA structure.

## Risks and Mitigation

- Duplicate execution: inspect current worker state before any retry.
- Hiding failures: keep terminal status and error payload intact.
