---
title: "Close ExperienceStoreCore SQLite connections deterministically"
component: experience-store
work_type: fix
status: DONE
priority: Blocker
created: 2026-10-21
depends_on: []
execution: agent
---

## Goal

Guarantee deterministic SQLite connection closure in ExperienceStoreCore while preserving existing transaction and initialization behavior, restoring the full governed quality gate.

## Context

The existing registration repair exposed an independently preexisting resource leak. Actual create-only profiling captured 6186 SQLite connects and descriptors 14 to 12390 through usage tracking, pipeline adoption and scan_incomplete_runs. The SAME bounded 20-session history scan on HEAD a56b2b4e and working sources grew descriptors 59 to 145, still 145 after GC. Source owner: src/cortex/experience/store_core.py:82-85; transaction contexts do not close sqlite3.Connection. LSP found 18 references, all in that file and all with self._connect(). Evidence: /tmp/cortex-registration-emfile-attribution.json. The archived unified-experience-store plan is a completed predecessor, not work to reactivate. User explicitly approved this separate narrow correction and subsequent sequential improvement execution.

## Scope

**in_scope**

- Deterministic close of every connection acquired by ExperienceStoreCore on success, body exceptions and initialization/configuration failures.
- Preserve SQLite transaction commit/rollback and existing schema initialization semantics, busy timeout and row factory.
- Regressions proving persisted successful writes, rollback on exceptions, closed handles and bounded repeated history scans; restore fresh full quality/docs gates.

**out_of_scope**

- History/cache/schema redesign, data deletion, live DB/registry cleanup or changes to adoption/TTL/ownership rules.
- Other connection-owning classes without evidence, new dependencies, permissions or system-limit changes.
- Commits, push, deployment, shared service restart, foreign-process interruption or any TradeWing activity.
- Implementing the three improvement features in this pass or adding artificial prerequisite edges to them.

## Approach

At the existing connection factory, retain the sqlite3.Connection transaction context and explicitly close the acquired connection in finally after the transaction exits. Reuse current connection settings and all existing callers. Preserve commit-on-success and rollback-on-exception; closure is resource ownership, not a transaction-policy change. Use the normal Cortex fix/do flow and explanatory # AI: comments only for the non-obvious transaction-versus-close distinction.

## Implementation Steps

1. Reuse captured failing-before evidence; inspect all LSP connection references and existing ExperienceStoreCore tests before editing. Confirm no caller consumes a cursor lazily after leaving the context.
2. Apply the smallest central lifetime correction, with connection close guaranteed after success or exceptions without changing current transaction or initialization behavior.
3. Add permanent isolated regressions for successful persistence plus closed handles, exception rollback plus closed handles, initialization failure, and bounded repeated scan connection closure. Never suppress ResourceWarning or change GC/FD/coverage/timing protections to get green.
4. Exercise a bounded actual scanner/API smoke on synthetic stores. Run the fresh full governed Cortex quality gate and required Docs Phase B with current configured Synapse, preserving foreign state and exact source/test provenance.
5. Review the owned diff inline and finalize this plan through supported lifecycle operations only after its acceptance criteria pass. Do not complete or reclassify unrelated operator plans.

## Verification Checklist

- [ ] Re-read store_core._connect, initialization, write methods and cursor consumers; use LSP references for the return contract change.
- [ ] Inspect nearest experience store/scanner fixtures; verify success, exception and initialization cleanup without mock echoes or source-text assertions.
- [ ] Verify bounded repeated scan handles close deterministically and repeated scans do not accumulate descriptors; use synthetic data only.
- [ ] Record fresh full gate identity/source fingerprint, exact tests/coverage/lint/format/types and Docs Phase B; preserve foreign files and the current Synapse gitlink.

## Dependencies

None. This is the user-approved gate-restoration correction, not a dependency on registration acceptance. The three improvement plans remain dependency-independent and execute sequentially after gate restoration under the latest authorization. No artificial graph edges are introduced.

## Success Criteria

- Successful write transactions remain committed and readable after their connection is closed.
- Exceptional transactions remain rolled back, the original exception propagates, and the connection closes.
- Initialization/configuration failures do not leak acquired handles; existing initialization and database behavior remain intact.
- Repeated bounded history scans close every acquired connection without relying on GC and without growing open descriptors.
- Fresh full governed tests and quality checks pass at unchanged coverage/timing thresholds; Docs Phase B passes. No source-only change is described as deployed.

## Testing Strategy

AAA isolated real SQLite stores and bounded deterministic instrumentation. Retain actual acquired handles to verify closure with SQLite behavior, not mock forwarding. Cover success, exception rollback, initialization failure and repeated scans; target 95% changed-code coverage and preserve the 90% full-source gate. Follow with the full governed gate and an actual bounded API/scanner smoke. Do not reuse a pre-fix or cached green receipt.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Closing changes transaction semantics | Preserve the existing SQLite transaction context, then close in finally; verify commit and rollback through real stores. |
| Cursor consumer outlives its connection | Inspect all references; materialize needed results inside existing context boundaries without unrelated API redesign. |
| False resource-green through GC or suppressed diagnostics | Prove deterministic closed-handle behavior and bounded repeated scans without weakening protections. |
| Unrelated edits are swept into gate/finalize | Keep one editor, snapshot foreign state, selectively preserve the current Synapse gitlink, and finalize only this plan. |
