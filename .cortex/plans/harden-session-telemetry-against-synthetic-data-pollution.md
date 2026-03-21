---
title: "Harden session telemetry against synthetic data pollution"
component: "session analytics / context-usage statistics"
work_type: "fix"
status: "IN_PROGRESS"
priority: "MEDIUM"
created: "2026-03-20"
depends_on: []
---

## Progress (2026-03-21)

- Done: schema field `record_quality` / `ContextTelemetryRecordQuality`; classification module; production-only rollups and exclusion logging; unit tests for classification and rollup behavior.
- Remaining: metrics-level observability (step 4); optional stricter write-path validation; consider migration/backfill for existing persisted rows.

## Goal

Improve reliability of persisted telemetry by filtering or labeling synthetic/test sessions and enforcing entry validity checks.

## Context

Review found repeated synthetic-like entries (e.g., `Test task`) and frequent zero-budget records that can skew optimization outputs and recommendations.

## Implementation Steps

1. Define telemetry schema constraints for production analytics records.
2. Add synthetic-session detection/flagging and exclude from aggregate rollups.
3. Add validation for non-trivial task entries with invalid budget/file selections.
4. Add observability for dropped/flagged telemetry events.

## Verification Checklist

- Step 1:
  - What to search for: telemetry model definitions and write paths
  - Search scope: session/context-usage modules
  - Files to re-read: telemetry writer/aggregator modules
- Step 2:
  - What to search for: synthetic/test marker handling
  - Search scope: telemetry ingestion and aggregation logic
  - Files to re-read: telemetry ingestion module and tests
- Step 3:
  - What to search for: validation rules for token budget/files selected
  - Search scope: analytics validation code
  - Files to re-read: validators, rules, related tests
- Step 4:
  - What to search for: metrics/logging for filtered entries
  - Search scope: logging/metrics modules
  - Files to re-read: telemetry reporting modules

## Dependencies

- Existing telemetry model and persistence format compatibility.

## Success Criteria

- Synthetic/test events do not pollute production optimization statistics.
- Invalid non-trivial records are rejected or clearly marked.
- Aggregate recommendations become stable and trustworthy.

## Testing Strategy (95% coverage target)

- Add unit tests for filtering/validation branches and rollup behavior.
- Add regression tests using representative synthetic vs production session samples.
- Maintain >=95% coverage for touched analytics modules.
