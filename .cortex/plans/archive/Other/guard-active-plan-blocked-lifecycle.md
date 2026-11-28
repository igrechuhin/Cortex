---
title: "Guard the active Cortex plan block transition"
slug: guard-active-plan-blocked-lifecycle
status: DONE
execution: agent
created: 2026-11-28
---

## Goal

Allow an explicit, guarded transition to BLOCKED on an existing active plan when its canonical roadmap row already records the blocker.

## Context

Registration intentionally preserves existing READY metadata. The guarded editor protects frontmatter. Four TradeWing plan files therefore still appear ready in the dependency graph after their roadmap rows were reconciled.

## Scope

Extend the existing unified plan tool, cover the transition with focused tests, and verify the actual graph from the source runtime. Keep execution owners, unrelated plan bytes, the guarded editor, and completion operations intact.

## Approach

Require the exact active slug, current raw plan SHA-256, explicit reason, dry run, and one canonical BLOCKED roadmap entry before changing the status field. Accept a retry of an already blocked plan without changing bytes. Refuse terminal, archived, ambiguous, stale, or unsupported targets.

## Implementation Steps

1. Add the guarded active block operation to the existing plan tool.
2. Cover preview, apply, retry, refusal, and graph readback with the repository quality gate.
3. Verify the operation against the four already reconciled TradeWing rows through the local source runtime. Keep the installed server and publication state unchanged.

## Verification Checklist

- [x] Exact active transition is guarded and preserves execution and body.
- [x] The graph reflects the transition and refused cases leave bytes unchanged.
- [x] All four TradeWing plans agree with the roadmap after verified application.

## Dependencies

Existing plan identity, guarded mutation, and authoritative roadmap logic.

## Success Criteria

The only plan bytes changed are the authorized status values. The four previously contradictory plans are blocked in the plan graph and excluded from its ready set.

## Testing Strategy

Use isolated repository-shaped cases for stale hashes, unsafe paths, ambiguous rows, explicit roadmap blocking, and repeatable graph readback.

## Risks and Mitigation

Preserve all roadmap bytes and require an existing unique matching blocked row. Dated evidence remains in its existing plans.

## Partial Progress Log

- 2026-11-28: Verified the guarded transition with Cortex quality gate b04fa76797ca (221 tests) and confirmed all four TradeWing results in the canonical plan graph.

## Change History

- 2026-11-28. Created the focused lifecycle plan.
