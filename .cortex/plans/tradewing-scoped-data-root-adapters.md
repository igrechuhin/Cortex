---
title: "TradeWing scoped data root and Swift adapter draft"
component: "project-access"
work_type: security
status: BLOCKED
priority: High
created: 2026-11-14
depends_on: []
execution: agent
---

## Goal

Deliver one reviewable, uncommitted Cortex draft that extends approved project access with an independently approved data root and a bounded, hash-pinned Swift adapter contract, proven using synthetic fixtures only.

## Context

Enrich the existing tradewing-scoped-data-root-adapters plan from reviewed Cortex delivery d896464f29b00cc4303f52f65ad42f1b3f9b07e2; do not create a duplicate. The connection and project-access guides describe the current single-root restriction, incompatible output creation, missing structured progress, and uncertain execution behavior. The user now authorizes staged planning followed by native Cortex implementation and verification of a draft only. A real collector or verified original-profile command is unavailable. The 489 unbound fields and all live TradeWing work are outside this task.

Requested acceptance: retain the existing project MCP binding and 14-tool inventory; independently approve source and data roots without privilege broadening; pin policy and reviewed Swift executable; deny arbitrary commands, arguments, network and writes outside the allowed output; publish small versioned progress/final receipts; prove interruption, durable checkpoint/resume, duplicate and retry behavior and negative security boundaries. No live project or dataset is an input to this work.

## Scope

**in_scope**

- Existing manage_file project_access entrypoint, operator-owned disabled-by-default policy, descriptor-relative containment helpers, and current fixture suite.
- Optional explicit canonical data root with separate exact read and write allowlists; no source-root expansion or symlink shortcut.
- Opt-in reviewed Swift executable adapter with fixed protocol arguments, finite parameters, executable/policy digests and an enforced filesystem/network execution boundary that fails closed when unavailable.
- Bounded structured request, progress, checkpoint and final receipt schemas; durable reservations, explicit bounded resume only after a known ended attempt, and refusal of uncertain execution.
- Synthetic sibling roots, tiny SQLite, compiled harmless Swift stub and adversarial fixture cases; updated future activation/verification/revocation instructions and evidence requirements.

**out_of_scope**

- TradeWing chat or checkout access, profile/migration artifacts, active configuration or permission changes, service restart, MCP installation/reconnection, global or duplicate MCP.
- Real collector or profile-command invention, exporter rewrite, model training, trading, deployment, task-router changes, network use, the 489 fields, commits or pushes.
- Production approvals or activation; documentation specifies these future operator actions without performing them.

## Approach

Preserve the existing one-project attachment and v1 approvals. Reuse the consolidated entrypoint, exact path and SQLite controls and existing reservation patterns. Add an optional explicitly approved data-root object and a distinct Swift adapter job model; absence grants nothing. Data reads and output bases have separate allowlists and cannot overlap or escape through physical aliases.

The adapter receives only fixed protocol flags and a bounded versioned request containing approved finite parameters and sealed synthetic inputs. Use the local macOS deny-by-default execution boundary to block network and writes outside a fresh reserved output; if the boundary or reviewed binary is unavailable, refuse execution. Do not provide a shell, general argv or a fallback unsandboxed launcher. Preserve legacy approved jobs without giving them the new data-root privileges.

Keep control receipts outside the adapter-writable output. Validate structured progress/final/checkpoint files before publication; bind identity to policy, executable, inputs and parameters. A repeated start never executes twice. Explicit resume is bounded and only follows a definitively ended interrupted attempt with a valid durable checkpoint; missing or uncertain worker evidence remains blocked.

## Implementation Steps

1. Stage 1 — extend root/policy/request models and path resolution, preserving old approvals. Add fixture tests for canonical independent roots, exact reads, SQLite root selection, write allowlists and physical-link/traversal rejection. Run the native selected quality gate before proceeding.
2. Stage 2 — implement the fixed Swift adapter boundary and synthetic stub. Pin and validate executable bytes and finite parameters; reserve fresh output; deny network, subprocess escape and outside writes. Keep all active environment/configuration unchanged. Run selected native tests and negative security cases.
3. Stage 3 — implement small versioned progress/final receipts, known interruption, durable checkpoint sealing, explicit bounded resume and duplicate/retry handling. Test fresh-process recovery, invalid/stale checkpoints, digests, unrecognized arguments, uncertain state and failure paths; run the selected native gate.
4. Stage 4 — review the draft end to end; update both guides with exact future chat/config identity verification, separately scoped activation and revocation evidence, unavailable real collector and remaining TradeWing-side work. Run Cortex autofix, fresh full quality and docs gates; retain an uncommitted draft and native task receipts for review.

