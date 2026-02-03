# MCP Tool Timeout Strategy

## Overview

All Cortex MCP tools are protected with timeout mechanisms to prevent hanging operations and improve system reliability. This document describes the timeout strategy, categories, and how to select appropriate timeouts for new tools.

## Timeout Infrastructure

### Centralized Timeout Mechanism

All MCP tools use the `@mcp_tool_wrapper(timeout=...)` decorator from `cortex.core.mcp_stability` to add timeout protection. This provides:

- **Timeout enforcement**: Operations that exceed their timeout are automatically cancelled
- **Resource limits**: Concurrent operations are limited to prevent resource exhaustion
- **Connection stability**: Connection health checks and recovery mechanisms
- **Clear error messages**: Timeout errors provide actionable information

### Timeout Constants

Timeout values are defined in `cortex.core.constants`:

```python
MCP_TOOL_TIMEOUT_FAST = 60          # Fast operations (30-60s)
MCP_TOOL_TIMEOUT_MEDIUM = 120        # Medium operations (60-120s)
MCP_TOOL_TIMEOUT_COMPLEX = 300      # Complex operations (120-300s)
MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600  # Very complex operations (300-600s)
MCP_TOOL_TIMEOUT_EXTERNAL = 120     # External operations (30-120s)
MCP_TOOL_TIMEOUT_QUALITY_FIXES = 60  # Quality auto-fix tools (e.g. fix_quality_issues)
```

## Timeout Categories

### Fast Operations (60 seconds)

**Use for**: Simple, quick operations that should complete in under a minute.

**Examples**:

- Simple file reads/writes
- Metadata queries
- Configuration operations
- Health checks
- Structure information retrieval

**Tools using this category**:

- `check_mcp_connection_health`
- `check_structure_health`
- `get_structure_info`
- `configure`

### Medium Operations (120 seconds)

**Use for**: Operations that involve validation, parsing, or moderate file processing.

**Examples**:

- File operations with validation
- Link parsing and validation
- Dependency graph construction
- Version history queries
- Metadata cleanup

**Tools using this category**:

- `manage_file`
- `parse_file_links`
- `validate_links`
- `get_dependency_graph`
- `get_version_history`
- `get_link_graph`
- `rollback_file_version`
- `cleanup_metadata_index`
- `fix_roadmap_corruption`

### Complex Operations (300 seconds / 5 minutes)

**Use for**: Operations that process multiple files, perform complex analysis, or involve significant computation.

**Examples**:

- Context optimization
- Progressive loading
- Transclusion resolution
- Validation across all files
- Content summarization
- Relevance scoring

**Tools using this category**:

- `load_context`
- `load_progressive_context`
- `resolve_transclusions`
- `validate`
- `summarize_content`
- `get_relevance_scores`

### Very Complex Operations (600 seconds / 10 minutes)

**Use for**: Operations that perform comprehensive analysis, refactoring, or large-scale processing.

**Examples**:

- Refactoring analysis and execution
- Comprehensive analysis operations
- Large-scale file operations
- Rules indexing and retrieval

**Tools using this category**:

- `suggest_refactoring`
- `apply_refactoring`
- `analyze`
- `get_memory_bank_stats`
- `provide_feedback`
- `rules`

### External Operations (120 seconds)

**Use for**: Operations that interact with external systems, run commands, or perform network requests.

**Examples**:

- Git operations
- External command execution
- Network requests
- Pre-commit checks

**Tools using this category**:

- `sync_synapse`
- `update_synapse_rule`
- `update_synapse_prompt`
- `get_synapse_rules`
- `get_synapse_prompts`
- `execute_pre_commit_checks`
- `fix_quality_issues`

## How to Add Timeout to a New Tool

### Step 1: Import Required Modules

```python
from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM  # or appropriate category
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp
```

### Step 2: Apply Required Decorator Stack

Every MCP tool MUST use this decorator stack in order (CI enforces it):

