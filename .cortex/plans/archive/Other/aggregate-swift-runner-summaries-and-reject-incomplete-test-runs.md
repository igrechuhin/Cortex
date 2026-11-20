---
title: "Aggregate Swift runner summaries and reject incomplete test runs"
component: "SwiftAdapter"
work_type: fix
status: DONE
execution: agent
priority: High
created: 2026-11-20
depends_on: []
---

## Goal

Use complete, non-overlapping Swift and XCTest terminal evidence for truthful counts and a fail-closed verdict.

## Context

A filtered log reports 8 cases across two Swift Testing invocations but Cortex shows 4. A full log has 11,116 Swift cases and 5 XCTest cases but shows 98. A previous success can mask a later runner failure or interruption.

## Scope

**in_scope**

- Swift test diagnostic parsing and focused tests.
- Preserve only demonstrated post-completion SIGBUS and non-failing known-issue behavior.

**out_of_scope**

- TradeWing changes, whole Swift reruns, deployment, or publication.

## Approach

Keep authoritative grand totals separate from child XCTest rows. Treat explicit failures and missing completion as negative evidence before allowing any proven teardown exception.

## Implementation Steps

1. Aggregate Swift Testing summary lines and bound XCTest totals to authoritative run logs.
2. Classify explicit Swift and XCTest failures and nonzero exit before any documented teardown allowance.
3. Exercise both replay logs and focused tests, including false-green negative cases.

## Verification Checklist

- Check clean mixed totals and legacy per-bundle fallback without double counting.
- Check an earlier success, later failure or incomplete run, strict exit handling, and known issues.

## Dependencies

None.

## Success Criteria

Focused Cortex suites pass and both real replay logs show corrected totals without rerunning Swift.

## Testing Strategy

Use unit and adapter regressions covering pass, failure, truncation, mixed frameworks, and the documented teardown exception.

## Risks and Mitigation

A narrowed exception can reveal genuine incomplete test runs. Require evidence and leave genuine failures red.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
