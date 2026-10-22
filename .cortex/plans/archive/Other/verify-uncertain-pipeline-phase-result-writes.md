---
title: "Verify uncertain pipeline phase-result writes before retry"
component: pipeline-handoff
work_type: feature
status: DONE
priority: High
created: 2026-10-21
depends_on: []
execution: agent
---

## Goal

Give existing pipeline phase-result publication an exact-request verification and replay contract after an interrupted write or lost response.

## Context

pipeline_handoff_io.py writes history, result and manifest separately (op_write_result, _write_result_payload_file, _append_write_event); history records data keys, not payload identity. experience/resume.py verifies frontier/completed phase names, not exact result content. Existing snapshots, run ownership, experience history and completion_transaction operation identity must be reused where applicable, not proposed as absent. Source: <https://www.anthropic.com/research/effective-harnesses-for-long-running-agents> . Cortex adaptation only.

### Corrective reacceptance pending (2026-10-21)

The original atomic completion `ef56c610bf2d71a83e3701e9` and its observed gate
counts are historical evidence, not current acceptance of the missing-replay
path. Prior no-gaps acceptance is retracted for this guard: an absent target
result could permit replay despite existing conflicting separated configuration
or a wrong manifest session/pipeline. Corrective reacceptance is pending.

The approved normal corrective plan is `guard-missing-phase-result-replay-preconditions` at
`.cortex/plans/guard-missing-phase-result-replay-preconditions.md`. It requires failing-before public-API
no-mutation regressions, minimal precondition validation before MISSING, preserved
initial publication, focused/full governed gates, changed-line coverage, review
and supported acceptance. Typed-refusal implementation remains on hold until
that corrective plan closes. No artificial dependency edge is added.

Archived DONE frontmatter/title/history remain preserved because the supported
lifecycle has no reopen transition; this record does not invent one or
re-register the archived identity. Source acceptance is not shared MCP rollout.

### Corrective source reacceptance (2026-10-21)

The linked `guard-missing-phase-result-replay-preconditions` correction now passes
source acceptance: existing manifest run/pipeline and overlapping canonical typed
config are validated before MISSING can authorize replay. Absent/initialized and
compatible initial publication remain usable; complete/partial evidence,
ownership and exact byte-idempotent replay retain their prior contracts.

Eight independent failing-before public-API regressions observed `missing` for
verification and `ok` for unsafe replay while production SHA-256 remained
`85e8b23ef22b9818280f8527b0b620087222bd29a8815829e7ee0cb9cc7f2e19`.
All 34 new cases and 323 affected focused assertions now pass. Fresh accepted
full gate PID 62902, start 1792595699.856895, finish 1792595817.287338, passed
8,463 tests with zero failures and four skips; global coverage 92.03%, precise
corrective changed executable coverage 9/9 (100%). Formatting, lint, structural,
types, spelling, Markdown, disposable actual public-API smoke, .venv compile/import,
final LSP diagnostics and Docs Phase B passed. Inline Review Gate found no gaps.

Current source inventory fingerprint is
`43af1f96cf80a3a54ba7a4e37d89d525ab82c34107aaf806eb22eb7ed08c58f2`;
governed source fingerprint `e9cfee529df3af49`. Retained before/after JUnit,
full worker/input bindings, coverage and pre-cleanup lifecycle receipts are in
`local://cortex-do-pass-4-result.json` and its linked evidence. This later record
supersedes the preceding pending acceptance statement only for the demonstrated
missing-path correction; original completion operation, observed gate counts,
frontmatter and all prior history remain preserved. No formal reopen or old-plan
completion was performed.

Corrective plan atomic completion `344ddc8f6f92993fac2e8828` archived only the
new corrective identity as DONE. Readback confirmed its one canonical roadmap
row absent, today's progress/context completion entries present and archive/graph
agreement; old archived identity and completion history stayed unchanged.
Source-only, uncommitted and undeployed; shared MCP was not restarted. Typed-refusal
work remains subject to the parent's sequencing release, not this source record.


## Scope

**in_scope**

- Existing pipeline_handoff phase-result publication, bound to current run, pipeline, phase and deterministic caller-payload fingerprint.
- Read-back distinction between exact persisted, missing, and partial/conflicting evidence before a retry.
- Exact replay preserving result timestamp, history cardinality and newer writes; include separated force_fresh/test_timeout config in request identity.

**out_of_scope**

- Re-executing phases or guaranteeing exactly-once external side effects.
- New journal/database, full event sourcing, generic retry loops, automatic sibling takeover or arbitrary execution gateway.

## Approach

Extend existing result/manifest/history evidence with the smallest typed request identity and receipt necessary to verify one phase-result publication. Reuse the current owner binding, checkpoints and resume rules. Return an explicit uncertain/conflicting result rather than inferring success or retrying work.

Keep no commits/pushes/dependencies/permission changes/shared restarts in this planning task. Future implementation uses the normal supported Cortex flow and `# AI:` comments only for non-obvious invariants.

## Implementation Steps

1. Trace pipeline_handoff_io.op_write_result and existing result/manifest/history/experience failure boundaries; define exact caller-payload canonicalization including separated config fields.
2. Add a typed exact-write receipt and verification/replay path to the existing pipeline_handoff surface, reusing current run identity and persistence.
3. Reject differing request identity or partial evidence without overwriting newer results; keep sibling ownership and failed-frontier rules unchanged.
4. Add deterministic interruption/lost-reply/replay cases and document that result publication verification never authorizes rerunning underlying work.

## Verification Checklist

- [ ] Re-read src/cortex/tools/session/pipeline_handoff_io.py, pipeline_handoff_resume.py, src/cortex/experience/resume.py and recorder.py.
- [ ] Search for duplicate phase execution, redundant journal creation or implicit live-owner takeover; preserve existing snapshot/resume behavior.
- [ ] Verify result, manifest, separated config and history agree on one request identity before reporting exact persistence.

## Dependencies

The registration repair is not an implementation prerequisite. Preserve any other dependencies declared in frontmatter. The user explicitly authorized implementation through the existing sequential Cortex do loop; the earlier planning-only hold is superseded. Preserve the declared dependency graph and all safety constraints. Reuse the completed mechanisms named in Context; do not reactivate archived plans.

## Success Criteria

- Lost-response verification classifies exact persisted, missing and partial/conflicting states deterministically.
- Exact replay changes no completion timestamps, history records or newer/different payloads.
- Different requests with identical key sets cannot be confused; force_fresh/test_timeout participate in request matching.
- Existing owner isolation, completed-phase skipping and failed-frontier refusal regressions remain green.

## Testing Strategy

Use isolated roots, injected interruption at each existing publication boundary, and deterministic request fingerprints; target 95% changed-code coverage. Exercise through the existing API plus focused real smoke, with no live models or external phase side effects.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Publication receipt mistaken for work completion | Document and test that only phase-result publication is verified. |
| New identity conflicts with existing runs | Bind to current per-connection run identity and preserve ownership/refusal rules. |
| Partial evidence appears successful | Return explicit uncertainty and require verification, never blind retry. |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
