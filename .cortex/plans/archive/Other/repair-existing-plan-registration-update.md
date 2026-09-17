---
title: Repair existing plan registration updates
component: plan-lifecycle
work_type: investigation
status: DONE
priority: Blocker
created: 2026-09-17
depends_on: []
execution: agent
---

## Goal

Allow an existing non-complete plan's roadmap status and description to be updated without deleting its registration or returning a false missing-section error.

## Context

While recording plugin verification blockers, plan(register, section=pending) returned "Section 'pending' not found" although that section exists. register_helpers._insert_entry_in_section returns no inserted line for an existing plan path; register.py treats that result as a missing section. The guarded roadmap_remove operation correctly refuses deleting non-complete plans, so remove/re-add is not an available update path. Existing registration was preserved.

## Scope

**in_scope**

- Idempotent registration and in-place status/description updates for the same canonical plan path.
**out_of_scope**
- Removing unfinished plans, changing completion semantics, or plugin behavior.

## Approach

Reuse the existing structured roadmap transaction. Distinguish a missing section from an existing registration, preserve its position and unrelated content, and keep unfinished-plan removal guards.

## Implementation Steps

1. Reproduce re-registering an existing plan in an existing section.
2. Update the existing matching entry without creating duplicates or deleting the registration.
3. Verify unchanged re-registration, changed status/description, and genuinely missing sections.

## Verification Checklist

- [x] Trace register_helpers._insert_entry_in_section through register.py result handling.
- [x] Verify exact unrelated roadmap content and one canonical plan reference remain.
- [x] Verify failed writes leave the original registration intact.

## Dependencies

Existing roadmap parser, registration transaction, and removal safety guard.

## Success Criteria

Existing registration updates succeed; unchanged re-registration is idempotent; missing-section diagnostics only describe genuinely missing sections.

## Testing Strategy

Use behavior-level AAA cases for a real roadmap with an existing non-complete plan, preserving unrelated entries and order. Target 95% changed-code coverage.

## Risks and Mitigation

- Duplicate references: match canonical plan paths and retain one entry.
- Accidental removal: preserve existing completion/removal guards and transaction behavior.

## Implementation Evidence

- Existing entries now return their actual line and update in place; pathless exact replays preserve section headers.
- Roadmap writes stage a same-directory replacement and retain existing permissions; partial-write and replacement failures preserve the original registration.
- Removed two obsolete regressions that required re-registration to fail or silently ignore updates.
- Six behavior regressions cover update/replay, unchanged registration, partial-write failure, replacement failure, pathless replay, and unknown sections.
- Focused registration/task-graph/roadmap suite: 123 passed.
- Autofix transport exceeded 30 seconds; its detached worker completed successfully. A separate ASAP investigation tracks bounded outcome reporting.
- Full detached quality worker: all eight checks passed; 8,104 tests passed, four skipped, 91.73% overall coverage; all 12 changed executable statements covered (100%).
- Evidence: `.cortex/.session/plan-registration-repair-evidence.json`.
