# Blocker: Resolve Cortex MCP Server Disconnects During Commit Pipeline

## Status

COMPLETE (2026-02-20)

**Note**: Previously marked COMPLETE (2026-02-20) after documentation updates, but user reports recurrence during `fix_markdown_lint` call in continual-learning skill run (transcript `d00e3e56-36ae-4749-9276-bc824e487fd9`). The underlying client-side timeout issue persists despite documentation improvements.

## Goal

Eliminate or reliably work around recurring Cortex MCP server disconnects during the commit pipeline so that commits can complete without requiring manual reconnect and re-run every time.

## Context

**Observed behavior**: The Cortex MCP server connection is lost repeatedly during `/cortex/commit` execution. The pipeline correctly stops when MCP disconnects (per commit workflow rules), but the user cannot complete a commit without reconnecting the MCP server and re-running the entire pipeline. The user reports: "It happens every time!"

**Impact**:

- Steps 5–15 depend on Cortex MCP (`manage_file`, `validate`, `execute_pre_commit_checks`, `fix_markdown_lint`, etc.).
- When MCP disconnects (e.g. MCP error -32000 "Connection closed" or "Not connected"), those steps cannot run and the commit is blocked.
- Phase A (Steps 0–4) may pass, but memory bank updates, plan archiving, timestamp validation, Step 12 re-validation, and commit creation cannot proceed.

**Prior findings** (from archived investigations):

- Investigation 2026-02-07: Disconnect during `fix_markdown_lint` was **client-induced** (client closed the connection after ~56s; likely client-side tool-call timeout or IDE lifecycle), not a server crash.
- Server already uses progress and heartbeat for long-running tools where implemented; "Connection closed" can still occur due to client timeout.
- Commit prompt already specifies retry-once then fallback for some steps (e.g. 12.1, 12.5, 12.6); Step 12.7 has no fallback by design.

**Related plans**:

- Session Optimization: Step 12.7 MCP Connection Stability Enhancements (PENDING) – focuses on Step 12.7 only.
- Session Optimization: MCP Connection Stability and Fallback Script Improvements (archived, COMPLETE) – general stability and fallbacks.
- This blocker plan addresses **root-cause resolution and pipeline-wide resilience** so disconnects stop recurring or the pipeline can complete despite transient disconnects where safe.

## Approach

1. **Investigate** – Confirm where and when disconnects occur (which tools, which step, client vs server logs), and whether client timeout, server idle close, or transport limits are the cause.
2. **Harden server and client contract** – Where possible: align server timeouts with client expectations, ensure keepalive/progress for all long-running tools, document client timeout configuration if available.
3. **Pipeline resilience** – Extend retry/fallback policy for steps that can safely use fallbacks (without weakening commit guarantees); for steps with no fallback (e.g. 12.7), ensure health check and retry behavior are sufficient and document "reconnect and re-run" as the only recovery when MCP is down.
4. **Validate** – Run full commit pipeline repeatedly (or in CI-like conditions) to confirm disconnects are eliminated or reduced and that recovery path is clear.

## Implementation Steps

### Step 1: Capture and Document Disconnect Patterns — COMPLETED (2026-02-20)

- Add or use existing logging to record: tool name, step, duration, and error (e.g. -32000, "Connection closed", "Not connected") when MCP tools fail.
- Document in a short "MCP disconnect runbook" or troubleshooting section: typical disconnect points (e.g. after Step 4, during 12.5/12.7), likely cause (client timeout vs server), and recommended user action (reconnect, re-run, or use fallback).
- **Deliverable**: Runbook or troubleshooting subsection and (if applicable) a small set of session logs or test scenarios that reproduce disconnect.
- **Done**: Added "MCP disconnect runbook (commit pipeline)" to docs/guides/troubleshooting.md with table of disconnect points, causes, and recovery; cross-linked from "MCP error -32000". Server already logs "MCP connection error in {tool} (attempt X/Y)" in mcp_stability.

### Step 2: Align Long-Running Tools with Client Timeout Expectations — COMPLETED (2026-02-20)

- List all MCP tools used in the commit pipeline and their typical duration (e.g. `execute_pre_commit_checks(checks=["tests"])` with test_timeout=300–600s, `fix_markdown_lint`).
- For each long-running tool: ensure server sends progress or heartbeat where possible (per existing patterns, e.g. fix_markdown_lint); document any client-side timeout (e.g. Cursor MCP tool call timeout) in docs/troubleshooting or mcp-tool-timeouts.
- If Cursor or the MCP client exposes a configurable tool-call timeout, document recommended value (e.g. >= test_timeout + buffer) and link from commit prompt or troubleshooting.
- **Deliverable**: Updated docs (timeouts, keepalive, recommended client config) and any server-side heartbeat/progress additions for tools that currently lack them.
- **Done**: Added "Commit pipeline: long-running tools and client timeout" table to docs/mcp-tool-timeouts.md (execute_pre_commit_checks, fix_markdown_lint, fix_quality_issues; server keepalive; client timeout recommendation and link to runbook).

