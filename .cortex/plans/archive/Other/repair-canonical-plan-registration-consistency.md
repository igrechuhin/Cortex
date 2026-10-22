---
title: "Repair canonical plan registration identity and consistency"
component: plan-lifecycle
work_type: fix
status: DONE
priority: Critical
created: 2026-10-21
depends_on: []
execution: operator
---

## Goal

Repair and accept globally canonical plan registration without consuming narrative references, downgrading lifecycle state, or losing concurrent changes.

## Context

The following paragraph records the incident and earlier unaccepted checkpoints; Acceptance Result below is authoritative for the final source.

The October 21 incident replaced a narrative path reference with a PENDING row while a correct BLOCKED registration remained under the custom Deferred Backup Work heading. This is a new root-cause correction, not reactivation of archived repair-existing-plan-registration-update. Sources: <https://www.anthropic.com/research/writing-tools-for-agents> and <https://www.anthropic.com/research/demystifying-evals-for-ai-agents> . These inform Cortex-specific adaptations, not external mandates. Local source repair remains an unaccepted candidate and is not deployed. During the earlier acceptance checkpoint, a read-only probe confirmed a remaining insertion defect in register_helpers.find_insertion_line_for_section: a fenced example directly under Pending, without an intervening heading and without an existing live canonical row, causes a newly rendered registration to be inserted inside the fence. The earlier no-findings review is superseded for this edge. Existing fence regressions placed examples under a separate heading and did not cover this same-section insertion case. No workspace data was mutated by the probe; the four registered Cortex plan rows were separately verified outside such fences. The authorized candidate now selects insertion targets using the existing fence-aware live-line iterator. The original eight permanent backtick/tilde, first/last, with/without live-bullet regressions were extended with eight nested-heading cases. All sixteen now pass under the supported one-worker runner, including unchanged example bytes and exact-repeat byte idempotence. Full-gate acceptance remains blocked as recorded below. Coordinator-verified live cleanup is complete via the existing separate TradeWing planning MCP connection: dry-run then apply on the same raw base removed only original roadmap line 90, the redundant diagnostic PENDING registration (570 bytes removed, no additions). The sole correct BLOCKED row and every other roadmap byte were preserved; both plan files remained byte-identical. Fresh coordinator Cortex read/graph confirms diagnose-whole-capital-strategy-results-and-loss-drivers remains BLOCKED, depends on record-fleet-indicator-repair-and-corpus-acceptance still IN_PROGRESS, and is not ready. Roadmap SHA256 changed from a0b102f3d1636e6fbd7db46367b4eb7950c7948bfedf52f52a2bdba2eb9f227a to b7d8de901b11f83cc4ee6bab6fc5c6688c72aad00190b1e6525aefe1c4f31a9b. No re-registration, status mutation, narrative restoration, source/data change, shared restart, publication or protected repair-session message occurred. This Cortex session performed no TradeWing action; source rollout and full-gate acceptance remain pending. Earlier published MCP smoke in a disposable workspace passed, and changed-module LSP/compile/import and structural checks passed. The earlier no-findings review was superseded by the same-section fenced insertion defect, now corrected in the unaccepted candidate. Final one-worker isolation passed 5 of 5 assertions with no ENFILE; the governed command still failed unchanged whole-source coverage (36.82 versus required 90 percent). The two-worker focused checkpoints were registration 141 passed/2 ENFILE failures, completion 76 passed/1 ENFILE failure, and roadmap/graph 250 passed/1 skipped; fail-fast left the broader selection incomplete. Earlier timing failure showed no demonstrated isolated regression against HEAD; measured timing modules and test were byte-identical. Synapse preflight confirmed a clean physical Cortex checkout on main tracking origin/main. Supported fetch and fast-forward synchronization verified remote, checkout, and the already-staged project index gitlink at 5465812ed47fde7628f285ff7943d3c390fe495a; no additional staging or source update was needed. The prior submodule-hygiene blocker is resolved. Synapse no longer blocks verification; the current acceptance blocker is recorded in Verification Checkpoint below. No full-green or rollout claim is made.

## Acceptance Result

