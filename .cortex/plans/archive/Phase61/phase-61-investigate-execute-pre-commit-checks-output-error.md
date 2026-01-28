## Phase 61: Investigate `execute_pre_commit_checks` MCP Output Handling Failure

### Problem Statement

The `execute_pre_commit_checks` Cortex MCP tool is invoked during the commit pipeline to run fix-errors, formatting, type checking, quality checks, and tests.  
In this session, calls to `execute_pre_commit_checks` reported that large output was written to an `agent-tools/*.txt` file, but attempts to read that file from the Cursor environment failed with `File not found` and "content exceeds maximum" errors.  
As a result, the structured JSON result for `execute_pre_commit_checks` was not available to the agent, blocking verification of fix-errors/type/quality/test results and preventing safe continuation of the commit workflow.

### Impact

- Commit pipeline cannot safely proceed because:
  - The agent cannot parse `results.fix_errors`, `results.format`, `results.type_check`, `results.quality`, or `results.tests` from the MCP response.
  - Zero-errors / zero-violations guarantees required by the commit workflow cannot be validated.
  - Step 0 (Fix Errors) and subsequent Steps 1–4 that depend on `execute_pre_commit_checks` lack trustworthy status.
- This is a **CRITICAL** MCP tooling issue for Cortex, because commit workflows depend on this tool as the single source of truth for pre-commit checks.

### Goals

1. Restore reliable, structured `execute_pre_commit_checks` responses in Cursor so agents can:
   - Read full JSON results directly from the MCP response.
   - Avoid reliance on large-output spill files that may be inaccessible in the IDE sandbox.
2. Ensure that large textual logs (if needed) are optional extras, not the only source of truth.
3. Add regression tests and stability checks under `src/cortex/core/mcp_stability.py` to cover this failure mode.

### Investigation Tasks

1. **Reproduce the Failure**
   - Run `execute_pre_commit_checks` with typical commit-pipeline parameters from Cursor.
   - Capture:
     - Raw MCP response shape seen by `CallMcpTool`.
     - Any stderr/stdout logging mentioning `agent-tools/*.txt`.
   - Confirm under what conditions (output size, error vs success, specific checks list) the spill-to-file behavior is triggered.

2. **Trace Output Handling Pipeline**
   - Inspect MCP transport / integration layer between Cursor and Cortex:
     - How large responses are chunked or truncated.
     - When and where "large output written to: agent-tools/…" is emitted.
   - Verify whether:
     - The structured JSON result is still present in the MCP payload but dropped/truncated by the integration.
     - Or only the path to the spill file is returned to the agent.

3. **Validate `agent-tools` Persistence and Access**
   - Confirm actual on-disk location of `agent-tools/*.txt` files for this workspace.
   - Verify that the Cursor `Read` tool can access that path consistently (no race conditions / cleanup between calls).
   - If files are ephemeral:
     - Document lifecycle and retention policy.
     - Decide whether this mechanism is compatible with Cortex commit workflow requirements.

4. **Design and Implement a Robust Result Channel**

   - **Preferred approach**: Ensure `execute_pre_commit_checks` always returns a compact, structured JSON result in the MCP payload, independent of any large human-readable logs.
   - If logs must be spilled to disk:
     - Keep logs and JSON strictly separated.
     - Guarantee that JSON remains in-band in the MCP response.
   - Update `src/cortex/tools/pre_commit_tools.py` and any wrappers to:
     - Enforce a clear JSON schema for results.
     - Avoid logging massive payloads directly into the MCP response body.

5. **Harden `mcp_stability` and Error Handling**
   - Extend `src/cortex/core/mcp_stability.py` to:
     - Detect responses that only contain "large output written to…" text without JSON.
     - Classify such cases as CRITICAL tool failures for commit workflows.
     - Emit clear, structured diagnostics that can be surfaced to users and recorded in the memory bank.
   - Add explicit stability tests for:
     - Large-output scenarios.
     - Mixed JSON + log output.
     - Timeouts and partial responses.

6. **Update Documentation and Commit Workflow**
   - Update commit workflow docs to:
     - Document the expected `execute_pre_commit_checks` response shape.
     - Clarify how large logs are handled.
   - Add guidance for agents on:
     - How to detect and respond to this specific failure mode.
     - When to treat it as CRITICAL vs recoverable.

### Success Criteria

- `execute_pre_commit_checks` always returns a usable, structured JSON result in Cursor, even when large logs are produced.
- The commit pipeline can:
  - Parse `results.fix_errors`, `results.format`, `results.type_check`, `results.quality`, and `results.tests` reliably.
  - Enforce ZERO-errors tolerance with explicit counts and statuses.
- Large human-readable logs (if any) are:
  - Optional, not required for correctness.
  - Accessible via stable paths and within Cursor sandbox limits.
- New tests in the MCP stability suite cover:
  - Large-output scenarios.
  - JSON + log coexistence.
  - Error classification and reporting.

### Priority and Status

- **Priority**: 🔴 **FIX-ASAP BLOCKER** – commit pipeline cannot safely proceed without resolving this.
- **Status**: ✅ COMPLETE (2026-01-28) – Fixed by implementing log truncation in `execute_pre_commit_checks` and `fix_quality_issues` tools.
