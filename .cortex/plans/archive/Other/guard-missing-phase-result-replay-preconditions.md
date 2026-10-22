---
title: "Guard missing phase-result replay preconditions"
component: pipeline-handoff
work_type: fix
status: DONE
priority: Blocker
created: 2026-10-21
depends_on: []
execution: agent
---

## Goal

Refuse missing phase-result replay when existing manifest identity or separated
configuration conflicts, without changing persisted evidence or weakening valid
initial publication.

## Context

This finite corrective plan follows
`archive/Other/verify-uncertain-pipeline-phase-result-writes.md`, completed by
operation `ef56c610bf2d71a83e3701e9`. Its historical completion and real gate counts
remain preserved, but its prior no-gaps acceptance is retracted for this newly
confirmed missing-path guard. Corrective reacceptance is pending. The supported
lifecycle has no archived-plan reopen operation; this linked corrective plan does
not recreate or re-register the archived identity.

`src/cortex/tools/session/pipeline_handoff_publication.py` returns MISSING at
lines 93-96 before checking existing manifest binding and configuration at
lines 149-162. A missing code result can therefore authorize replay over a review
phase's newer separated configuration, or despite a wrong manifest session or
pipeline. Evidence: `local://cortex-do-pass-2-post-completion-finding.json`.

This is the existing approved uncertain-result correction, not a new feature.
The user authorized the corrective-plan fallback and requires this acceptance
before typed-refusal implementation, without adding artificial dependency edges.
Source adaptation: <https://www.anthropic.com/research/effective-harnesses-for-long-running-agents>.
The article motivates verified retry boundaries; it does not prescribe this fix.

## Scope

**in_scope**

- Existing missing-evidence verification/replay guards and canonical comparisons.
- Public-API no-mutation regressions, valid initial-publication cases, and source smoke.
- Focused/full governed checks, changed-line coverage, review and corrective records.

**out_of_scope**

- New retry loops, phase execution, journals, schemas or permission/lifecycle APIs.
- Typed-refusal feature implementation, shared rollout/restart or live data cleanup.
- Changing the archived plan identity/frontmatter or any unrelated dependency edge.

## Approach

Reuse the existing publication lock, passive ownership checks, receipt/status
models and canonical JSON comparisons. Check existing manifest identity and
conflicting overlapping separated configuration before MISSING can authorize
publication. Preserve legitimate absent or initialized publication and safe
initial configuration; do not require an already-persisted target receipt.
Keep complete/partial-evidence behavior, exact replay and ownership guards intact.

## Implementation Steps

1. Add deterministic real public-API regressions BEFORE production changes for a
   missing target result with conflicting existing separated config, wrong
   manifest session_id and wrong pipeline. Scope each fixture mutation precisely
   and assert refusal plus unchanged bytes/mtime for verify and replay.
2. Apply the minimal missing-path precondition correction. Cover valid initial
   publication and compatible configuration without weakening existing guards.
3. Run affected governed tests with explicit receipts, source API smoke,
   compile/import checks, fresh full Cortex gate and changed-line coverage.
4. Review the owned diff; record actual corrective reacceptance linked to the
   preserved archive through supported APIs, run Docs Phase B and atomically
   complete this corrective plan only after all acceptance requirements pass.

## Verification Checklist

- [x] Step 1: failing-before JUnit and unchanged production SHA prove the actual
  missing-path bypass in the public pipeline_handoff API.
- [x] Step 2: inspect publication verification and adjacent interruption cases;
  refuse wrong run/pipeline and stale config without modifying evidence.
- [x] Step 3: exact full-gate PID/start/input fingerprint, test counts, coverage,
  formatting, lint, structural, type, Markdown and smoke receipts are retained.
- [x] Step 4: historical archive identity is preserved, corrective acceptance is
  explicit, one canonical corrective row is removed only at accepted completion,
  and progress/context/archive/graph readback agrees.

## Dependencies

`depends_on: []`. The earlier phase-result implementation is already present and
is linked as a predecessor, not a new lifecycle gate. Typed-refusal sequencing is
an explicit user hold until this correction and the accepted context work pass;
its declared dependency list must remain unchanged. No external rollout is needed
for source verification, and source acceptance is not shared MCP deployment.

## Success Criteria

All three conflict scenarios refuse both verify/replay with unchanged persisted
bytes and timestamps; missing/initial publication remains usable and exact retry
remains byte-idempotent. Existing ownership, partial-evidence and configuration
contracts remain intact. Fresh full governed checks and Docs Phase B pass; global
coverage remains at least 90% and changed executable coverage at least 95%.
Corrective acceptance and atomic Finalize are verified, not merely reported.

## Testing Strategy

Use isolated real public-API fixtures and existing governed Synapse runner at
bounded concurrency. Keep failing-before/passing-after tests for each missing-path
conflict, plus positive initial/config cases and existing guard suites. Assert
actual bytes/mtime/history preservation, not mocked forwarding or source strings.
Exercise source API in a disposable root. Save exact full gate/source and
changed-line coverage receipts; preserve every existing threshold and protection.

## Risks and Mitigation

| Risk | Mitigation |
|---|---|
| Reject legitimate first publication | Cover absent and initialized manifests and safe initial config |
| Miss conflicting current configuration | Compare overlapping existing keys with canonical typed digests |
| Rewrite partial or foreign evidence | Reuse fail-closed locks/ownership and assert no mutation |
| Hide retracted historical acceptance | Preserve archive/history and append explicit corrective evidence |
| Misrepresent deployment | State source-only and retain shared-restart boundary |

## Corrective Source Acceptance (2026-10-21)

Eight real public-API regressions failed before production changed; retained JUnit
and unchanged SHA-256 prove the missing-path bypass. The minimal correction now
validates existing manifest binding and overlapping typed config before MISSING;
34 new cases cover refusal/no-mutation and valid initial/exact replay behavior.
323 affected focused assertions pass (subset coverage wrapper retains global90
and correctly rejects subset39.09%). Fresh accepted full gate PID62902,
start1792595699.856895/end1792595817.287338: 8463 passed, zero failed, four skipped;
global92.03%, precise corrective executable9/9(100%). All structural/format/lint/
type/spelling/Markdown checks, final-byte .venv compile/import, LSP diagnostics,
disposable actual public-API smoke, Docs Phase B and inline no_gaps review pass.

The prior archived body has a guarded append-only source reacceptance record;
original historical completion and factual gate counts remain intact. All51
nonowned baseline artifacts and the prior shared documentation content are
preserved. Source-only/uncommitted/undeployed; no shared MCP restart, formal
archived-plan reopening, typed-refusal implementation or dependency changes.
Atomic corrective completion `344ddc8f6f92993fac2e8828` archived only this identity;
roadmap/progress/context/archive/graph readback verified the accepted outcome.
Evidence: `local://cortex-do-pass-4-result.json` and linked retained receipts.