- Accepted at source/testing level after the approved ExperienceStoreCore lifetime correction restored the full governed gate. Earlier blocked checkpoints below are historical and superseded.
- Final source fingerprint: `3702cb0f93b8441cc4ec6e5a845147a24626ea4db583a1608b6725fa4f254e4a`; source and test hashes remained unchanged across the acceptance gate.
- Fresh worker 11869: 8283 passed, zero failed, four skipped, 91.9% global coverage. All quality, lint, formatting, types, spelling and Markdown checks passed. Receipt: `/tmp/cortex-registration-acceptance-worker.json`.
- Registration changed executable lines: 189 of 198 covered, 95.45%, without rounding the requirement or weakening any threshold. Receipt: `/tmp/cortex-registration-final-full-coverage.json`.
- Exclusive preservation proof: all 16 fenced cases, including nested Pending headings, plus owner-policy refusal passed. The refusal leaves both canonical roadmap and plan bytes unchanged. Full suite also passes lifecycle precedence, stale preimage, failed-write rollback and noncomplete-removal guard cases. Focused receipt: `/tmp/cortex-registration-acceptance-focused.xml`.
- Inline owned-source review is `no_gaps`, verified through the supported fix pipeline and its actual review-result file. Original production hashes are unchanged from the full inline review; the additional policy regression was read and verified before acceptance.
- Required Cortex Docs gate passed. Coordinator-completed TradeWing duplicate cleanup remains intact; no TradeWing action was performed here.
- This accepts source only. No commit, push, deployment or shared MCP restart occurred; it does not assert that the existing shared server has loaded this source.

## Historical Verification Checkpoint

- Final owned source/diff review is complete. Candidate fingerprint: `62545aad471834928af89b8ca0bfc31a956c648d32ea433dd558896105238cff`. Source is not deployed or accepted.
- Exclusive permanent fenced matrix: 16 passed, covering both original eight cases and eight with a recognized Pending heading inside the example. Backtick/tilde, first/last, example bytes and exact-repeat bytes are verified. Receipt: `/tmp/cortex-registration-fence-after.xml`. The scoped command still exits nonzero at unchanged whole-source coverage, 34.39% versus 90%; this is not a full-gate pass.
- Final governed non-test worker passed quality/structural limits, lint, formatting, Synapse formatting/lint, spelling, types and complete Markdown scope. Receipt: `/tmp/cortex-registration-final-static-checks.json`. Required Cortex Docs Phase B passed and is rechecked after this evidence update.
- Last full governed run `5738f00f2f71` completed 2026-10-21T10:47:23Z–2026-10-21T10:50:26Z: 8221 passed, 48 failed, 4 skipped, coverage 91.8%. Two test failures and four quality violations were owned structural issues, now corrected. The 46 EMFILE test failures are resource failures; this full receipt predates the final source fingerprint and does not establish final acceptance.
- **Exact acceptance blocker:** unchanged `src/cortex/experience/store_core.py:82-85` returns SQLite connections whose surrounding transaction contexts do not deterministically close them. Usage tracking (`usage_tracker.py:139`) queries pipeline adoption (`pipeline_handoff_session.py:171-218`), which invokes `scan_incomplete_runs` (`resume.py:75-77`); its history loops repeatedly open connections. Actual create-only profiling captured 6186 SQLite connect calls and descriptors 14 → 12390.
- The SAME bounded synthetic history scan with 20 sessions reproduced 59 → 145 descriptors, still 145 after GC, identically on HEAD `a56b2b4e` and the working-source fixture. All five resource-path source files are byte-identical to HEAD. This establishes an independently existing blocker, not a registration regression. Receipts: `/tmp/cortex-registration-bounded-scan-head.xml`, `/tmp/cortex-registration-bounded-scan-working.xml`, and `/tmp/cortex-registration-owner-fd-83599.json`.
- **Minimum separate approval scope:** deterministic connection close in ExperienceStoreCore preserving current commit/rollback and migration behavior; bounded repeated-scan regression; then a fresh full governed gate. No history/cache redesign, live DB or registry mutation, limits changes, foreign-process interruption, or shared restart. Do not repeat the broad suite toward descriptor exhaustion before this is resolved.
- The three improvement plans remain PENDING with no artificial repair dependency; this grants no feature implementation authority. Coordinator-completed TradeWing cleanup remains intact. No rollout is authorized.

## Scope

**in_scope**

- Registration-shaped global identity, existing-row location preservation, and correct insertion boundaries.
- Coherent roadmap/frontmatter lifecycle and dependency state; original-preimage optimistic locking and explicit failed-write outcomes.
- Deterministic incident, repeat-register, stale-base, concurrent-edit, partial-failure, and noncomplete-removal-guard regression proof.
- Fresh full governed verification and operator acceptance of the local source repair, preserving the authorized Synapse gitlink and all foreign changes.
- Consistent canonical final-label identity in registration, removal guard, bounded archive cleanup and session discovery, preserving historical/fenced narrative and typographic separators.

