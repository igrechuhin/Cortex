# Session Optimization Analysis

**Session**: `/cortex/commit` run (2026-02-01)  
**Signals**: Memory bank (activeContext, progress), MCP log excerpt (fix_markdown_lint connection closed), user feedback (script analysis not used; MCP connection closed).

## Summary

The session ran the commit pipeline and hit two issues the user called out: (1) the session created/ran a script (inline Python to check markdownlint on 3 files) but did **not** use the project’s script-analysis tooling (`analyze_session_scripts`, `capture_session_script`, `suggest_tool_improvements`); (2) `fix_markdown_lint` completed on the server but the client had already closed the connection, yielding `MCP error -32000: Connection closed` and `anyio.ClosedResourceError` when sending the response. This analysis turns both into mistake patterns, root causes, and concrete Synapse/prompt recommendations.

## Mistake Patterns Identified

### Pattern 1: Script created/run without using script-analysis tooling

- **Description**: During the commit run, the agent ran an inline Python script (subprocess calling `npx markdownlint-cli2` on three files) to work around markdown lint results. The project has MCP tools for script capture and analysis (`capture_session_script`, `list_session_scripts`, `analyze_session_scripts`, `suggest_tool_improvements`, `promote_session_script`), but none were used.
- **Examples**: Running a Python snippet in the shell to check markdownlint on `.cortex/memory-bank/progress.md`, `roadmap.md`, and one plan file instead of using `fix_markdown_lint` or then feeding the script into `capture_session_script` / `analyze_session_scripts`.
- **Frequency**: At least once in this session; likely whenever commit or other workflows fall back to “run a script” without a prompt rule to use script tooling.
- **Impact**: Scripts are not captured or analyzed; no promotion path, no consistency with script-generation-prevention (Phase 27) or implement-next-roadmap-step guidance.

### Pattern 2: MCP “Connection closed” on long-running tool response

- **Description**: `fix_markdown_lint` (with `check_all_files=True`, 178+ files) completed on the server and logged “fix_markdown_lint: completed,” but when the MCP server tried to send the response, the client had already closed the connection. The transport raised `anyio.ClosedResourceError` and the client saw `{"error":"MCP error -32000: Connection closed"}`.
- **Examples**: User-cortex MCP log (2687–2739): `_send_response` → `_write_stream.send(JSONRPCMessage(...))` → `send_nowait` → `ClosedResourceError`; client log: “Error calling tool 'fix_markdown_lint': MCP error -32000: Connection closed.”
- **Frequency**: Occurs when a long-running tool (e.g. markdown lint over many files) exceeds client/IDE timeout or user navigates away before the response is sent.
- **Impact**: Orchestrator cannot parse the tool result; commit prompt may treat the step as failed and either block or fall back without clear guidance, and the server-side completion is effectively lost to the client.

## Root Cause Analysis

### Cause 1: Commit prompt does not require script-analysis when a script is run

- **Description**: The commit prompt and related agents focus on pre-commit checks, memory bank, and plan archiving. They do not state that when the agent creates or runs a script (inline or file), it must use `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements`.
- **Contributing factors**: Script-analysis guidance exists in `implement-next-roadmap-step.md` but not in the commit prompt; agents are not reminded to “if you ran a script, use script tooling.”
- **Prevention opportunity**: Add an explicit step or rule in the commit prompt (and optionally in a general agent-workflow rule): “If this session created or executed a script (inline or file), call `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements` as appropriate.”

### Cause 2: No guidance for MCP “Connection closed” in commit workflow

- **Description**: When an MCP tool returns “Connection closed” (or the client sees that error), the commit prompt does not tell the agent to retry the tool once or to fall back to an equivalent shell/local check for that step and document the fallback.
- **Contributing factors**: MCP failure protocol focuses on tool crashes and invalid JSON; client-initiated closure (timeout/closed connection) is a different case—tool logic succeeded but the response could not be delivered.
- **Prevention opportunity**: In the commit prompt (e.g. “MCP Tool Failure” or “Failure Handling”): if the tool error indicates “Connection closed” or “Connection closed” in the message, retry the tool once; if it fails again, perform a documented fallback (e.g. run markdown lint via shell for Step 12.6) and note “MCP connection closed; fallback used” so the pipeline can continue without blocking.

### Cause 3: Long-running tools and client timeout mismatch

- **Description**: `fix_markdown_lint` with `check_all_files=True` can take a long time (many files). The client (Cursor/IDE) may close the connection or timeout before the server sends the response, even though the tool completed successfully.
- **Contributing factors**: No documented “client timeout vs tool duration” guidance; no explicit recommendation to use a smaller scope (e.g. modified files only) when full check is slow, or to document that “Connection closed” can mean “client gave up, not tool failure.”
- **Prevention opportunity**: Document in `docs/mcp-tool-timeouts.md` (or a short “Connection closed” subsection): long-running tools may finish after the client has closed; agents should treat “Connection closed” as “retry once, then fallback if needed” rather than a hard tool failure.

