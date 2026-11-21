---
title: "Reuse verified Swift tests in the standard commit workflow"
component: quality-gate
work_type: fix
status: DONE
priority: High
created: 2026-11-21
depends_on: []
execution: agent
---

## Goal

Run the full SwiftPM suite once in a standard Cortex commit when Phase A proves the inputs and Step 12 can verify the same evidence.

## Context

The standard workflow omits the explicit phase intent used by the existing reuse worker. Its config-only final-gate handoff uses the legacy result writer while the gate reads the checks task.

## Scope

- **in_scope** — Cortex server routing, existing SwiftPM evidence, workflow regressions, and API documentation.
- **out_of_scope** — TradeWing checkout or active run, installed plugins, staged-final mode, commits, and pushes.

## Approach

Resolve standard gate roles from the current commit run and its handoffs. Keep the existing project input declaration and independently measured evidence. Require a fresh final gate for Markdown and all applicable checks.

## Implementation Steps

1. Route the legacy config-only commit checks handoff to task storage and preserve the Phase A result.
2. Derive the standard gate role using the verified commit frontier and fresh final-gate handoff.
3. Verify reuse, fresh Markdown checks, and full execution on absent or changed evidence.

## Verification Checklist

- Replay the standard Phase A and Step 12 handoff without explicit intent.
- Confirm changed, unknown, filtered, and foreign inputs cannot authorize reuse.
- Run the Cortex quality and docs gates on the existing checkout.

## Dependencies

Existing detached worker evidence and commit pipeline handoff.

## Success Criteria

An eligible standard commit reports zero final test executions with Phase A provenance. Changed documentation is checked in the final gate. An unverified suite runs fresh.

## Testing Strategy

Exercise the public handoff and gate against local SwiftPM fixtures. Keep worker, ownership, Markdown, and input-fingerprint regressions covered.

## Risks and Mitigation

Preserve project-reviewed exclusions and run ownership. Missing, ambiguous, or changed evidence falls back to the full suite.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
