# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Cortex.

## Common Issues

### Installation and Setup

#### Issue: `uv` command not found

**Symptoms**:

```bash
$ uvx cortex
-bash: uvx: command not found
```

**Solution**:
Install `uv` package manager:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Issue: Python version too old

**Symptoms**:

```text
ERROR: Python 3.13 or later is required
```

**Solution**:
Install Python 3.13+:

```bash
# Using uv
uv python install 3.13

# Or using pyenv
pyenv install 3.13.0
pyenv global 3.13.0
```

#### Stable MCP setup (one-place checklist)

For a **stable MCP connection**, see [Getting started: Stable MCP setup](../getting-started.md#stable-mcp-setup-recommended): Cortex exits on disconnect by default (client starts a new process when needed, so you get fresh Initialize with no user action), optional bridge, faster markdown lint, and usage tips. The sections below cover individual issues and causes.

#### Issue: MCP server crashes with BrokenResourceError

**Symptoms**:

```text
ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
  anyio.BrokenResourceError
```

**Causes**:

- Client disconnected while server was processing
- Request was cancelled by client
- Client process terminated unexpectedly

**Solution**:

From a **server** perspective this is graceful behavior (the server exits cleanly with exit code 0 and does not crash). From a **workflow** perspective disconnections are a real problem:

1. **You must reconnect**  
   After a disconnection the agent can continue running **without MCP**—it may use only built-in tools and skip Cortex (memory bank, rules, quality checks). To keep the agent under Cortex control, reconnect the client so the MCP server restarts, and if the agent is already running, consider re-running the task so it uses Cortex MCP tools.

2. **Check that MCP is available before relying on the agent**  
   If you don’t verify the connection, the agent may work without MCP control. Use a lightweight check (e.g. ensure Cortex tools appear in the client, or call `check_mcp_connection_health` if available) before starting important agent work.

3. **If disconnections are frequent**  
   Check client configuration, timeouts, and network stability. See [MCP error -32000: Connection closed](#issue-mcp-error-32000-connection-closed) for mitigations.

4. **Reconnect is automatic**  
   By default Cortex **exits** when the connection drops; the client starts a new process when it next needs MCP. No user reload needed. If you set `CORTEX_AUTO_RESTART=1`, you may then see "0 tools" after a disconnect and need to reload MCP.

The server distinguishes between:

- **Graceful disconnection** (exit code 0): Client closed connection
- **Actual errors** (exit code 1): Server-side failures

If the **client** shows `MCP error -32000: Connection closed` during a tool call, see [MCP error -32000: Connection closed](#issue-mcp-error-32000-connection-closed).

#### Issue: MCP server not found by client

**Symptoms**:

- Claude Desktop doesn't show Memory Bank tools
- Cursor IDE doesn't connect to server

**Solution**:

1. Check MCP configuration file location:
   - **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
   - **Cursor**: `.cursor/mcp_config.json` in project root

2. Verify configuration:

   ```json
   {
     "mcpServers": {
       "memory-bank": {
         "command": "uvx",
         "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
       }
     }
   }
   ```

3. Restart the MCP client

#### Issue: MCP error -32000: Connection closed {#issue-mcp-error-32000-connection-closed}

**Symptoms**:

- Tool call returns: `{"error":"MCP error -32000: Connection closed"}`
- Occurs during long-running tools (e.g. `fix_markdown_lint`, `execute_pre_commit_checks`, `fix_quality_issues`)

**Cause**:

The **client** (e.g. Cursor) closed the MCP connection before the tool finished—usually due to client-side tool timeout or IDE lifecycle, not a server bug. The tool may have completed on the server; the connection was already closed when the response was sent.

**Why it matters**: After a disconnect the agent may keep running **without MCP**. It will not use Cortex tools (memory bank, rules, quality checks). Reconnect so the server restarts; for important work, re-run the task so the agent runs with MCP control. For disconnects **during the commit pipeline**, see the [MCP disconnect runbook (commit pipeline)](#mcp-disconnect-runbook-commit).

**Reconnect is automatic**: By default Cortex exits when the connection drops; the client starts a new process when it next needs MCP. If you set `CORTEX_AUTO_RESTART=1`, you may need to reload MCP after a disconnect to restore tools.

**Fix (what to do)**:

1. **Retry once**  
   The client or agent should retry the same tool once. Many connection drops are transient; the second call often succeeds.

2. **Use local markdownlint**  
   For `fix_markdown_lint`, use a local install so the tool runs faster and is less likely to hit the client timeout:
   - From project root: `npm install` (uses `package.json`). The tool prefers `node_modules/.bin/markdownlint-cli2` and avoids npx/network at run time.
   - See [markdownlint-cli2 and npm (fix_markdown_lint)](#markdownlint-cli2-and-npm-fix_markdown_lint).

3. **Use documented fallbacks in the commit pipeline**  
   If a retry still fails with "Connection closed", follow the commit prompt’s fallback for that step (e.g. run markdown lint via shell for Step 12.5, or the fallback scripts for Step 12.6) and record "MCP connection closed; fallback used". Do not block the pipeline on "tool not found" after a disconnect—use the fallback.

HTTP/SSE or a stdio–HTTP bridge is not a supported workaround for this issue (it has been tried and does not resolve connection closed during long tools).

**Server-side mitigations (already in place)**:

- **Client cancel no longer disconnects**: When the client cancels a request (e.g. timeout), the server returns a structured error response instead of propagating cancellation. The connection stays open, so you avoid disconnect and "0 tools" from cancels.
- Progress and heartbeat for long tools (e.g. 2 s heartbeat and wrapper progress for `fix_markdown_lint`, frequent progress for `execute_pre_commit_checks`).
- Automatic retry for connection errors in the tool wrapper. Most tools get one retry; `fix_markdown_lint` gets **four attempts** (1 initial + 3 retries) with exponential backoff (1 s, 2 s, 4 s) to reduce commit-pipeline disconnects.
- Batched markdown lint to reduce total duration.
- **Serialization with wait for long-running tools**: Only one of `execute_pre_commit_checks`, `fix_markdown_lint`, or `fix_quality_issues` can run at a time. If you call a second long-running tool while the first is still running, the second call **waits up to 330 seconds (5–6 minutes)** for the first to finish; if the first is still running after that, the server returns an error. This allows sequential commit-pipeline calls (e.g. `execute_pre_commit_checks` then `fix_markdown_lint`) to succeed when the second request arrives before the first has returned. See [Another long-running tool is in progress](#issue-another-long-running-tool-in-progress).

#### Issue: Found 0 tools, 0 prompts, and 0 resources {#issue-mcp-0-tools}

**Symptoms**:

- MCP client log shows: `Found 0 tools, 0 prompts, and 0 resources` for the Cortex server.
- Warnings like: `Failed to validate request: Received request before initialization was complete`.

**Cause**:

This happens when the client sends ListTools/ListPrompts/ListResources **before** completing an **Initialize** handshake with the server—usually after a disconnect when the server process was **replaced under the same connection** (e.g. you use `CORTEX_AUTO_RESTART=1`). The new process has no session yet; the client may send list requests using old session state, so the server rejects them and the client shows 0 tools.

**Fix (what to do)**:

- **Default (no CORTEX_AUTO_RESTART)**: Cortex exits on disconnect; the client starts a new process when it next needs MCP, so you get a fresh Initialize with no user action. You should not see 0 tools.
- **Automatic recovery**: Install the [Cursor MCP Refresh](https://github.com/tankmurdock/cursor-mcp-refresh) extension and set **Auto-refresh interval** (e.g. 60–300 seconds). It refreshes MCP servers on a timer, so "0 tools" is cleared on the next refresh without manual toggle. [Install from VSIX](https://github.com/tankmurdock/cursor-mcp-refresh/releases).
- **If you set CORTEX_AUTO_RESTART=1** and don't use the extension: reload MCP manually (disable/enable Cortex in MCP Servers, or restart Cursor). Retry once first; optional: `CORTEX_USE_FALLBACK_ROOT=1`; see [mcp-tool-timeouts](mcp-tool-timeouts.md).

#### Issue: Another long-running tool is in progress {#issue-another-long-running-tool-in-progress}

**Symptoms**:

- Tool call returns a `RuntimeError`: "Another long-running tool is in progress (e.g. execute_pre_commit_checks or fix_markdown_lint). Please wait for it to finish (up to 5–6 minutes) and retry."

**Cause**:

Only one of `execute_pre_commit_checks`, `fix_markdown_lint`, or `fix_quality_issues` can run at a time. If the client (or agent) invokes a second long-running tool while the first is still running, the second call **waits up to 330 seconds (5–6 minutes)** for the first to finish. If the first is still running after that, the server returns this error.

**Fix (what to do)**:

1. If you see this error, the first long-running tool took longer than 330 seconds (5–6 minutes). Wait for it to finish, then retry the tool you wanted to run.
2. Prefer running long-running tools one after another and wait for each to complete before starting the next (e.g. run `fix_markdown_lint` only after `execute_pre_commit_checks` has completed, or vice versa). Sequential calls that arrive while the first is still running will wait automatically.

#### MCP disconnect runbook (commit pipeline) {#mcp-disconnect-runbook-commit}

Use this runbook when the Cortex MCP connection is lost **during** `/cortex/commit` (e.g. client shows `MCP error -32000: Connection closed` or "Connection closed", and the pipeline stops or cannot complete Step 12).

**Typical disconnect points** (where disconnects are most often observed):

| When | Step / phase | Likely cause | Recommended action |
|------|----------------|---------------|---------------------|
| After Phase A (Steps 0–4) | Before or at start of Step 5 | Client idle or tool-call timeout after Phase A gap | Reconnect Cortex MCP, then re-run `/cortex/commit`. Call `check_mcp_connection_health()` before Step 12 if the pipeline supports it. |
| During Step 12.1 (format) | Format fix or check | Client timeout during formatting tool | Retry once; if retry fails, use fallback scripts (`fix_formatting.py` then `check_formatting.py`) per commit prompt; record "MCP connection closed; fallback used". Do not skip Step 12.1. |
| During Step 12.5 (markdown lint) | `fix_markdown_lint` or check | Client timeout (markdown lint can be slow) | Retry once; if retry fails, run markdown lint via shell (see commit prompt) and record "MCP connection closed; fallback used". |
| During Step 12.6 (file size / function length) | Quality checks | Client timeout | Retry once; if retry fails, use shell script fallbacks for file size and function length checks; record "MCP connection closed; fallback used". Do not skip Step 12.6. |
| During Step 12.7 (tests with coverage) | `execute_pre_commit_checks(checks=["tests"], ...)` | Client timeout (tests can run 5–10+ minutes) | Retry once. **There is no fallback for Step 12.7.** If retry fails, **block commit** and tell the user: "Reconnect Cortex MCP and re-run the commit command." Do not proceed with Phase A results. |

**Likely cause**: In most cases the **client** (e.g. Cursor) closed the connection—due to client-side tool-call timeout or IDE lifecycle—not a server crash. The tool may have completed on the server; the connection was already closed when the response was sent. To increase Cursor’s timeout, see [Cursor IDE: MCP tool timeout configuration](#cursor-ide-mcp-tool-timeout-configuration). See also [MCP error -32000: Connection closed](#issue-mcp-error-32000-connection-closed).

**How to confirm**: Check MCP server stderr (or Cursor Output / MCP logs) for lines like `MCP connection error in <tool_name> (attempt 1/2): ...` to see which tool and attempt failed. In one observed case (MCP log 1-18553), disconnect during `fix_markdown_lint` occurred **≈10 s** after the tool call started; compare that with client timeout settings. Session logs or repro: run `/cortex/commit`, let it reach the long step (e.g. 12.7), and note after how long the disconnect occurs.

**Recovery summary**:

- **Steps with fallback (12.1, 12.5, 12.6)**: Retry once → if still failing, use documented shell/script fallback → record "MCP connection closed; fallback used" → continue pipeline. Never skip these steps based on Phase A.
- **Step 12.7 (no fallback)**: Retry once → if still failing, **block commit**, report connection failure, and instruct user to **reconnect Cortex MCP and re-run the commit command**. Do not proceed with Phase A test results.

**References**: Commit prompt "Connection closed" and "Step 12" sections; [MCP error -32000: Connection closed](#issue-mcp-error-32000-connection-closed); [Client connection closed during long tools](../../mcp-tool-timeouts.md#client-connection-closed-during-long-tools) in mcp-tool-timeouts.

### Development and Testing

#### Issue: I don't see any option to run tests in Cursor

**Symptoms**:

- No "Run Test" / "Run All Tests" buttons
- No Test view or testing icon in the sidebar

**Solution**:

1. **Open the Testing view**  
   - Click the **flask/beaker icon** in the left sidebar (Testing), or  
   - **View → Testing**, or  
   - Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) → type **"Testing: Focus on Test View"**.

2. **Install the Python extension**  
   - Extensions panel (`Cmd+Shift+X` / `Ctrl+Shift+X`) → search **"Python"** (Microsoft) → Install if missing.  
   - The built-in Test explorer depends on this extension.

3. **Select the workspace interpreter**  
   - Command Palette → **"Python: Select Interpreter"** → pick **`.venv (Python 3.13.x)`** under the project folder.  
   - Without this, test discovery may not run or may use the wrong environment.

4. **If the Test view is empty or discovery fails**  
   Cursor’s bundled Python extension can have pytest discovery issues. Try:
   - **Cursor Pytest** extension: Extensions → search **"Cursor Pytest"** (by Arun Dev) → Install. It adds inline Run/Debug buttons and test discovery.
   - Or run tests from the terminal: `uv run pytest tests/ -k "test_name"` for a single test, or use Cortex MCP `execute_pre_commit_checks(checks=["tests"], ...)` for the full suite.

5. **Ensure `.vscode/settings.json` exists** (see next subsection) so that when tests do run from the UI, the correct interpreter is used.

#### Issue: "pytest-cov is not installed" during test discovery

**Symptoms**:

- Python extension log shows: `VSCodePytestError: ERROR: pytest-cov is not installed, please install this before running pytest with coverage as pytest-cov is required.`
- Test discovery fails and the Test view stays empty.

**Cause**:

The Microsoft Python extension runs pytest for discovery. If `pytest.ini` has `--cov` in `addopts`, the extension requires `pytest-cov` to be installed and aborts discovery otherwise (even when coverage is disabled for that run).

**Solution** (applied in this repo):

Coverage is **not** in the default `pytest.ini` addopts. CI and `execute_pre_commit_checks` pass `--cov=src/cortex`, `--cov-report=...`, and `--cov-fail-under=90` explicitly, so full runs still enforce coverage. IDE discovery no longer sees coverage options and no longer requires `pytest-cov` for discovery.

If you see this error in another project, either add coverage options only when running tests (e.g. via CI or a script), or install dev deps so `pytest-cov` is present: `uv sync --group dev --extra dev`.

#### Issue: Tests don't run or always fail from Cursor/VS Code UI

**Symptoms**:

- Clicking "Run Test" / "Run All Tests" in the Test view does nothing or shows failures
- Running a single test file exits with "FAILED" due to coverage (e.g. "Required test coverage of 90% not reached")

**Cause**:

`pytest.ini` sets `--cov-fail-under=90` in `addopts`. When you run one test or one file from the IDE, coverage is computed over the whole codebase, so the run fails even if the tests passed.

**Solution**:

1. **Use the project venv**  
   Select the workspace interpreter: `.venv/bin/python` (Command Palette → "Python: Select Interpreter" → choose the one under the project folder).

2. **Disable coverage for IDE test runs**  
   So the Test UI doesn't enforce 90% coverage on partial runs, add or merge this into `.vscode/settings.json` (this folder is gitignored; create it if needed):

   ```json
   {
     "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
     "python.testing.pytestEnabled": true,
     "python.testing.unittestEnabled": false,
     "python.testing.pytestArgs": ["-p", "no:cov"]
   }
   ```

   `-p no:cov` disables the coverage plugin for that run. In Cortex, default `pytest.ini` addopts do not include coverage; CI and MCP pass `--cov` explicitly for full runs.

3. **Reload the window**  
   After changing settings: Command Palette → "Developer: Reload Window", then use the Test view again.

#### Step 12.7 and sandboxed environments {#step-127-and-sandboxed-environments}

**Symptoms**:

- Step 12.7 (tests with coverage) in the commit pipeline fails or cannot execute when run in a sandboxed environment (e.g. restricted CI, agent runner, or environment where test execution is disabled or times out).

**Cause**:

Sandboxed environments may block or limit subprocess execution, network, or long-running processes. The commit pipeline requires Step 12.7 to pass before commit; there is no fallback for tests (unlike formatting or quality checks).

**What to do**:

1. **Commit remains blocked** until Step 12.7 executes successfully. Phase A (Step 4) test results are not acceptable in place of Step 12.7, because code or memory-bank changes in Steps 5–11 can affect test results.
2. **Run tests outside the sandbox**: Run the full test suite locally or in a non-sandboxed CI job (e.g. `execute_pre_commit_checks(checks=["tests"], ...)` or `uv run pytest tests/` with coverage). Ensure tests pass and coverage ≥ 90%.
3. **Re-run the commit pipeline** after tests pass outside the sandbox, so Step 12.7 can complete (or run the pipeline in an environment where Step 12.7 is allowed).
4. **Document the limitation**: If your environment routinely runs in a sandbox, document that commit must be run in an environment where test execution is allowed, or run tests manually before invoking commit.

#### Step 12.7 Timeout and Connection Requirements {#step-127-timeout-and-connection-requirements}

**Overview**: Step 12.7 (tests with coverage validation) is a long-running operation that can take up to 600 seconds (10 minutes) to complete. The commit pipeline includes connection stability enhancements to prevent commit blocks due to connection closure during test execution.

**Expected test execution time**:

- **Typical duration**: 5–10 minutes for full test suite with coverage
- **Maximum timeout**: 600 seconds (10 minutes) as configured in `test_timeout=600`
- **Client-side timeout requirements**: The client (e.g. Cursor IDE) must have a tool-call timeout ≥ 600 seconds to avoid connection closure during Step 12.7

**Connection health check before Step 12.7**:

- **MANDATORY**: The commit pipeline executes `check_mcp_connection_health()` immediately before Step 12.7.1
- **If health check fails**: Wait 2–5 seconds, retry health check once
- **If still unhealthy**: Block commit with message: "MCP connection unhealthy before Step 12.7. Please reconnect Cortex MCP server and re-run commit pipeline."
- **Rationale**: Fails fast with a clear message instead of timing out during the long test run

**Enhanced retry logic with exponential backoff**:

- **First retry**: If `execute_pre_commit_checks(checks=["tests"])` fails with connection error (e.g., "Connection closed", MCP error -32000), wait 2 seconds and retry
- **Second retry**: If first retry fails, wait 5 seconds and retry again
- **If both retries fail**: Block commit immediately. Do not proceed to Step 13. Report error and instruct user to reconnect Cortex MCP and re-run the commit command
- **No fallback**: Unlike Step 12.6, there is no shell script fallback for tests. Step 12.7 must execute successfully via MCP

**Connection stability monitoring**:

- Connection health metrics are logged before and after test execution for analysis:
  - Health status (healthy/unhealthy)
  - Concurrent operations count
  - Resource utilization percentage
  - Long-running semaphore holder (if any)
- Metrics help identify patterns:
  - Timeout thresholds (when do connections close relative to execution time?)
  - Concurrent operation limits (does semaphore usage correlate with failures?)
  - Client vs server-side timeouts

**How to increase client timeout** (if needed):

- **Cursor IDE**: See [Cursor IDE: MCP tool timeout configuration](#cursor-ide-mcp-tool-timeout-configuration) below for settings and recommended values. Default timeout should be ≥ 600 seconds for Step 12.7.
- **Other clients**: Consult client documentation for tool-call timeout settings.
- **If timeout cannot be increased**: Consider running tests manually before invoking commit, or use a CI environment with longer timeouts.

#### Cursor IDE: MCP tool timeout configuration {#cursor-ide-mcp-tool-timeout-configuration}

Cursor IDE may apply a **client-side tool-call timeout**; when that is shorter than a long-running MCP tool (e.g. `fix_markdown_lint`, `execute_pre_commit_checks`), the client can close the connection and you see `MCP error -32000: Connection closed`. Reported behavior varies by version: some users see ~60 s or 2 minutes (e.g. Cursor 1.5.1+), others see longer defaults; in one log (MCP log 1-18553), disconnect occurred **≈10 s** after `fix_markdown_lint` started, which may indicate a separate shorter limit in some builds or environments.

**Configurable timeout (community-documented)**:

Cursor does not officially document a tool-call timeout setting. Community guides and forum posts suggest adding the following to Cursor’s **Settings (JSON)** (e.g. `Ctrl/Cmd + Shift + P` → “Open Settings (JSON)”):

```json
"mcp.server.timeout": 600000,
"mcp.elicitation.timeout": 600000
```

Values are in **milliseconds**. `600000` = 10 minutes. Use at least **600000** (10 min) if you run the full commit pipeline including Step 12.7 (tests). After changing, reload Cursor (e.g. `Ctrl/Cmd + R`).

**Caveats**:

- These keys are not guaranteed to be supported in all Cursor versions or builds; if disconnects persist, rely on server-side progress, retries, and the [MCP disconnect runbook](#mcp-disconnect-runbook-commit).
- If you observe disconnects at ~10 s despite a long `mcp.server.timeout`, another limit (e.g. stdio or first-response timeout) may apply; report the timing and Cursor version for diagnostics.

**References**: [MCP tool calling timeout (Cursor forum)](https://forum.cursor.com/t/mcp-tool-calling-timeout/49149), [Long Running MCP tool calls (Cursor forum)](https://forum.cursor.com/t/long-running-mcp-tool-calls/131279); [mcp-tool-timeouts.md](../mcp-tool-timeouts.md) (commit pipeline tools and client timeout).

**Troubleshooting connection closures during Step 12.7**:

1. **Check connection health before Step 12.7**: The pipeline automatically checks health; if it reports unhealthy, reconnect MCP before proceeding
2. **Review connection stability logs**: Check server logs for connection health metrics recorded before/after test execution
3. **Verify client timeout**: Ensure client tool-call timeout ≥ 600 seconds
4. **Check for concurrent long-running operations**: If another long-running tool is executing, wait for it to complete before running commit pipeline
5. **Reconnect and retry**: If Step 12.7 fails after retries, reconnect Cortex MCP server and re-run the commit command

**References**: Commit prompt Step 12.7 section; [MCP disconnect runbook (commit pipeline)](#mcp-disconnect-runbook-commit); [MCP error -32000: Connection closed](#issue-mcp-error-32000-connection-closed)

### File Operations

#### Issue: File lock timeout

**Symptoms**:

```text
FileLockTimeoutError: Could not acquire lock for activeContext.md within 10 seconds
```

**Causes**:

- Another process is writing to the file
- Stale lock from crashed process

**Solution**:

1. Check for running processes:

   ```bash
   ps aux | grep cortex
   ```

2. Clean up stale locks:

   ```bash
   # Remove lock files
   rm .memory-bank/*.lock
   ```

3. Retry the operation

#### Issue: File conflict error

**Symptoms**:

```text
FileConflictError: File projectBrief.md was modified externally
```

**Causes**:

- File was edited outside Cortex
- Concurrent edits from multiple clients

**Solution**:

1. Read the current file content:

   ```json
   {
     "tool": "read_memory_bank_file",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "projectBrief.md"
     }
   }
   ```

2. Merge your changes with the current content

3. Write with updated hash:

   ```json
   {
     "tool": "write_memory_bank_file",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "projectBrief.md",
       "content": "merged content",
       "expected_hash": "current_hash_from_read"
     }
   }
   ```

#### Issue: Git conflict markers detected

**Symptoms**:

```text
GitConflictError: File systemPatterns.md contains Git conflict markers
```

**Solution**:

1. Open the file and resolve conflicts:

   ```markdown
   <<<<<<< HEAD
   Version A
   =======
   Version B
   >>>>>>> branch-name
   ```

2. Remove conflict markers and keep desired content

3. Retry the operation

### Validation Issues

#### Issue: Required sections missing

**Symptoms**:

```json
{
  "status": "error",
  "errors": [
    {
      "type": "missing_section",
      "file": "projectBrief.md",
      "section": "Project Overview"
    }
  ]
}
```

**Solution**:

Add the required section to the file:

```markdown
# Project Brief

## Project Overview

Your project overview here...
```

#### Issue: Duplication detected

**Symptoms**:

```json
{
  "duplications": [
    {
      "file1": "systemPatterns.md",
      "file2": "techContext.md",
      "similarity": 0.92
    }
  ]
}
```

**Solution**:

Use transclusion to eliminate duplication:

1. Extract shared content to a dedicated file:

   ```markdown
   <!-- shared.md -->
   ## Authentication
   Users authenticate via OAuth 2.0...
   ```

2. Use transclusion in both files:

   ```markdown
   <!-- systemPatterns.md -->
   {{include:shared.md#Authentication}}

   <!-- techContext.md -->
   {{include:shared.md#Authentication}}
   ```

#### Issue: Token budget exceeded

**Symptoms**:

```text
TokenLimitExceededError: 120000 tokens (limit: 100000)
```

**Solution**:

1. **Option A**: Increase budget in configuration:

   ```json
   {
     "token_budget": {
       "max_total_tokens": 150000
     }
   }
   ```

2. **Option B**: Archive old content:

   ```bash
   mkdir -p memory-bank/archive
   mv memory-bank/old-file.md memory-bank/archive/
   ```

3. **Option C**: Use summarization:

   ```json
   {
     "tool": "summarize_content",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "large-file.md",
       "strategy": "extract_key_sections",
       "target_reduction": 0.5
     }
   }
   ```

### Link and Transclusion Issues

#### Issue: Broken link detected

**Symptoms**:

```json
{
  "broken_links": [
    {
      "file": "systemPatterns.md",
      "link": "missing-file.md",
      "type": "file_not_found"
    }
  ]
}
```

**Solution**:

1. Check if file exists:

   ```bash
   ls memory-bank/missing-file.md
   ```

2. Fix the link or create the missing file

#### Issue: Circular transclusion

**Symptoms**:

```text
Error: Circular transclusion detected: fileA.md -> fileB.md -> fileA.md
```

**Solution**:

1. Identify the cycle in your transclusions:

   ```markdown
   <!-- fileA.md -->
   {{include:fileB.md}}

   <!-- fileB.md -->
   {{include:fileA.md}}  <!-- Circular! -->
   ```

2. Restructure to eliminate the cycle:

   ```markdown
   <!-- Create fileC.md with shared content -->

   <!-- fileA.md -->
   {{include:fileC.md}}

   <!-- fileB.md -->
   {{include:fileC.md}}
   ```

#### Issue: Transclusion section not found

**Symptoms**:

```text
Error: Section 'NonExistent' not found in shared.md
```

**Solution**:

1. Check available sections:

   ```json
   {
     "tool": "query_memory_bank",
     "args": {
       "query_type": "parse_links",
       "file_name": "shared.md"
     }
   }
   ```

2. Update the transclusion with correct section name:

   ```markdown
   <!-- Before -->
   {{include:shared.md#NonExistent}}

   <!-- After -->
   {{include:shared.md#Authentication}}
   ```

### Optimization Issues

#### Issue: Context optimization takes too long

**Symptoms**:

- Optimization takes > 10 seconds
- High CPU usage

**Causes**:

- Large number of files
- Complex dependency graphs
- Relevance scoring overhead

**Solution**:

1. Enable caching:

   ```json
   {
     "performance": {
       "cache_enabled": true,
       "cache_ttl_seconds": 600
     }
   }
   ```

2. Reduce file count:

   ```bash
   # Archive unused files
   mkdir -p memory-bank/archive
   mv memory-bank/unused-*.md memory-bank/archive/
   ```

3. Use simpler optimization strategy:

   ```json
   {
     "optimization": {
       "strategy": "priority"  // Instead of "hybrid"
     }
   }
   ```

#### Issue: Irrelevant files selected

**Symptoms**:

- Context optimization selects wrong files
- Low relevance scores for important files

**Solution**:

1. Adjust relevance scoring weights:

   ```json
   {
     "relevance_scoring": {
       "tfidf_weight": 0.6,        // Increase keyword weight
       "dependency_weight": 0.3,
       "recency_weight": 0.05,
       "quality_weight": 0.05
     }
   }
   ```

2. Use mandatory files:

   ```json
   {
     "optimization": {
       "mandatory_files": [
         "memorybankinstructions.md",
         "projectBrief.md",
         "important-context.md"
       ]
     }
   }
   ```

#### Issue: Context effectiveness shows no_data in analysis-only sessions

**Symptoms**:

- End-of-session Analyze report shows "No session logs found" or "Calls Analyzed: 0"
- `analyze_context_effectiveness()` returns `"status": "no_data"`

**Cause**:

When the only action in the session is running the Analyze (End of Session) prompt, no `load_context` calls were made, so there is no context-effectiveness data for the current session. This is **expected behavior**, not an error.

**Solution**:

- No action required. Report the manual summary (e.g. files used from Pre-Analysis Checklist) in the Context Effectiveness Analysis section.
- **Optional**: To record one call for metrics, run `session_start()` or `load_context(task_description="end-of-session analysis", token_budget=5000)` before running the analysis steps.

#### Issue: load_context zero-budget or zero-files (configuration error)

**Symptoms**:

- `load_context` returns a validation error when `token_budget=0` is passed for a non-trivial task
- Context-effectiveness analysis reports `token_budget=0` or `files_selected=0` for refactor/fix/debug/implement tasks in `learned_patterns` or recommendations

**Cause**:

For non-trivial tasks (refactor, fix, debug, implement), zero token budget or zero files selected is a **configuration/usage error**. The implement, commit, and analyze prompts require non-zero `token_budget` for these task types (e.g. 10k–15k for fix/debug, 20k–30k for implement/add). Passing `token_budget=0` or ending up with zero files selected indicates the caller did not request adequate context.

**Solution**:

1. Use an explicit non-zero `token_budget` when calling `load_context` for non-trivial work: e.g. `load_context(task_description="...", token_budget=10000)` or `token_budget=15000` for fix/debug, `token_budget=20000` or higher for implement/add.
2. Do not pass `token_budget=0` for refactor/fix/debug/implement; the tool may return a validation error for non-trivial tasks.
3. If context-effectiveness reporting flags zero-budget or zero-files in historical sessions, treat it as a configuration error and document the recommendation to use task-appropriate budgets in future runs.

#### Issue: Rules indexing returns no rules (get_relevant)

**Symptoms**:

- `rules(operation="get_relevant", task_description="...")` returns `rules_count: 0` and `indexed_files: 0`
- Coding standards or project rules do not appear in context

**Causes**:

- Rules directory (e.g. `.cortex/rules`) is empty or not populated
- Indexing has not run (e.g. `rules(operation="index")` not called)
- Rules are only in Synapse or in AGENTS.md/CLAUDE.md, not in the indexed rules folder

**Solution**:

1. Ensure the rules directory exists and contains rule files (e.g. `.mdc`, `.md`).
2. Run indexing: `rules(operation="index")` (or `rules(operation="index", force=True)` to reindex).
3. **Fallback**: When the rules index is empty or returns no rules, use one or more of:
   - `get_synapse_rules(task_description="...")` for shared Synapse rules
   - Read key rules from the rules directory path (from `get_structure_info()` → `structure_info.paths.rules`) using the Read tool
   - Use AGENTS.md and CLAUDE.md for coding standards and memory bank access

Prompts (e.g. implement, commit, analyze) already instruct agents to use this fallback when `rules()` returns `status: "disabled"` or no rules; the same applies when `indexed_files` is 0.

### Shared Rules Issues

#### Issue: Git submodule initialization fails

**Symptoms**:

```text
SharedRulesGitError: Git clone failed for shared rules
```

**Causes**:

- Invalid repository URL
- Authentication required
- Network issues

**Solution**:

1. Verify repository URL:

   ```bash
   git ls-remote https://github.com/your-org/shared-rules.git
   ```

2. Set up authentication:

   ```bash
   # SSH (recommended)
   git config --global url."git@github.com:".insteadOf "https://github.com/"

   # Or use personal access token
   git config --global credential.helper store
   ```

3. Retry initialization:

   ```json
   {
     "tool": "setup_shared_rules",
     "args": {
       "project_root": "/path/to/project",
       "repo_url": "git@github.com:your-org/shared-rules.git",
       "force_reinit": true
     }
   }
   ```

#### Issue: Context detection not working

**Symptoms**:

- Wrong rules loaded for task
- Generic rules only

**Solution**:

1. Add more language keywords:

   ```json
   {
     "shared_rules": {
       "context_detection": {
         "language_keywords": {
           "python": ["python", "py", "pytest", "django", "fastapi"],
           "swift": ["swift", "swiftui", "uikit", "combine"]
         }
       }
     }
   }
   ```

2. Manually specify context:

   ```json
   {
     "tool": "get_rules_with_context",
     "args": {
       "project_root": "/path/to/project",
       "task_description": "Implement Python REST API using FastAPI"
     }
   }
   ```

### Git and SSL Certificate Issues

#### Issue: SSL certificate verification failed (git push / clone / fetch)

**Symptoms**:

```text
fatal: unable to access 'https://github.com/...': SSL certificate problem: unable to get local issuer certificate
```

or:

```text
fatal: unable to access '...': SSL certificate problem: self signed certificate in certificate chain
```

**Causes**:

- Missing or outdated CA certificates on the system
- Incorrect certificate path configured for Git
- Corporate or self-signed certificates in the chain
- Certificate expiration or revoked certificate

**Solutions**:

1. **Install or update CA certificates** (most common):

   ```bash
   # macOS (Homebrew)
   brew install ca-certificates

   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install ca-certificates

   # Windows (Git for Windows)
   # Use the certificate manager or run: git config --global http.sslBackend schannel
   ```

2. **Point Git to the correct CA bundle** (if certificates are in a custom path):

   ```bash
   # macOS (system store)
   git config --global http.sslCAInfo /etc/ssl/cert.pem

   # Linux (common paths)
   git config --global http.sslCAInfo /etc/ssl/certs/ca-certificates.crt

   # Or use system store (OpenSSL)
   git config --global http.sslCAInfo "$(openssl version -d | sed 's/OPENSSLDIR: "\(.*\)"/\1/')/certs/cert.pem"
   ```

3. **Self-signed or corporate certificates** (use only in controlled environments):

   ```bash
   # Option A: Add the specific CA certificate
   git config --global http.sslCAInfo /path/to/your/ca-bundle.crt

   # Option B: Temporarily disable verification (NOT recommended for production)
   git config --global http.sslVerify false
   ```

   Prefer Option A; use Option B only for local or isolated networks and revert when done.

4. **Certificate expiration**:

   - Update system and CA packages (e.g. `apt-get upgrade`, `brew upgrade`)
   - On corporate proxies, ask IT for an updated CA bundle

**Commit pipeline note**: Push happens after the commit is created. If push fails due to SSL (or network) errors, the commit is still saved locally. See [Git operations](./git-operations.md#push-failures-and-ssl) and retry push manually after fixing SSL, or push from another environment.

**Platform-specific**:

- **macOS**: System keychain is used by default; if Git was installed via Homebrew, ensure `brew install openssl` and that Git uses the Homebrew CA path if needed.
- **Linux**: Distribution package `ca-certificates` must be installed and up to date.
- **Windows**: Git for Windows can use the Windows certificate store; set `git config --global http.sslBackend schannel` to use it.

### Quality gate unavailable in environment

When the implement step or commit pipeline runs the quality gate (`execute_pre_commit_checks(checks=["quality"])`), it may fail due to environment issues rather than code issues.

**Symptoms**:

- Tool output reports "ruff not found", "black not found", or similar at expected `.venv` paths
- Type check fails with download or certificate errors (e.g. when downloading a Python build or packages)

**Causes**:

- Dev dependencies (ruff, black, pyright) not installed—e.g. `.venv` created without `uv sync --group dev` or equivalent
- Venv not activated in the environment where the MCP server or checks run
- Network or SSL/certificate problems (e.g. corporate proxy, invalid peer certificate) when the tool tries to download runtimes or packages

**Recommendation**:

- **Documentation-only changes**: If the change set only touches docs (no `src/` or `tests/` code changes), you may treat the quality gate as skipped for that session. Note: "Quality gate skipped - environment (doc-only session); run full pre-commit before commit." Run the full commit pipeline (or pre-commit) in a healthy environment before committing.
- **Code changes**: Fix the environment first (install dev deps, fix SSL/certificate, or run from a shell where `uv sync --group dev` and `uv run black` / `uv run ruff` succeed), then re-run the quality gate and commit pipeline.

**Fixing uv SSL / certificate errors** (e.g. `invalid peer certificate: UnknownIssuer` when running `uv sync` or type check):

- uv uses bundled certificates by default. If you see SSL errors (e.g. when downloading Python builds or packages), use the system certificate store or a custom bundle:
  1. **Point to the system CA bundle** (often fixes the issue on macOS/Linux): set `SSL_CERT_FILE` before running uv. Example (macOS):

     ```bash
     export SSL_CERT_FILE=/etc/ssl/cert.pem
     uv sync
     ```

     On many Linux systems use `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` (or your distro’s CA bundle path).
  2. **Use system TLS** (alternative, e.g. corporate CAs in system store): run uv with `UV_NATIVE_TLS=true` (or `uv --native-tls ...`). You can combine with `SSL_CERT_FILE` if needed:

     ```bash
     export UV_NATIVE_TLS=true
     uv sync
     ```

  3. **CI or custom bundle**: set `SSL_CERT_FILE` to the path of your certificate bundle.
- Ensure your system CA store is up to date (e.g. `brew install ca-certificates` on macOS, or your distro’s `ca-certificates` package). See [Git and SSL certificate issues](#git-and-ssl-certificate-issues).
- To make the fix persistent, add the chosen `export` to your shell profile (e.g. `~/.zshrc`) or use a `.env` file in the project root if your tooling supports it.

See also [Git and SSL certificate issues](#git-and-ssl-certificate-issues) for certificate configuration.

#### Quality gate failed on push (tests or coverage)

When the GitHub Actions "Code Quality" workflow fails on push (e.g. [run #244](https://github.com/igrechuhin/Cortex/actions)) with "Test suite failed" or "One or more quality checks failed", the commit passed local pre-commit but CI failed.

**Symptoms**:

- Push succeeds; GitHub Actions "Code Quality" job fails
- Annotations mention tests step or coverage (e.g. "All tests must pass with at least 90% coverage")

**What to do**:

1. **Run the exact CI test command locally** (from repo root, with same Python/uv as CI):

   ```bash
   uv run python -m pytest tests/ -m "not slow" -n auto -v --cov=src/cortex --cov-report=xml --cov-report=term --cov-fail-under=90
   ```

   Fix any test failures or coverage shortfall before pushing again. The commit pipeline uses the same scope (`-m "not slow"`) and coverage threshold (90%); the Python adapter runs `python -m pytest` for CI parity.

2. **Ensure Step 12 (Final Validation Gate) ran before commit.** If the agent skipped Step 12.7 (tests) due to a connection error or assumed Phase A was enough, that can cause "passed locally, failed in CI". Never commit without Step 12.7 having passed in that run.

3. **Require status checks for merge.** In GitHub: **Settings → Branches → Branch protection** for `main` (and `develop` if used), add a rule that requires the "Code Quality" (or "quality") status check to pass before merging. That prevents merging pushes that failed the quality gate.

**Reference**: The single source of truth for the CI test command is the "Run tests" step in [.github/workflows/quality.yml](../../.github/workflows/quality.yml); the workflow comment at the top of that file repeats the command for local parity.

#### markdownlint-cli2 and npm (fix_markdown_lint)

The `fix_markdown_lint` MCP tool and the commit pipeline require `markdownlint-cli2`. The tool looks for it in this order: (1) local `node_modules/.bin/markdownlint-cli2` (if present), (2) `markdownlint-cli2` in PATH, (3) `npx --yes markdownlint-cli2`.

#### Issue: fix_markdown_lint returns failures without rule codes

**Symptoms**:

- `fix_markdown_lint` returns `success: false` and `files_with_errors: N` (N > 0)
- Each failing file has `"error_message": "Markdown lint failed"` but `"errors": []` (empty list)
- No rule codes (e.g. MD036, MD022) are present in the response
- Agent cannot target fixes without rule codes

**Causes**:

- Batch markdownlint run failed (non-zero exit) and stderr parsing did not extract rule codes
- markdownlint output format differs from expected `file:line:rule` pattern
- Batch failure occurred but per-file error details were not captured

**Solution**:

1. **Retry once**: The tool now includes improved stderr parsing and per-file fallback. Retry `fix_markdown_lint` once—it may succeed on the second attempt.

2. **If retry still returns no rule codes**: Run markdown lint locally to obtain rule codes:

   ```bash
   # From project root
   npx --yes markdownlint-cli2 --fix '**/*.md' '**/*.mdc'
   
   # Or if local install exists
   node_modules/.bin/markdownlint-cli2 --fix '**/*.md' '**/*.mdc'
   ```

3. **Review output**: The local run will show rule codes (e.g. `file.md:15:3 MD036/heading-style`) and file locations.

4. **Fix violations**: Apply fixes based on rule codes, then re-run the commit pipeline.

5. **For commit pipeline**: Record "fix_markdown_lint returned no rule codes; used local markdownlint fallback" in commit output.

**Prevention**:

- The tool now includes improved stderr parsing that handles format variations
- When batch fails, the tool automatically falls back to per-file runs to obtain rule codes
- This should reduce occurrences of "no rule codes" responses

##### Recommended: local install (no global install, avoids npx network at run time)

From the project root:

```bash
npm install
```

This uses the repo’s `package.json` and installs `markdownlint-cli2` into `node_modules/.bin/`. The MCP tool will use that binary when present, so no global install or npx is needed when running lint.

**If `npm install` fails with SSL (e.g. UNABLE_TO_GET_ISSUER_CERT_LOCALLY)**

- Use the system CA bundle (same idea as for Git/uv): set `NODE_EXTRA_CA_CERTS` or `npm config set cafile /path/to/ca-bundle.crt` if you have a custom bundle, or ensure the system CA store is up to date.
- As a last resort in controlled environments only: `npm config set strict-ssl false` (project-only: run in repo root so it writes to `.npmrc` in the project). After `npm install` succeeds, you can remove or revert `.npmrc` if desired. Do not disable strict-ssl in shared or CI config unless required by your network.

##### Alternative: global install

```bash
npm install -g markdownlint-cli2
```

Then the tool will find `markdownlint-cli2` in PATH. If npm hits SSL errors, use the same SSL workarounds as above.

### Refactoring Issues

#### Issue: Refactoring execution fails

**Symptoms**:

```text
RefactoringExecutionError: Failed to execute refactoring consolidation_001
```

**Solution**:

1. Check refactoring status:

   ```json
   {
     "tool": "get_refactoring_history",
     "args": {
       "project_root": "/path/to/project",
       "suggestion_id": "consolidation_001"
     }
   }
   ```

2. Validate suggestion:

   ```json
   {
     "tool": "preview_refactoring",
     "args": {
       "project_root": "/path/to/project",
       "suggestion_id": "consolidation_001"
     }
   }
   ```

3. If validation fails, reject and request new suggestion

#### Issue: Rollback fails

**Symptoms**:

```text
RollbackError: Failed to rollback refactoring split_002
```

**Solution**:

1. Check rollback history:

   ```bash
   cat .memory-bank-rollbacks.json
   ```

2. Manual rollback:

   ```bash
   # Restore from version history
   cp .cortex/history/<snapshot>.md .cortex/memory-bank/file.md
   ```

3. Update metadata:

   ```json
   {
     "tool": "query_memory_bank",
     "args": {
       "query_type": "stats"
     }
   }
   ```

### Refactoring Workflow Best Practices

When fixing quality violations (e.g. function length, file size) by refactoring, follow these practices to reduce fix iterations and avoid type/duplicate errors.

#### Intermediate Validation

Run type check and quality check **after each refactor step**, not only at the end. This catches new violations (e.g. redeclaration, new function length) immediately. See commit prompt Step 3.5 (Intermediate Validation During Refactoring) and implement prompt "Code Quality" (incremental validation). Benefits: fewer pre-commit cycles and faster resolution.

#### Type Narrowing

When control flow guarantees a value is not `None` but the type checker still reports an error, use `assert value is not None` to narrow the type. See [Python coding standards: Type Narrowing with assert](../../.cortex/synapse/rules/python/python-coding-standards.mdc) (Synapse rules). Quick reference:

```python
def process_value(value: int | None) -> int:
    if value is None:
        return 0
    assert value is not None  # Type narrowing for type checker
    return value * 2
```

For type check errors involving `int | None` or similar, see the [Type Narrowing](#type-narrowing) subsection above.

#### Duplicate Detection

Before creating new helper functions during refactoring, search for existing functions with similar names to avoid duplicates (e.g. redeclaration or unused-symbol errors). See commit prompt Step 3.6 (Duplicate Detection Before Creating Helpers) and implement prompt "Code Quality" (duplicate detection). Use the Grep tool or your language’s search to find existing helpers; reuse or rename to avoid duplicate declarations.

For quality check failures during refactoring, see [Intermediate Validation](#intermediate-validation) above.

### Performance Issues

#### Issue: Slow tiktoken initialization

**Symptoms**:

- First token count takes 10-30 seconds
- "Downloading encoding..." message

**Causes**:

- tiktoken downloads encoding files on first use

**Solution**:

This is expected behavior. The encoding is cached after first use:

```python
# First call (slow)
tokens = await token_counter.count_tokens(content)  # 10-30s

# Subsequent calls (fast)
tokens = await token_counter.count_tokens(content)  # <5ms
```

No action needed - performance is normal after initialization.

#### Issue: High memory usage

**Symptoms**:

- Python process using > 1GB RAM
- System slowdown

**Causes**:

- Large file caching
- Multiple project caches

**Solution**:

1. Reduce cache size:

   ```json
   {
     "performance": {
       "max_cache_size_mb": 50
     }
   }
   ```

2. Clear caches:

   ```bash
   # Remove cache files (safe - will regenerate)
   rm -rf ~/.cache/cortex/
   ```

3. Restart MCP server

## Diagnostic Tools

### Check Server Status

```bash
# Test server startup
uv run cortex

# Should see:
# MCP server started successfully
```

### Check Memory Bank Structure

```json
{
  "tool": "query_memory_bank",
  "args": {
    "query_type": "stats"
  }
}
```

Returns:

- File count and sizes
- Token usage
- Version history size
- Metadata status

### Validate Everything

```json
{
  "tool": "validate_memory_bank",
  "args": {
    "project_root": "/path/to/project",
    "fix_issues": false
  }
}
```

Returns:

- Schema validation results
- Link validation results
- Duplication detection results
- Quality score

### Check Structure Health

```json
{
  "tool": "check_structure_health",
  "args": {
    "project_root": "/path/to/project"
  }
}
```

Returns:

- Health score (0-100)
- Required directories status
- Symlink status
- Recommendations

## Logging and Debugging

### Context Logging (Client-Visible Messages)

Cortex uses **Context logging** so the MCP client can show operation progress and errors:

- **Client-visible**: Messages sent via MCP (e.g. "Starting operation", "Completed", warnings, errors) use `log_client(ctx, level, message)` from `cortex.core.context_logging`. These appear in the client UI or logs.
- **Server-only**: Detailed diagnostics use standard Python `logger.debug()` / `logger.info()` and go to stderr only.

If you do not see tool progress in the client:

1. Ensure the client supports MCP log messages (Cursor/Claude Desktop do).
2. Check that tools receive `ctx` (injected by the server); when `ctx` is `None`, messages fall back to stderr.
3. See [Logging Guidelines](../development/logging-guidelines.md) for patterns and levels.

### Enable Debug Logging

Set environment variable:

```bash
# Verbose logging
export CORTEX_LOG_LEVEL=DEBUG

# Run server
uv run cortex
```

### Check Log Files

Logs are written to stderr (captured by MCP client):

```bash
# For standalone testing
uv run cortex 2> debug.log
```

### Inspect Metadata Files

```bash
# View metadata index
cat .memory-bank-index | jq .

# View access log
cat .memory-bank-access-log.json | jq .

# View learning data
cat .memory-bank-learning.json | jq .
```

## Getting Help

### Check Documentation

1. [Getting Started](../getting-started.md)
2. [Configuration Guide](./configuration.md)
3. [Architecture](../architecture.md)
4. [API Reference](../api/tools.md)

### Search Issues

[GitHub Issues](https://github.com/igrechuhin/cortex/issues)

### Create New Issue

Include:

1. **Symptoms**: What's happening?
2. **Expected**: What should happen?
3. **Steps**: How to reproduce?
4. **Environment**: OS, Python version, uv version
5. **Logs**: Relevant error messages

### Community Support

- GitHub Discussions
- MCP Community Discord
