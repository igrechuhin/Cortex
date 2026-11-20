---
status: PENDING
---

## Goal

Run the complete SwiftPM suite once on the final staged candidate.

## Context

TradeWing has over 614k linked regular inputs; historical cross-gate reuse is difficult to prove.

## Scope

Additive Cortex-only plan. No TradeWing or separate Synapse edits.

## Approach

Opt-in fast Phase A with explicit deferred tests, then final full coverage on frozen staged inputs; no early success or external push.

## Implementation Steps

Define server receipt and compatibility, then coordinate Synapse ordering.

## Verification Checklist

Reject edits, crashes, filters, failure and stale receipts before any commit.

## Dependencies

Matching Synapse client before activation.

## Success Criteria

Exactly one full final suite in normal uninterrupted commit with all independent guards.

## Testing Strategy

Fixture gate/ownership/order and preserve standalone gate, fix and old clients.

## Risks and Mitigation

Default off. Never mark tests passed early or skip required checks.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
