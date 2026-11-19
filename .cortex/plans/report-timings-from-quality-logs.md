---
status: PENDING
---

## Goal
Report measured phase wall time and slowest tests.

## Context
TradeWing parallel test groups make sums misleading.

## Scope
- In scope: read-only report and fixtures.
- Out of scope: changes to scheduling, test thresholds or reconnect.

## Approach
Parse timestamped invocation events and Swift Testing results.

## Implementation Steps
1. Add a deterministic CLI report.
2. Verify fixtures and real logs.

## Verification Checklist
- Show repeated phases and incomplete inputs.

## Dependencies
None.

## Success Criteria
Elapsed and individual durations distinct.

## Testing Strategy
Fixtures and real logs.

## Risks and Mitigation
Never infer missing timestamps.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