## Optimization Recommendations

### Recommendation 1: Require script-analysis when commit (or any) session runs a script

- **Priority**: High
- **Target**: `.cortex/synapse/prompts/commit.md` (and optionally `.cortex/synapse/rules/general/agent-workflow.mdc`)
- **Change**: Add a step or bullet: “If during this run you created or executed any script (inline snippet or file), you MUST call `capture_session_script` and/or `analyze_session_scripts` or `suggest_tool_improvements` as appropriate. Do not run scripts without using script tooling.”
- **Expected impact**: Ensures every session that generates/executes a script is analyzed and capturable, aligning with Phase 27 script-generation-prevention and existing implement-next-roadmap-step guidance.
- **Implementation**: Insert in commit prompt after “Steps without dedicated agents” or in a new “Script use” subsection; optionally add the same rule to agent-workflow.mdc for all workflows.

### Recommendation 2: Define “Connection closed” handling in commit and MCP docs

- **Priority**: High
- **Target**: `.cortex/synapse/prompts/commit.md` (Failure Handling / MCP Tool Failure), `docs/mcp-tool-timeouts.md`
- **Change**:
  - Commit: When an MCP tool returns an error whose message or code indicates “Connection closed” (or “Connection closed” / “ClosedResourceError”): (1) Retry the tool once. (2) If it fails again with the same class of error, perform a documented fallback for that step (e.g. for `fix_markdown_lint`, run markdown lint via shell with the same scope) and record “MCP connection closed; fallback used” so the pipeline can proceed.
  - Docs: Add a short “Client connection closed during long tools” subsection: explain that long-running tools may complete after the client has closed; “Connection closed” can mean client timeout/disconnect, not necessarily tool failure; recommend retry then fallback.
- **Expected impact**: Reduces commit blocks and confusion when `fix_markdown_lint` (or similar) succeeds on the server but the client no longer receives the response.
- **Implementation**: Edit commit prompt “MCP Tool Failure” / “Failure Handling” and add a subsection under docs/mcp-tool-timeouts.md.

### Recommendation 3: Mention script tooling in commit prompt “Common errors” or “Tooling”

- **Priority**: Medium
- **Target**: `.cortex/synapse/prompts/commit.md`
- **Change**: In “COMMON ERRORS TO CATCH” or tooling section, add: “**Script run without analysis**: If you ran a script (e.g. Python/shell snippet) during the pipeline, you must use `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements`. Not using script tooling is a process violation.”
- **Expected impact**: Makes script-analysis a visible, checkable item during commit.
- **Implementation**: One short bullet or sub-bullet in the commit prompt.

### Recommendation 4: Optional—reduce scope of fix_markdown_lint in Step 12 when safe

- **Priority**: Low
- **Target**: Commit prompt Step 12.6 description
- **Change**: Note that for Step 12.6, if `fix_markdown_lint(check_all_files=True)` has previously timed out or returned “Connection closed,” the agent may run markdown lint on modified/added markdown files only (with a one-line note) to reduce duration while still validating changed files.
- **Expected impact**: May reduce incidence of client disconnect during the final markdown lint step.
- **Implementation**: One sentence in Step 12.6 or in the “Connection closed” handling text.

## Implementation Plan

1. **Recommendation 2** (Connection closed handling): Update commit prompt and `docs/mcp-tool-timeouts.md` so “Connection closed” is explicitly handled (retry, then fallback) and documented.
2. **Recommendation 1** (Script-analysis when script run): Add mandatory script-analysis step/rule to commit prompt (and optionally agent-workflow.mdc).
3. **Recommendation 3** (Common errors): Add “Script run without analysis” to commit prompt common errors/tooling section.
4. **Recommendation 4** (Optional): Add optional narrower-scope note for Step 12.6 when connection/timeout has been an issue.

## References

- User feedback: (1) “Session created a script. Has it been analyzed? We have tooling for that. But I don't see that it was used.” (2) “MCP error -32000: Connection closed” and MCP log excerpt (fix_markdown_lint completion then ClosedResourceError on send).
- Existing guidance: `implement-next-roadmap-step.md` (script generation prevention, suggest_tool_improvements, capture_session_script, analyze_session_scripts, promote_session_script); Phase 27 script capture tools; commit prompt “Do NOT run scripts directly; use tools only” (refers to pre-commit scripts, not script-analysis tooling).
- MCP log: anysphere.cursor-mcp.MCP user-cortex lines 2687–2739 (fix_markdown_lint: completed → TaskGroup error → ClosedResourceError in _send_response).
