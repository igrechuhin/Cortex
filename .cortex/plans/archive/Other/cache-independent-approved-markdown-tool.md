---
title: "Cache-independent approved Markdown tool"
component: "quality-gate"
work_type: fix
status: DONE
priority: High
created: 2026-11-15
depends_on: []
execution: agent
---

## Goal

Make the official Cortex Markdown gate use an approved locked installed rumdl without shared uv-cache access, preserving lint rules, owned scope and genuine failure behavior.

## Context

Ilya approved scope C: “Надо сделать чтобы такой проблемы не было”. This is a first-party production resolver fix, not permission to retry denied shared-cache access, change sandbox permissions, install binaries, redirect caches or run ad hoc tests.

Use the same isolated worktree /private/tmp/cortex-ab-session-quality-20261115 and the same source writer. The separate A/B plan is project-access-bootstrap-owned-quality-runs; its code and authored tests are stabilized, including real MCP startup after fixing an import cycle, but unit verification is pending. Preserve its snapshot at /tmp/cortex-ab-review.patch and /tmp/cortex-ab-stable-before-c-tree. Do not restart A/B or touch the original dirty checkout. Track C source delta and check status separately.

Baseline resolver pre_commit_rumdl_resolve prefers uv run rumdl whenever uv exists. Installed interpreter/project tool routes are behind uv absence; the worker does not retry nonzero lint output. uv.lock pins rumdl 0.1.45, while package declarations allow newer versions. Read-only inspection found installed rumdl 0.1.45 metadata and a matching RECORD SHA-256 and size for its native executable. Its Python module wrapper searches a development target/release path, so it must not become an unverified fallback.

### Verification checkpoint (2026-11-15)

The final official C-selected gate is green: zero errors/warnings, all eight
checks and Markdown success. The recorded detailed same-selector result is
45 passed, 0 failed; the final compact success differs only by a spelling
vocabulary comment. Scope is selected_tests_only, coverage is null and
full_suite_validated is false. Exact selector:
test_pre_commit_rumdl_resolve or test_pre_commit_worker_resolve_rumdl or
test_pre_commit_worker_md_collect or test_poll_phase_a_markdown_merge.

The approved installed 0.1.45 native executable passed bounded METADATA/RECORD
identity validation; genuine lint errors are returned without retry. No denied
uv-cache read, environment cache redirection, installation or permission change
was used. A/B remains separately BLOCKED at 121/124 with three permission errors;
C's success does not certify that behavior. Code remains uncommitted for review.

## Scope

**in_scope**

- Approved installed project/package tool selection with explicit version and installed-file provenance.
- A cache-independent native rumdl route in the official check and fix entry points, without requiring execution of an extra or disallowed interpreter.
- Clear fail-closed no-approved-tool/unusable-tool errors.
- Synthetic regressions for unavailable uv/global cache, real lint findings from the approved installed tool, absence/mismatch/corruption and no rerun after genuine lint failure.
- Native Cortex verification after fixed source is actually loaded and route provenance confirms no forbidden cache attempt; separate C and A/B receipts and review patches.

**out_of_scope**

- Any retry of /Users/igrechuhin/.cache/uv/sdists-v9/.git access, cache relocation, sandbox/auth changes or environment tricks.
- Unapproved binary installation/download, global PATH tool adoption, arbitrary command dispatch, skipping required checks or substituting tests.
- TradeWing files/data/jobs and the unrelated adapter draft; commits, publishing, release, reset or push.

## Approach

Inspect and reuse supported installed-tool and packaging paths. Select only an explicitly approved locked tool from the attached project or the Cortex package environment; verify dependency provenance rather than trusting a global name or launching a second interpreter to discover it. Keep the approved version synchronized with the Cortex lock/package policy and prove installed executable identity through its recorded metadata.

The official resolver must construct the same check/fix flags, configuration and owned Markdown file list as before, while avoiding uv-cache dependence. If no usable approved route exists, return a bounded blocking error. A launched linter's nonzero exit is a real gate result and must be returned immediately; never reroute or rerun it as a fallback.

## Implementation Steps

1. Complete native planning/readback/registration for this separate C plan after A/B stabilization, and preserve the A/B pre-C snapshot.
2. Implement approved installed-tool provenance and cache-independent official resolver/worker paths, including package-distribution behavior and interpreter restrictions.
3. Add synthetic tests covering approved installed lint with uv/global cache unavailable, a genuine lint violation, no tool, version/record mismatch and no fallback after nonzero lint output; update relevant resolver expectations.
4. Reopen the native development client on the real fixed source, confirm route/provenance without touching denied cache, then use native autofix/quality/docs entry points. First verify C regressions, then the relevant A/B regressions as a separate selected gate. Record exact counts, scope and remaining blockers; keep everything reviewable and uncommitted.

## Verification Checklist

- Re-read uv.lock, declared dependencies, installed metadata/RECORD and supported packaging paths; no executing a candidate during provenance inspection.
- Search official Markdown command construction for uv/global fallback, unapproved PATH candidates and extra interpreter requirements.
- Confirm check/fix argument parity, same .rumdl configuration, same owned path collector and unchanged lint error interpretation.
- Confirm a genuine launched lint failure is returned once, with no alternate tool or swallowed error.
- Re-read no-tool/mismatch errors and metadata bounds; no implicit installation, cache read or permission change.
- Load fixed code in the native client before any gate; record C and A/B selected receipts independently and verify original checkout preservation manifest.

## Dependencies

- Same isolated reviewed-baseline worktree and pinned local Synapse as the A/B task.
- Stabilized A/B code is already present; its acceptance does not need to be marked complete before C restores the gate.
- Existing approved rumdl 0.1.45 installed package and recorded native executable; no new binary is authorized.
- Healthy native Cortex entry points. A missing approved route remains a legitimate blocker, never authority for a detour.

## Success Criteria

- Official Markdown check/fix can use a proven approved installed tool without any shared uv-cache dependency or extra interpreter probe.
- No-tool, provenance mismatch and execution-unavailable cases fail closed with explicit reasons.
- Genuine lint errors, rules, configuration, owned scope and mandatory checks remain intact; no silent skip or retry after lint failure.
- Synthetic regression proof runs only through an authorized native Cortex gate after fixed route confirmation, or precise blockers/counts are reported.
- C has its own plan, source delta and verification status; A/B outcomes remain separately recorded and original dirty checkout is unchanged.

## Testing Strategy

Use temporary metadata/tool fixtures and the already-approved installed native linter under the official gate. Simulate uv/global-cache unavailability without opening that cache. Include a real invalid Markdown fixture and assert its nonzero result is surfaced with no second tool invocation. Cover absent tool, mismatched pinned version, corrupted/absent installed record, blocked interpreter and unchanged check/fix flags/scope. Run selected C regressions and then selected A/B regressions through run_quality_gate with write_task configuration; do not claim full-suite coverage from selected tests. No standalone pytest/linter/compiler test commands.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| A global or tampered executable is selected | Restrict environment/package provenance and approved locked version; verify installed record identity. |
| A denied route is hidden by retry | Resolve the approved cache-independent route before execution; return genuine lint results once. |
| Package installation lacks source lockfile | Carry a minimal explicit package tool pin/provenance contract compatible with packaging and test lock consistency. |
| A particular interpreter is disallowed | Inspect provenance in the running server and use the approved native executable without probing another interpreter. |
| C blends with A/B | Preserve pre-C snapshot and publish separate delta/status; same writer, sequential phases. |
| Official verification remains unavailable | Keep draft and record exact native error/counts; no alternate tests or permission changes. |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