**out_of_scope**

- TradeWing source/session/data repair, deployment, shared service restart, or restoring overwritten narrative history.
- New eval platform, new journal/event store, commits/pushes or permission changes.

## Approach

Reuse the established roadmap parser, artifact graph, status metadata and target-lock/atomic-replace discipline. Registration identity spans all roadmap headings; selected section only places a missing registration. Preserve lifecycle rules and fail closed on duplicate identities or stale preimages. The registration source correction is accepted after the approved ExperienceStoreCore fix restored the full governed gate. The final source passed this plan's regression and coverage requirements; deployment and shared MCP restart remain out of scope and were not performed.

Keep no commits/pushes/dependencies/permission changes/shared restarts in this planning task. Future implementation uses the normal supported Cortex flow and `# AI:` comments only for non-obvious invariants.

## Implementation Steps

1. Confirm the incident-shaped fixture with narrative in pending and canonical BLOCKED row under Deferred Backup Work; preserve unrelated history and canonical position.
2. Complete the remaining fence-aware insertion correction before acceptance: add a deterministic fixture with a fenced example directly under Pending and no intervening heading, then ensure new rows are inserted outside the fence. Cover backtick and tilde fences, first/last insertion, unchanged example bytes, and byte-identical repeat registration. Retain the identity/status and original-preimage concurrency repairs and their failure-preservation proof.
3. Run focused registration/roadmap/graph/guard tests and an isolated real registration smoke; record exact exercised evidence.
4. Run the normal fresh Cortex quality gate with the verified current Synapse checkout/index. Preserve foreign changes and do not weaken submodule hygiene, coverage, timing or permission rules.
5. Record acceptance through the supported plan lifecycle only after all required checks pass; rollout remains separately authorized.

## Verification Checklist

- [x] Re-read registration helper, persistence, lifecycle status owner and caller changes; inspect fixtures for the actual unknown-section incident.
- [x] Check exact replay bytes, one canonical row, unchanged narrative/history, established IN_PROGRESS/READY with unmet-dependency regressions, status/graph agreement under existing rules and original merge-preimage conflicts.
- [x] Confirm no protected direct writes, guard removal, foreign staging or shared restart; record full-gate blocked versus passed accurately.
- [x] Do not mark DONE before the true full gate, governed format/lint checks, and required acceptance pass; isolated assertion passes are not a substitute. Coordinator-completed TradeWing duplicate cleanup is recorded from its existing connection; this Cortex session performed no TradeWing action.

## Dependencies

No unmet code-plan prerequisite remains. Authorized Synapse synchronization and the completed separate connection-lifetime fix restored fresh verification. The final full gate and changed-code coverage requirement pass; no artificial dependency edge was added. Rollout and any shared restart remain separately unauthorized.

## Success Criteria

- Global re-registration updates exactly one canonical row in place and never treats prose as identity. Missing-row insertion stays outside backtick/tilde fences, preserves the example bytes, and is byte-idempotent on an exact repeat.
- Default PENDING replay preserves dependency BLOCKED and established lifecycle; established IN_PROGRESS/READY retain prior precedence even with unmet dependencies, and supported explicit transitions stay coherent.
- Stale and failed writes cannot silently overwrite competing content or report false success.
- Focused regressions and real smoke pass; fresh full quality gate passes with the verified current Synapse checkout/index and preserved foreign changes.

## Testing Strategy

AAA isolated filesystem fixtures and deterministic interleavings; target 95% changed-code coverage when the full gate can run. Do not substitute a cached or standalone receipt for the full gate. Keep removal policy and existing completion/status regressions.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Unknown headings hide canonical rows | Match registration identity globally before resolving insertion section. |
| Upstream or foreign state changes during verification | Re-read the clean submodule and configured upstream; preserve unrelated state and require a fresh gate without rollback or unrelated staging. |
| Crash or partial write | Report actual persistence outcome; do not claim source-only changes deployed or general exactly-once semantics. |

## Change History

- 2026-10-21T10:44:00Z: corrected the remaining fenced insertion candidate, added eight permanent regressions, resolved the Synapse prerequisite through its supported flow, and resumed IN_PROGRESS verification. No acceptance or rollout claimed.
