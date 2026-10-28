---
title: "Repair false-green spelling subprocess verdicts"
component: quality
work_type: investigation
status: DONE
priority: Blocker
created: 2026-10-25
depends_on: []
execution: agent
---

## Goal

Make the spelling stage report successful cspell execution only when the real checker completed successfully, preserving operational failures and producing a bounded, actionable gate result.

## Context

During verification of the canonical-read test-helper typing correction, Cortex returned a fresh green quality gate although Synapse check_spelling.py can mask npm failures. Lines 157-172 replace any nonzero return code with the count of output lines whose first colon-delimited field ends in .py; operational npm errors produce zero. The exact npx -y cspell --files-only --no-progress invocation, run with an isolated writable cache over the same 1524 paths, exited 1 because --files-only is unsupported. A compatible direct invocation without that presentation flag exited 1 with 1773 issues in 444 files. These are observed results, not a claim that every issue is a genuine misspelling.

The correction gate first had one unrelated E2E timeout: tests/e2e/test_public_workflow_smoke.py::test_quality_gate_reports_real_success_and_failure exceeded its 180-second deadline while npm logged ECONNRESET and a 241.464-second registry request. Nested spelling subprocesses have no timeout; the worker's 60-second test timeout applies to pytest, not prior spelling. Root-owned npm cache entries also caused EACCES. The unchanged-tree fresh retry returned green, but this does not prove cspell ran.

Evidence: .cortex/synapse/scripts/python/check_spelling.py:54-61,148-172,229-230; src/cortex/tools/execution/pre_commit_synapse.py; src/cortex/tools/execution/pre_commit_pipeline.py; npm fixture log ~/.npm/_logs/2026-10-25T09_15_30_380Z-debug-0.log; OMP tool receipts artifact://39 and artifact://40 in the originating session. Reports filed through xd://report_issue. Original feature commit 813d42eb is pushed. Two suppression-free TypedDict/Unpack test-helper edits remain uncommitted; focused Pyright, 41 canonical regressions, and real-worktree helper smoke pass.

## Scope

**in_scope**

- Trace the exact CLI, script return-code conversion, caller propagation, tool resolution, and subprocess lifetime.
- Replace incompatible presentation flags and preserve checker startup, option, permission, transport, timeout, and spelling failures.
- Provide deterministic toolchain preflight and bounded failure behavior without silently skipping a critical check.
- Add isolated regression proof for false-green error paths and exercise the actual public gate path.

**out_of_scope**

- Bulk fixing or blanket allowlisting the 1773 repository spelling findings.
- Weakening spelling policy, tests, exit codes, or critical-check requirements.
- sudo, modifying user-owned npm configuration or caches, service restarts, stopping existing jobs, or TradeWing changes.
- Canonical-read production changes, rewriting pushed history, or automatically committing the existing correction.

## Approach

First retain the failing CLI and return-code evidence. Establish a documented supported checker invocation and distinguish checker findings from infrastructure failures without converting nonzero status to success. Apply the narrowest shared script/caller correction and a bounded subprocess contract. Keep dictionary adjudication separate: surfacing an existing spelling failure is correct fail-closed behavior, not a reason to suppress it.

## Implementation Steps

1. Diagnose tool/version resolution and exit-status/lifetime propagation from cspell through the Synapse script to the public quality gate; capture supported CLI and operational-failure receipts.
2. Implement a supported invocation and fail-closed, bounded subprocess result handling at the shared responsible layer; preserve diagnostic text and file findings.
3. Add deterministic operational-failure regressions and run actual checker/script/public-gate smoke; document the invocation and any remaining real spelling backlog separately.

## Verification Checklist

- Step 1: Read the named script and every caller; verify actual selected cspell version, flags, config, and process timeout ownership. No production writes before diagnosis.
- Step 2: Inspect every return-code branch; unknown-option, executable missing, EACCES, ECONNRESET, and timeout results must stay failures. No error-count-derived false success.
- Step 3: Prove supported success, spelling findings, operational failure, and bounded termination through isolated tests plus a real command and public gate result. Report real remaining findings rather than calling a failing full spelling scan green.

## Dependencies

- No unfinished plan dependency. Requires an explicitly authorized separate maintenance pass for Synapse/shared gate changes.
- A working, documented cspell toolchain is an execution prerequisite; do not assume local shell environment changes reach an already-running MCP server.

## Success Criteria

- Every observed checker operational failure produces a nonzero script result and a failed public spelling stage with the actual diagnostic.
- Supported cspell invocation completes and returns the original spelling verdict; invalid flags cannot produce success.
- Spelling subprocess completion or failure is bounded and leaves no orphan created by the verification run.
- Regression evidence covers startup, CLI, permission, transport, timeout, findings, and success; no spelling backlog is silently waived.

## Testing Strategy

Use AAA-style isolated tests for consumer-visible error propagation and bounded lifecycle behavior, including nonzero errors with no .py-prefixed output. Target at least 95% changed-code coverage. Add one real installed-tool success/failure smoke and one public gate-path smoke without external registry dependency; preserve exact commands, versions, exit codes, and final verdicts. Do not weaken the existing E2E assertions or merely raise its timeout.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Existing spelling findings become newly visible | Preserve the failure and inventory findings for a separately scoped adjudication pass. |
| Unpinned npx changes CLI or depends on network | Use an explicit supported tool contract and deterministic preflight; fail clearly when unavailable. |
| Timeout leaves detached child processes | Establish timeout ownership and verify child lifecycle without interrupting foreign jobs. |
| Shared Synapse changes affect other projects | Scope the correction, run isolated cross-language script regressions, and do not restart shared services. |
