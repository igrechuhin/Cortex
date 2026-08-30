---
title: "Stop Synapse usage cache collection by default"
component: "usage-tracking"
work_type: fix
status: PENDING
priority: High
created: 2026-04-22
depends_on: []
---

## Goal

Disable default usage analytics writes to `.cortex/synapse/.cache/usage` unless explicitly opted in.

## Context

Current behavior writes usage events into the Synapse submodule cache by default when `.cortex/synapse` exists, which creates noisy analytics churn and unwanted data collection in normal workflows. The desired behavior is opt-in persistence only, while preserving analytics functionality for users who intentionally enable it.

## Scope

**in_scope** —

- Define and enforce an opt-in default for usage persistence (`usage_writable` false unless explicitly true).
- Update usage storage resolution and write-gating logic so default sessions do not write under `.cortex/synapse/.cache/usage`.
- Update usage tracking and related tests to validate default no-write behavior and explicit opt-in behavior.
- Update docs that currently describe Synapse usage cache collection as default behavior.

**out_of_scope** —

- Removing usage analytics tools, resources, or query interfaces.
- Migrating or deleting historical usage files that already exist in local checkouts.
- Reworking non-usage cache directories (for example session caches unrelated to usage events).

## Approach

Treat usage persistence as an explicit policy, not implicit environment detection. The implementation should centralize the default in the Synapse usage configuration loader and ensure all writers honor that gate before touching disk.

Keep read-side compatibility intact so existing query tools still behave predictably when cache data exists. Documentation and tests should align with the new default to prevent future regressions.

## Implementation Steps

1. Review current usage config and write path flow in `src/cortex/core/synapse_usage_config.py`, `src/cortex/managers/usage_tracker.py`, and `src/cortex/managers/usage_tracker_events.py`.
2. Change configuration defaults so `usage_writable` is false when no explicit opt-in is present.
3. Ensure all usage event write paths short-circuit cleanly when `usage_writable` is false.
4. Add or update tests for both modes: default no-write and explicit opt-in write to Synapse usage cache.
5. Update architecture docs and developer guidance to state that Synapse usage persistence is opt-in.
6. Run project quality checks and confirm no behavior regressions in usage analytics querying.

## Verification Checklist

1. Search `src/` for usage write call sites and confirm each uses the same write-gate helper.
2. Re-read changed config and tracker files to confirm no implicit fallback re-enables Synapse writes.
3. Search docs for `.cortex/synapse/.cache/usage` references and verify wording reflects opt-in semantics.
4. Re-read affected tests to confirm both disabled and enabled scenarios are asserted.
5. Confirm no plan step requires direct edits outside usage config/tracker/docs/tests scope.

## Dependencies

- No external plan dependencies.
- Depends on existing usage analytics architecture and test fixtures for usage tracking.

## Success Criteria

- Default configuration no longer writes usage events to `.cortex/synapse/.cache/usage`.
- Explicit `usage_writable: true` still enables usage event persistence.
- Tests cover both default-disabled and explicit-enabled behavior.
- Documentation consistently describes usage persistence as opt-in.

## Testing Strategy

- Target 95% coverage for modified modules.
- Add or update unit tests for config default resolution and write gating.
- Add integration-level coverage for end-to-end usage event recording behavior under both configurations.
- Include negative tests proving no files are written when usage persistence is disabled.
- Follow Arrange-Act-Assert structure for all new/updated tests.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Query tools assume writable mode and regress when default changes | Keep read/query code paths unchanged and add compatibility tests. |
| Hidden writer path bypasses the central gate | Audit all usage event writes via repo-wide search and add regression tests. |
| Documentation drift causes future reintroduction of default writes | Update architecture docs in the same change and include doc assertions in review checklist. |
