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

This is **not an error** - the server handles client disconnections gracefully. When you see this in logs:

1. **Normal behavior**: Server exits cleanly with exit code 0
2. **No action needed**: Reconnect the client to restart the server
3. **If persistent**: Check client configuration or network stability

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

- Progress and heartbeat for long tools (e.g. 2 s heartbeat and wrapper progress for `fix_markdown_lint`, frequent progress for `execute_pre_commit_checks`).
- Automatic retry for connection errors in the tool wrapper (one retry).
- Batched markdown lint to reduce total duration.

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

#### markdownlint-cli2 and npm (fix_markdown_lint)

The `fix_markdown_lint` MCP tool and the commit pipeline require `markdownlint-cli2`. The tool looks for it in this order: (1) local `node_modules/.bin/markdownlint-cli2` (if present), (2) `markdownlint-cli2` in PATH, (3) `npx --yes markdownlint-cli2`.

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