1. `@mcp.tool()`
2. `@ensure_usage_context` — enables usage recording for analytics
3. `@mcp_tool_wrapper(timeout=...)` — timeout and stability

```python
@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def my_new_tool(...) -> str:
    """Tool description."""
    # Tool implementation
    ...
```

### Step 3: Select Appropriate Timeout

Choose the timeout category based on operation complexity:

- **Fast (60s)**: Simple queries, health checks, config operations
- **Medium (120s)**: File operations, parsing, validation
- **Complex (300s)**: Multi-file processing, optimization, analysis
- **Very Complex (600s)**: Comprehensive analysis, refactoring
- **External (120s)**: Git, commands, network requests

## Internal Operations

For internal async operations (not MCP tools), use `asyncio.timeout()` with constants from `cortex.core.constants` (Python 3.11+):

```python
from cortex.core.constants import GIT_OPERATION_TIMEOUT_SECONDS

async def _run_git_command(cmd: list[str]) -> dict[str, object]:
    async with asyncio.timeout(GIT_OPERATION_TIMEOUT_SECONDS):
        process = await asyncio.create_subprocess_exec(*cmd, ...)
        stdout, stderr = await process.communicate()
    ...
```

## Timeout Behavior

### Successful Completion

When an operation completes within its timeout:

- Result is returned normally
- No timeout error is raised
- Connection health is maintained

### Timeout Exceeded

When an operation exceeds its timeout:

- `TimeoutError` is raised with clear message
- Operation is cancelled automatically
- Connection health is checked
- Error message includes timeout value and operation name

### Error Messages

Timeout errors follow this format:

```text
MCP tool <tool_name> exceeded timeout of <timeout>s
```

## Client connection closed during long tools

Long-running MCP tools (e.g. `fix_markdown_lint(check_all_files=True)` with many files) may complete on the server after the client has already closed the connection. In that case the transport can raise an error (e.g. `anyio.ClosedResourceError`) and the client may see a message like `{"error":"MCP error -32000: Connection closed"}`.

- **Meaning**: "Connection closed" in this context usually indicates the client disconnected or timed out, not that the tool failed. The tool may have completed successfully on the server.
- **Server-side mitigations**: To reduce the chance of client idle timeout, the server (1) sends progress more frequently (every 5s instead of 10s) for tools with timeout ≥ 300s, and (2) for `fix_markdown_lint`, reports progress at start (0%) then every 3 files so the connection sees activity during long runs.
- **Recommendation**: In the commit workflow, when an MCP tool reports "Connection closed" or "ClosedResourceError": (1) Retry the tool once. (2) If it fails again with the same class of error, perform the documented fallback for that step (see commit prompt "Connection Closed During Long Tool") and record "MCP connection closed; fallback used" so the pipeline can proceed.
- **Tool unavailability after disconnect**: After a connection closed error, a retry may fail with "tool not found" or similar (e.g. client/MCP reconnection or tool registration). In that case proceed with the documented fallback for that step (e.g. markdown lint via shell) and do not block the pipeline.

## Resource read timeouts and "unknown message ID"

When the client (e.g. Cursor) fetches many MCP **resources** in parallel (e.g. when opening the MCP resources panel or loading instructions), you may see:

- **`MCP error -32001: Request timed out`** on resource reads (`cortex://structure/health`, `cortex://memory-bank/stats`, `cortex://usage/stats`, etc.)
- **`Request X cancelled - duplicate response suppressed`** in server logs
- **`Received a response for an unknown message ID: Request cancelled`** on the client

**Cause**: The MCP server handles one request at a time over stdio. If a long-running **tool** is executing (e.g. `rules`, `manage_file`, `fix_quality_issues`), all **ReadResource** requests are queued. The client applies its own timeout (often ~5–10 seconds) per request. Queued resource reads exceed that timeout, so the client cancels them. When the server later sends the response, the client has already discarded that request ID → "unknown message ID" and "duplicate response suppressed".