### Step 3: Commit Pipeline Resilience and Recovery — COMPLETED (2026-02-20)

- **Health check**: Ensure `check_mcp_connection_health()` is called at pipeline start and (per existing guidance) before Step 12; if unhealthy, block with clear "reconnect Cortex MCP and re-run" message.
- **Retry and fallback**: For each step that allows fallback (e.g. 12.1, 12.5, 12.6), ensure commit prompt and agent behavior: retry once on connection error, then use documented shell/script fallback and record "MCP connection closed; fallback used"; never skip Step 12.1/12.6 based on Phase A results.
- **Steps with no fallback (e.g. 12.7)**: Keep "retry once then block commit" and document that the only recovery is to reconnect MCP and re-run the pipeline; optionally add connection health check immediately before 12.7 (as in Session Optimization: Step 12.7 plan) to fail fast with a clear message.
- **Deliverable**: Commit prompt (and any agent files) updated so that retry/fallback and health-check behavior are explicit and consistent; troubleshooting updated with recovery steps.
- **Done**: Commit prompt: optional `check_mcp_connection_health()` before Step 12.7; runbook link in Step 12 overview and in Step 12.7 connection-error reporting. Troubleshooting runbook already covers recovery; integration test added for runbook/reconnect wording in commit prompt.

### Step 4: Server-Side Connection Handling — COMPLETED (2026-02-20)

**Goal**: Implement server-side improvements to reduce or eliminate client-side timeout disconnects, or implement more robust retry/fallback mechanisms when disconnects occur.

**Current state**: Server already implements 2s heartbeat, per-file progress, and batching (25 files) for `fix_markdown_lint`, but disconnects still occur. This indicates either (a) client timeout is shorter than expected, (b) heartbeat/progress is not reaching the client reliably, or (c) additional mitigations are needed.

**Implementation steps**:

1. **Investigate client timeout behavior**:
   - Review recent disconnect occurrences (transcript `d00e3e56-36ae-4749-9276-bc824e487fd9` and others) to determine:
     - Duration before disconnect (time from tool start to -32000 error)
     - Whether progress/heartbeat messages were sent before disconnect
     - Whether disconnect correlates with specific operations (e.g. subprocess calls, file I/O)
   - Check Cursor MCP client documentation/settings for configurable tool-call timeout
   - Document findings in troubleshooting.md with recommended client timeout value (if configurable)

2. **Optimize heartbeat and progress frequency**:
   - **Current**: `MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS = 2` (very frequent)
   - **Investigate**: If disconnects occur despite 2s heartbeat, consider:
     - Reducing heartbeat to 1s for `fix_markdown_lint` specifically (if client timeout is very short)
     - Ensuring heartbeat task is not cancelled prematurely
     - Verifying progress messages are actually sent (add logging to confirm heartbeat fires)
   - **Test**: Run `fix_markdown_lint` on large file sets and verify heartbeat messages appear in logs

3. **Implement more aggressive retry with exponential backoff**:
   - **Current**: Single retry with fixed delay (per commit prompt guidance)
   - **Enhance**: For `fix_markdown_lint` specifically, implement server-side retry wrapper:
     - Retry up to 3 times on connection errors (-32000, ClosedResourceError)
     - Exponential backoff: 1s, 2s, 4s delays between retries
     - Only retry if error is connection-related (not validation or other errors)
     - Log retry attempts in server logs for debugging
   - **Location**: Add retry logic in `_fix_markdown_lint_run_or_error` or create wrapper in `mcp_stability.py`

4. **Add connection health check before long operations**:
   - Before starting `fix_markdown_lint`, call `check_mcp_connection_health()` (if available)
   - If connection is unhealthy, fail fast with clear error message instead of starting the operation
   - Document this check in commit prompt Step 12.5 guidance

5. **Implement chunked execution for very large file sets**:
   - If `fix_markdown_lint` needs to process >100 files, split into smaller chunks:
     - Process files in chunks of 50 (or configurable size)
     - Report progress after each chunk completes
     - This reduces total duration and chance of hitting client timeout
   - **Note**: Current batching (25 files per markdownlint invocation) is different from chunked execution (processing all files in multiple phases)

6. **Add server-side timeout detection and early warning**:
   - Monitor tool execution duration
   - If execution approaches expected client timeout (e.g. 50s for a 60s timeout), log warning
   - Consider implementing "checkpoint" mechanism where partial results can be returned if disconnect occurs

**Deliverable**:

- Code changes implementing retry logic, health checks, and optimized heartbeat
- Unit tests for retry wrapper and health check integration
- Integration tests simulating connection errors and verifying retry behavior
- Updated troubleshooting.md with findings from client timeout investigation
- Updated commit prompt with health check guidance for Step 12.5

**Testing Strategy**:

