# Phase 93: Usage Events Collection Pipeline Investigation

Status: PENDING

## Goal

Investigate and fix why usage analytics events stopped being written under `.cortex/synapse/.cache/usage/events`, restoring reliable event collection for `query_usage` and related monitoring features.

## Context

- The `.cortex/synapse/.cache/usage/events` directory appears to have stopped receiving new events.
- A recent `query_usage(query_type="events", hours=168)` call returned **no events**, confirming that the analytics pipeline is currently producing an empty stream.
- Usage events and `query_usage` are used for:
  - Tool usage analytics and optimization.
  - Anomaly detection and production monitoring.
  - Session-level insights and recommendation features.
- This regression reduces observability for MCP tool behavior and can hide real anomalies in production.

## Approach

Take a staged approach: first confirm the break and its time window, then map the full event collection pipeline, identify the failing segment (instrumentation, transport, or writer), and finally harden the pipeline and monitoring so similar silent failures are caught early.

## Implementation Steps

1. **Confirm current behavior and failure window**
   1. Use `query_usage(query_type="events")` over varying windows (last 24h, 72h, 7d, 30d) to pinpoint when events became empty.
   2. Inspect `.cortex/synapse/.cache/usage/events` on disk (file count, sizes, mtimes) and compare against git history / previous snapshots to understand expected shape and rotation behavior.
   3. Document the last-known-good period and the first empty-period window in this plan.

2. **Map the end-to-end events pipeline**
   1. Use `SemanticSearch`/`Grep` to locate the code responsible for:
      - Emitting usage events (instrumentation around MCP/tool calls).
      - Serializing events and writing them under `.cortex/synapse/.cache/usage/events`.
      - Reading/aggregating those events to back `query_usage(query_type="events", ...)`.
   2. Sketch a simple flow diagram (in this plan) of the pipeline: *caller → event builder → writer → storage → query_usage*.
   3. Identify all configuration and environment dependencies (paths, feature flags, sampling/ratelimiting, error-handling switches).

3. **Check for configuration, path, or environment regressions**
   1. Verify that the configured events directory still resolves to `.cortex/synapse/.cache/usage/events` in all relevant execution modes (local, Cursor Cloud, tests).
   2. Inspect recent changes around:
      - Cache/usage configuration.
      - File-system sandboxing or path resolution utilities.
      - Any guards that may short-circuit event writes on errors (e.g. to avoid blocking user flows).
   3. Add targeted logging or assertions (behind a debug flag) to confirm whether the event-writing path is being reached at runtime.

4. **Instrument and diagnose the writer path**
   1. Add temporary instrumentation around the event writer to log:
      - Number of events attempted vs actually written.
      - Any exceptions when opening/writing/rotating event files.
      - Locking or concurrency failures if a lock-based writer is used.
   2. Run controlled scenarios (e.g. small synthetic sessions) to see whether events are being constructed but fail to persist, or never constructed at all.
   3. Capture and summarize findings in this plan.

5. **Identify and implement the fix**
   1. Based on diagnostics, fix the root cause. Examples include (not exhaustive):
      - Incorrect or missing path resolution for the events directory.
      - Overly strict sandbox or permission errors silently caught and dropped.
      - A refactor that removed or bypassed instrumentation call sites.
      - A concurrency/locking regression that prevents writes on some paths.
   2. Ensure the fix is applied in a minimal, well-scoped way with clear separation between:
      - Event construction.
      - File I/O and rotation.
      - Query layer (`query_usage`) semantics.
   3. Update or add configuration defaults if misconfiguration contributed to the break.

6. **Harden monitoring and alerts**
   1. Extend `query_usage`-based reporting so that prolonged periods of **zero events** for active sessions are treated as anomalies, not normal behavior.
   2. Add a light-weight health check (or dashboard metric) that surfaces:
      - Recent event volume.
      - Last event timestamp.
      - Any writer error counters.
   3. Ensure these signals are visible in existing analysis/health tooling so similar failures are caught quickly.

7. **Cleanup, documentation, and follow-up**
   1. Remove temporary debug logging once the pipeline is stable.
   2. Document the final pipeline (with a short diagram and description) in the relevant technical docs or memory bank.
   3. Add a short entry to `activeContext` and `progress` summarizing the incident, root cause, and fix.
   4. If appropriate, propose a follow-up phase for broader observability improvements.

## Testing Strategy (MANDATORY)

- **Coverage target**: Achieve **≥ 95% coverage** for any new or significantly modified modules in the event emission, writing, and `query_usage` paths.
- **Unit tests**:
  - Add or extend tests for the event writer component to verify:
    - Successful append/rotate behavior under normal conditions.
    - Robust handling of I/O failures (e.g. directory missing, permission errors) without silent data loss.
  - Add tests for event construction helpers to ensure schema consistency and required fields.
- **Integration tests**:
  - Create integration tests that:
    - Emit synthetic usage events through the normal instrumentation path.
    - Confirm that the events are persisted under `.cortex/synapse/.cache/usage/events`.
    - Verify that `query_usage(query_type="events", ...)` returns the expected non-empty event summaries.
- **Regression tests**:
  - Add a regression test that simulates the previously failing conditions (e.g. misconfigured path or environment) and asserts that:
    - The failure is either impossible under the new design, **or**
    - It surfaces as an explicit, observable error rather than a silent absence of events.
- **Structured JSON and Pydantic**:
  - When testing MCP tool responses or internal event schemas, prefer Pydantic v2 models and `model_validate_json()` / `model_validate()` over raw dict assertions.
  - Ensure event models are validated and that tests assert on the model fields rather than untyped dictionaries.
- **AAA pattern and naming**:
  - Ensure all new tests follow Arrange–Act–Assert.
  - Use standard test naming (`test_<behavior>`) so they are picked up by existing test-naming checks.

## Risks and Mitigations

- **Risk: Hidden multi-environment differences** (local vs CI vs Cursor Cloud) could cause events to work in one environment but not others.
  - **Mitigation**: Explicitly test event writing and `query_usage` in all supported environments, and encode key assumptions in tests.
- **Risk: Added diagnostics impacting performance** if left enabled.
  - **Mitigation**: Gate heavy diagnostics behind debug flags and ensure they are disabled by default in normal operation.
- **Risk: Further regressions due to tight coupling** between analytics and core execution paths.
  - **Mitigation**: Keep analytics side-effectful but non-blocking, and maintain clear separation of concerns in code structure.

## Timeline (Initial Estimate)

- **Day 1–2**: Confirm failure window, map pipeline, and perform initial diagnostics.
- **Day 3–4**: Implement and iterate on the fix, add tests and regression coverage.
- **Day 5**: Harden monitoring, finalize documentation, and clean up temporary instrumentation.