**Recommendations**:

1. **Prefer tools over resources during commit or long workflows**: Use MCP tools (e.g. `get_structure_info()`, `manage_file()`, `get_memory_bank_stats()`) instead of reading `cortex://...` resources when running the commit flow or other long operations. Tools are invoked explicitly and are not affected by the client’s parallel resource prefetch.
2. **Avoid resource-heavy UI during long tools**: If the commit prompt or a long tool is running, avoid opening views that trigger many parallel resource reads (e.g. MCP resources panel) until the run completes.
3. **Ignore transient resource errors in logs**: Timeout and "unknown message ID" for resources during or right after a long tool run are expected; they do not indicate a server bug and do not require action.

**Server-side mitigations (Cortex)**:

- **Short-TTL cache for expensive resources**: Cortex caches responses for `cortex://structure/info` and `cortex://structure/health` with a 30-second TTL (`MCP_RESOURCE_CACHE_TTL_SECONDS`). When many ReadResource requests are queued behind a long tool, the first read after the tool completes populates the cache; subsequent reads for the same resource return immediately. This speeds up queue draining and makes later resource panel loads fast. Other heavy resources may get the same treatment in future updates.
- **Stdio is sequential**: The MCP Python SDK over stdio processes one request at a time. The server cannot process ReadResource requests while a tool is running. Concurrency would require a different transport (e.g. HTTP/SSE); for stdio, caching and the recommendations above are the available mitigations.

## Troubleshooting

### Tool Times Out Prematurely

**Symptoms**: Tool fails with `TimeoutError` even for simple operations.

**Solutions**:

1. Check if timeout value is appropriate for operation complexity
2. Verify operation isn't blocking on I/O unnecessarily
3. Consider increasing timeout if operation legitimately needs more time
4. Check for infinite loops or deadlocks in operation logic

### Tool Hangs Despite Timeout

**Symptoms**: Tool hangs indefinitely even with timeout wrapper.

**Possible Causes**:

1. Operation is blocking event loop (synchronous I/O)
2. Timeout wrapper not applied correctly
3. Operation is in infinite loop before timeout check

**Solutions**:

1. Ensure all I/O operations are async
2. Verify `@mcp_tool_wrapper()` is applied correctly
3. Check operation logic for infinite loops
4. Use `asyncio.timeout()` for internal async operations

### Timeout Value Too Long

**Symptoms**: Tools take too long to fail, poor user experience.

**Solutions**:

1. Review timeout category selection
2. Consider if operation can be optimized
3. Break large operations into smaller chunks
4. Use progressive loading for large datasets

## Best Practices

1. **Always use full decorator stack**: Every `@mcp.tool()` must have `@ensure_usage_context` then `@mcp_tool_wrapper(timeout=...)` (in that order)
2. **Choose appropriate category**: Match timeout to operation complexity
3. **Use constants**: Never hardcode timeout values, use constants from `cortex.core.constants`
4. **Test timeout behavior**: Verify tools timeout correctly in tests
5. **Document timeout selection**: Add comments explaining why a specific timeout was chosen
6. **Monitor timeout errors**: Track timeout frequency to optimize timeout values

## Verification

To verify all tools have the required decorator stack:

```bash
# Run the enforcement test (required stack: @mcp.tool -> @ensure_usage_context -> @mcp_tool_wrapper)
./.venv/bin/python -m pytest tests/unit/test_mcp_stability_timeouts.py::TestAllToolsHaveTimeoutWrapper::test_every_mcp_tool_has_required_wrappers -v

# Count tools without timeout wrapper
find src/cortex/tools -name "*.py" -exec grep -l "@mcp.tool()" {} \; | wc -l

# These counts should match
```

## Related Documentation

- `cortex.core.mcp_stability`: Timeout implementation details
- `cortex.core.constants`: Timeout constant definitions
- Phase 34 Plan: Implementation details and rationale
