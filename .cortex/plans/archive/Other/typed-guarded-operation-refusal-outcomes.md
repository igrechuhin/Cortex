---
title: "Typed refusal outcomes for existing guarded operations"
component: guarded-file-operations
work_type: feature
status: DONE
priority: High
created: 2026-10-21
depends_on: []
execution: agent
---

## Goal

Expose stable domain refusal outcomes from the existing guarded document and plan-owner operations so deterministic callers do not parse prose.

## Context

src/cortex/tools/files/document_patch_operations.py already supports exact raw-byte preconditions, dry-run, unique literal repairs, target locks and refusal without mutation. Its error response exposes free-text error and Python error_type; stale hashes and policy refusal can both be ValueError. scripts/set_plan_execution.py already invokes the supported guarded owner API but reduces non-success to generic runtime rejection. No STALE_BASE, POLICY_BLOCKED or DECISION_REQUIRED domain outcomes were found in src or tests. Source: <https://www.anthropic.com/research/code-execution-with-mcp> . Adaptation is a narrow deterministic API contract, not an arbitrary code execution gateway.

## Scope

**in_scope**

- Typed domain codes for actual existing stale-base and policy-refusal branches of guarded Markdown repair and execution-owner correction.
- DECISION_REQUIRED only for a confirmed existing decision boundary; omit it if no such branch exists.
- The existing narrow scripts/API consume backend outcome codes and preserve raw-hash dry-run/apply refusal parity.

**out_of_scope**

- New tools merely wrapping existing tools, generic script runners or arbitrary-code gateways.
- Broad error taxonomy migration, automatic retries, changing permission rules or bypassing noncomplete removal guards.
- Creating a consistency dry-run already covered by existing validation and guarded patch previews.

## Approach

Define the smallest typed result vocabulary at the existing backend refusal boundary, retain useful diagnostic text and mutation evidence, and update narrow callers to branch deterministically. Keep authorization, raw-byte expected hashes, optimistic locking and status rules unchanged.

Keep no commits/pushes/dependencies/permission changes/shared restarts in this planning task. Future implementation uses the normal supported Cortex flow and `# AI:` comments only for non-obvious invariants.

## Implementation Steps

1. Inventory actual refusal/decision branches in document_patch_operations and plan execution-owner correction; freeze a finite code mapping without inventing decision gates.
2. Return typed stable outcomes with mutation_performed and target/revision evidence from those existing backend operations.
3. Update scripts/set_plan_execution.py and affected narrow callers/docs to report the exact domain outcome, never infer retry authority.
4. Prove stale hash, policy denial, dry-run, successful apply, uncertain response and repeat verification semantics through deterministic isolated fixtures.

## Verification Checklist

- [x] Re-read src/cortex/tools/files/document_patch_operations.py, plan execution correction owner and scripts/set_plan_execution.py; use references for affected callers.
- [x] Compare before/after bytes and refusal outcome across dry-run/apply; search for free-text matching in affected narrow callers.
- [x] Keep existing path/symlink/uniqueness/frontmatter/title/status/removal guards and supported operation allowlists unchanged.

## Dependencies

The registration repair is not an implementation prerequisite. Preserve any other dependencies declared in frontmatter. The user explicitly authorized implementation through the existing sequential Cortex do loop; the earlier planning-only hold is superseded. Preserve the declared dependency graph and all safety constraints. Reuse the completed mechanisms named in Context; do not reactivate archived plans.

## Success Criteria

- Real stale preimages return STALE_BASE and real policy refusals return POLICY_BLOCKED without mutation.
- DECISION_REQUIRED exists only if backed by a real decision boundary, otherwise is explicitly excluded.
- Narrow deterministic callers consume typed results, preserve diagnostics and do not retry denied or uncertain mutations blindly.
- Existing previews and apply share refusal semantics; no new permissions, tools or arbitrary execution surface are introduced.

## Testing Strategy

Use isolated workspace fixtures and actual backend calls; assert exact typed refusal, target/revision evidence and byte preservation for stale/policy/invalid path cases. Target 95% changed-code coverage; smoke the existing CLI against a disposable root.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Codes accidentally grant retry authority | Separate outcome reporting from authorization; uncertainty requires read-back. |
| New vocabulary hides existing diagnostics | Retain actionable error text and no-mutation evidence. |
| Scope grows into generic API redesign | Limit changes to the two existing guarded operations and narrow callers. |

