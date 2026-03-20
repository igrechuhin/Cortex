---
title: "Block dirty submodule references in commit workflow"
component: "commit pipeline / git hygiene"
work_type: "fix"
status: "PENDING"
priority: "HIGH"
created: "2026-03-20"
depends_on: []
---

## Goal

Prevent parent-repo commits when submodule pointers reference dirty submodule states, ensuring reproducible commit provenance.

## Context

Review identified `.cortex/synapse` gitlink as `...-dirty`, which can produce non-reproducible review/build states.

## Implementation Steps

1. Add a pre-commit/quality guard that detects dirty submodule state.
2. Fail fast with actionable remediation text (commit/discard inside submodule).
3. Ensure pipeline messages preserve existing zero-errors policy semantics.

## Verification Checklist

- Step 1:
  - What to search for: submodule status checks in commit pipeline
  - Search scope: commit orchestration and execution tools
  - Files to re-read: commit pipeline prompt/tool modules, git helpers
- Step 2:
  - What to search for: error message content and remediation hints
  - Search scope: pipeline error/reporting modules
  - Files to re-read: reporting/exception handling modules
- Step 3:
  - What to search for: zero-errors policy enforcement paths
  - Search scope: commit gate orchestration
  - Files to re-read: gate orchestration files and tests

## Dependencies

- Existing commit workflow checks and git-state inspection utilities.

## Success Criteria

- Commits are blocked when any submodule is dirty.
- Remediation text is clear and actionable.
- Clean-submodule scenarios continue to pass without regressions.

## Testing Strategy (95% coverage target)

- Add unit tests for dirty/clean submodule detection and decision branching.
- Add integration test for commit workflow rejection on dirty submodule.
- Preserve >=95% coverage for touched checking/reporting modules.