### Execution checkpoint (2026-11-15)

Stage 1 is PARTIAL: the uncommitted data-root model, policy/physical path checks,
scoped text/SQLite reads and 23 synthetic cases are written in Cortex. Native
quality gate 4822192bbcf6 passed fix-errors, quality, format, Synapse format/lint
and spelling checks, but failed before tests executed. Its Markdown subprocess
was denied access to /Users/igrechuhin/.cache/uv/sdists-v9/.git with
Operation not permitted (os error 1). The new fixture's unused rename result and
missing skip reference were corrected after the gate, without a rerun.

No further gate retry, escalation, cache redirection or disabled check was used
after the denial. All already-started gate jobs reached terminal. Stages 2 and 3
are NOT STARTED; stage 4 final review/full quality/docs verification is blocked.
No Swift executable, sandbox proof, progress/checkpoint/resume implementation or
coverage measurement is claimed. Native task: tradewing-scoped-data-root-adapters;
implementation run: c403d92d6214. Continue only after the required native checks
can run in an authorized environment; preserve the existing uncommitted draft.

## Verification Checklist

- Re-read modified project_access models, policy, paths and dispatch code; search all definitions/callers before changing helpers and verify no change to MCP registration count or default grants.
- Review every subprocess construction and environment: no shell, arbitrary flags, inherited credentials, network, unsandboxed fallback or new legacy data-root privilege.
- Verify no source/data read path overlaps a write base; reject symlink/hardlink components, root aliases, parent traversal and output escapes.
- Re-read protocol and worker state transitions, bounded file readers and atomic publications; prove repeated start and uncertain execution cannot relaunch.
- Inspect synthetic Swift fixture and fresh-process tests; verify all test paths are temporary and no TradeWing source/data is opened.
- Re-read both guides and native handoff/plan state; report exact test results, limitations and future approvals without claiming live activation or complete-profile availability.

## Dependencies

- Existing reviewed project_access implementation and guides in Cortex.
- Local Swift compiler and macOS sandbox facility for the synthetic integration proof; unavailable/denied execution must be reported, never bypassed.
- Native Cortex MCP planning/handoff/quality/docs tools must be healthy. Current work state selects this plan and reports no task locks.
- Production collector, stable working-data seals, installed target-chat revision/config identity and owner approvals remain future external prerequisites, not inputs.

## Success Criteria

- One enriched plan is registered and all four finite draft stages have reviewable code/tests/docs evidence.
- Source checkout binding stays exact; optional data-root reads and writes are independently explicit, physically contained and disabled without approval.
- Only the pinned Swift protocol executable and fixed arguments can use the new job path; network and outside-output writes are denied, including adversarial fixtures.
- Bounded versioned progress/final/checkpoint receipts and explicit resume behavior survive a synthetic interruption; duplicates and uncertain outcomes cannot rerun.
- Selected and fresh full Cortex quality/docs gates pass, or a precise external blocker is reported with no workaround; no live TradeWing action, activation, commit or push occurs.

## Testing Strategy

Use Arrange-Act-Assert tests with session-scoped temporary source/data/operator roots, tiny SQLite snapshots and a compiled synthetic Swift stub. Target at least 95% coverage for new security/protocol branches, with meaningful end-to-end proof rather than mirrored implementation checks. Cover default denial; separate allowlists; alias/traversal/hardlink cases; wrong binary/policy hash; unknown parameters/raw argv; outside writes/network; invalid/oversized structured receipts; checkpoint identity; interrupted known completion and explicit resume across processes; duplicate start/resume and uncertain orphan refusal. Preserve existing project_access regressions. Run gates through native Cortex tools only, focus first and then one fresh unrestricted gate; do not claim global coverage from selected tests.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Wider root exposes unrelated repositories | Keep the original project root, require one disjoint canonical data root and separate exact permissions. |
| Reviewed code can write or communicate outside its contract | Enforce a deny-by-default platform boundary; fail closed without it, never substitute an unrestricted command. |
| Process crash leaves an unknown child | Preserve reservation, report uncertain state and prohibit automatic retry/resume. |
| Policy, executable or input changes invalidate checkpoint | Bind durable identity to verified digests and reject stale evidence. |
| Synthetic proof is mistaken for production readiness | Mark draft and all examples synthetic; require separate owner review and real collector/build/input evidence before activation. |
| Unrelated workspace or live work is disturbed | Restrict source edits and native task state to this existing Cortex plan; stop on conflict or rejection. |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