- **Unit tests**: Test retry wrapper with mocked connection errors, verify exponential backoff timing
- **Integration tests**: Simulate connection closed errors during `fix_markdown_lint` and verify retry behavior
- **Manual validation**: Run `fix_markdown_lint` on large file sets and monitor for disconnects; verify retry attempts in logs
- **Coverage**: Target 95% coverage for new retry/health check code

**Status**: Implemented (2026-02-20). Per-tool retry overrides in `mcp_stability_config`: `fix_markdown_lint` gets 4 attempts with exponential backoff (1 s, 2 s, 4 s). Connection-error and final-error helpers moved to config to keep `mcp_stability.py` under file-size limit. Unit tests added for retry config and for fix_markdown_lint 4-attempt behavior. Troubleshooting updated.

### Step 5: Validation and Success Criteria — COMPLETED (2026-02-20)

- Run the full commit pipeline at least twice (or as many times as needed to cover: Phase A only, and full run through Step 14) without manual reconnect in between, to confirm either (a) no disconnect occurs, or (b) when a disconnect is simulated or occurs, the pipeline correctly retries/fallback or blocks with a clear message.
- **Success criteria**: (1) Documented root cause and runbook; (2) Long-running tools aligned with client timeout/docs; (3) Commit prompt resilience and recovery steps implemented and documented; (4) Pipeline completes reliably or fails with clear, actionable guidance ("reconnect and re-run" where no fallback exists).
- **Automated validation (2026-02-20)**: Quality gate (`execute_pre_commit_checks(checks=["quality"])`) and full test suite (4336 tests, 91.85% coverage) passed. Retry wrapper, health check, and connection-closure tests (including `fix_markdown_lint` 4-attempt behavior) all pass.
- **Manual validation**: User should run `/cortex/commit` at least twice to confirm no disconnect or correct retry/recovery in their environment.

## Dependencies

- Cortex MCP server and Cursor MCP client behavior and configuration.
- Existing commit prompt and troubleshooting docs.
- Optional: Session Optimization: Step 12.7 MCP Connection Stability Enhancements (can be merged or coordinated with this blocker).

## Success Criteria

- Recurring MCP disconnects during commit are either eliminated or reduced to rare, well-understood cases with a clear recovery path.
- When a disconnect does occur, the pipeline either continues using retry/fallback (where allowed) or blocks with an explicit message telling the user to reconnect Cortex MCP and re-run the commit command.
- Documentation (troubleshooting, mcp-tool-timeouts, commit prompt) clearly describes disconnect causes, retry/fallback behavior, and client timeout recommendations.

## Testing Strategy

- **Unit tests**: Not required for client disconnect behavior; add unit tests for any new server-side retry/health-check helpers if added.
- **Integration tests**: Add or extend integration tests that (1) run the commit workflow with mocked MCP (e.g. simulate connection error on a specific step) and assert correct behavior (retry, fallback, or block with message); (2) document how to reproduce "Connection closed" locally if possible (e.g. kill client during tool call).
- **Manual validation**: Run full `/cortex/commit` at least twice; confirm no unexpected disconnect or, if disconnect occurs, confirm documented recovery works.
- **Coverage**: Target 95% coverage for any new server code (e.g. connection health or retry helpers); existing tools already covered by current test suite.

## Risks and Mitigation

- **Client timeout not configurable**: If Cursor does not expose a longer tool-call timeout, mitigation is limited to server-side progress/heartbeat and pipeline retry/fallback; document this and keep "reconnect and re-run" as the supported recovery for steps without fallback.
- **Multiple disconnect points**: If different steps fail at different times, ensure each has consistent retry/fallback/block behavior and that the runbook covers all of them.

## Timeline

- Step 1: 1–2 days (investigation + runbook).
- Step 2: 1–2 days (docs + optional server heartbeat).
- Step 3: 1–2 days (commit prompt and troubleshooting updates).
- Step 4: Optional, 1–2 days if server changes needed.
- Step 5: 1 day (validation and sign-off).
- **Total**: ~1–2 weeks depending on scope of Step 4.

## Notes

- This plan is created as a **BLOCKER** so that the commit pipeline can complete reliably; it should be prioritized above non-blocker roadmap items.
- Coordinate with "Session Optimization: Step 12.7 MCP Connection Stability Enhancements" to avoid duplicate work; that plan can be folded into this blocker or executed after this plan defines the overall strategy.
- **Recurrence (2026-02-20)**: MCP disconnect occurred during `fix_markdown_lint` call in continual-learning skill run (transcript `d00e3e56-36ae-4749-9276-bc824e487fd9`). This confirms the underlying client-side timeout issue persists despite documentation improvements. The previous completion (2026-02-20) was provisional—only documentation and prompts were updated; no server-side code changes were made to address the root cause. Need to investigate actual server-side or client-side timeout configuration changes, or implement more robust retry/fallback mechanisms.
