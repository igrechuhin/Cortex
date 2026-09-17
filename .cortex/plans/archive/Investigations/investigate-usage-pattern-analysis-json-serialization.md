---
title: Investigate usage-pattern analysis JSON serialization failure
component: analysis
work_type: investigation
status: DONE
priority: Blocker
created: 2026-09-16
depends_on: []
execution: agent
---

## Goal

Make the public usage-pattern analysis response serialize real co-access results successfully.

## Context

The non-blocking post-prompt hook for project-review remediation returned `TypeError: Object of type CoAccessPattern is not JSON serializable` from `cortex://analysis` with `analysis_target: usage_patterns`. Original session routing was restored; no stale zero-argument handoff was flushed. The remediation quality/docs gates passed independently.

Verified 2026-09-17: the public resource reached
`analysis_run_helpers.analyze_usage_patterns`, which returned raw Pydantic models
in three collections. Each now uses `model_dump(mode="json")`; the nominated
`insight_usage_org` serializer was already correct. A real FastMCP resource read
preserved the nonempty pair and its count of five. Nine resource regressions cover
nonempty, empty, below-threshold, inventory, and cross-workspace behavior.

The separate confirmed inventory defect counted rule categories instead of rules;
`RuleAnalyzer.analyze` now sums category contents. Populated and empty fixtures
resolve the selected workspace correctly even from another working directory.
The historical zero prompt/rule totals were not reproduced as a discovery or
routing defect, so no such repair is claimed. Original routing remains byte-for-byte
unchanged (398 bytes); no stale zero-argument handoff was flushed.

Final verification: all eight quality checks passed with 8,082 tests, four skips,
and 91.61% overall coverage. Documentation timestamps, roadmap synchronization,
and roadmap/progress consistency passed. The MCP quality call exceeded its
30-second transport deadline; its detached outcome was recovered and final
verification used the same worker CLI with an explicit result path. That transport
issue is separately registered; no gate failure was treated as a pass.

## Scope

**in_scope**

- Trace the usage-pattern response and nested CoAccessPattern serialization.
- Reproduce with real analysis models and correct the narrow response boundary.
- Check the separately observed zero prompt/rule totals against populated Synapse directories; establish whether routing, discovery, or counting is responsible before changing behavior.

**out_of_scope**

- Plugin packaging, hook redesign, analytics features, and memory compaction.
- Reopening the completed project-review remediation or rewriting existing history.

## Approach

Use existing Pydantic 2 JSON serialization conventions. Preserve the public fields and actual pattern evidence rather than stringifying or dropping model objects.

Start at `src/cortex/analysis/insight_usage_org.py:_analyze_co_access_patterns`
and trace the public resource serializer. A nested-model serialization gap is a
lead, not yet a confirmed complete root cause. Inspect prompt/rule analyzer
project roots separately; do not interpret zero totals as valid empty input
without comparing them to the selected workspace.

## Implementation Steps

1. Locate the public analysis handler and reproduce a nonempty co-access result.
2. Serialize nested models at the responsible response boundary using existing patterns.
3. Verify nonempty, empty, and below-threshold co-access results through the resource.
4. Compare prompt/rule counts to populated and empty temporary workspaces, including invocation from a different working directory. Fix a confirmed routing/discovery defect at its owning boundary without expanding analytics scope.
5. Run focused regressions and quality/docs gates; document the actual root causes and restore session configuration.

## Verification Checklist

- [x] Real nonempty co-access patterns return successful JSON with their fields preserved.
- [x] Empty analysis results keep their documented behavior.
- [x] Populated prompt/rule directories yield their actual counts; empty directories remain valid zero results.
- [x] Selecting one workspace cannot report another workspace's patterns or inventory.
- [x] Original session routing is preserved after verification.
- [x] Focused regressions and quality/docs gates pass.

## Dependencies

Existing usage-pattern models, resource routing, and Pydantic 2 serialization.

## Success Criteria

The public resource no longer returns this TypeError for real co-access patterns; a behavior-level regression protects the fix.

## Testing Strategy

Use isolated session data and real models. Assert meaningful pattern fields in parsed JSON, not merely a success key. Use AAA regressions for the observed failures, including nested models and cross-workspace isolation; target at least 95% coverage of changed behavior. Do not re-run the known live failure merely to confirm it before investigating.

## Risks and Mitigation

- Nested models may appear in several fields: inspect the whole response boundary.
- Legacy routing contains unrelated phase state: use explicit scoped requests and restore configuration; never flush stale completion claims.
