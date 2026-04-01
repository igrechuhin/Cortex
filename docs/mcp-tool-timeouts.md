# MCP Tool Timeout Strategy

## Overview

All Cortex MCP tools are protected with timeout mechanisms to prevent hanging operations and improve system reliability. This document describes the timeout strategy, categories, and how to select appropriate timeouts for new tools.

## Why the first tool call can feel slow

Cortex MCP tools can take noticeable time on the **first** call (or first call after context is cleared) because of one-time setup:

1. **Project root resolution**  
   When `project_root` is not provided, the server asks the client for workspace roots via **roots/list** (see `resolve_project_root_async` in `project_root_resolver.py`). That round-trip is visible in the client log as "ListRootsRequest received" and is bounded by `MCP_ROOTS_LIST_TIMEOUT_SECONDS` (5s).

2. **Manager initialization**  
   The first tool run in a context triggers `get_managers(project_root)`, which:
   - Builds core managers (filesystem, index, token counter, dependency graph, version manager, migration, file watcher)
   - Registers linking, validation, optimization, analysis, refactoring, and execution managers (many as lazy)
   - Runs post-init (e.g. loading the metadata index, cleanup_locks, optional rules init)

   That work is cached in the **usage context** (contextvar). Subsequent tool calls for the **same project root** reuse the same managers and do **not** re-run initialization.

3. **Client-side behavior**  
   The client (e.g. Cursor) may run ListOfferings, GetInstructions, ListToolsRaw (and similar) when opening or refreshing the MCP connection. That is client-side and not controlled by Cortex.

**Optimizations in place:**

- **Reuse current managers**: Tools such as `manage_file` use `get_current_managers()` and `get_current_project_root()` when the requested root matches the context root, avoiding a second `get_managers()` and duplicate initialization.
- **Reuse resolved root**: When the usage context already has a project root (set by the first tool), tools like `manage_file` skip a second **roots/list** round-trip by using `get_current_project_root()`.
- **Deferred rules init**: Rules indexing (which can take tens of seconds) is no longer run during manager startup. It runs on **first use** of the `rules` tool instead, so the first tool call (e.g. `manage_file` read) is no longer blocked by rules indexing.
- **Single init under concurrency**: When several tools are invoked at once (e.g. three `manage_file` reads plus `rules` and `get_structure_info`), only one context setup runs: an init lock in `ensure_usage_context` serializes setup, and a process-scoped manager registry ensures all callers share the same cached managers for that project root. Without this, each concurrent tool would run a full init and total time could be 30+ seconds.

So the "long setup" is effectively **first-call-only** per process and no longer includes rules; later and concurrent calls for the same workspace reuse the same init.

**Why the first tool call can be ~30s even though files are local and small:**  
The server does **not** spend that time reading your files. It first has to resolve the project root. When you don’t pass a root, it asks the **client** (e.g. Cursor) for workspace roots via **roots/list**. The server then **waits for the client to respond**. If the client is slow to handle that request (e.g. due to UI/event loop or other work), the server can sit there for tens of seconds even though everything is local. So the delay is often **client response time** to roots/list, not file I/O or manager init.

**Workaround to confirm:** Set `CORTEX_USE_FALLBACK_ROOT=1` in the environment where the Cortex MCP server runs (e.g. in Cursor’s MCP server config or the shell that starts the server). The server will then **skip** the roots/list request and resolve the project root from the current working directory / script location. If the ~30s delay **disappears**, the bottleneck was the client’s response to roots/list; you can keep the env var set for faster first-tool response or report the slowness to the client (Cursor) team.

**Where the time goes (when not using the workaround):** On first-tool init, the server logs at **INFO** when a step is slow (so you see it without DEBUG):

- `project_root_resolver: list_roots() took X.XXs (client round-trip)` — time waiting for the client to respond to roots/list. If this is ~28s, the bottleneck is the client (Cursor) responding to the roots request.
- `ensure_usage_context: first-tool init took X.XXs (resolve=X.XXs, get_managers=X.XXs)` — total and split: resolve (includes list_roots) vs get_managers (server-side init).
- `get_managers: initialize_managers(...) took X.XXs` — server-side manager init.
- `initialize_managers: _post_init_setup took X.XXs` — index.load() + cleanup_locks().

Check the MCP server’s stderr (or Cursor’s “Output” / MCP logs) for these lines after the first tool call.

**Debug logging (finer detail):** To see where time is spent during the first tool call, set the log level to DEBUG. For example:

- Environment: `LOGLEVEL=DEBUG` or `CORTEX_LOG_LEVEL=DEBUG` (if your runner reads it).
- Or in code: `logging.getLogger("cortex").setLevel(logging.DEBUG)`.

Then look for log lines such as:

- `project_root_resolver: list_roots() took X.XXXs`
- `ensure_usage_context: resolve_project_root_async took X.XXXs`
- `ensure_usage_context: get_managers(...) took X.XXXs`
- `get_managers: registry.get_managers(...) took X.XXXs`
- `initialize_managers: _init_core_managers took X.XXXs`
- `initialize_managers: _post_init_setup took X.XXXs`
- `_post_init_setup: index.load() took X.XXXs`
- `_post_init_setup: cleanup_locks() took X.XXXs`
- `file_operations: reusing current managers` / `file_operations: get_managers(...) took X.XXXs`

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
MCP_TOOL_TIMEOUT_VERY_COMPLEX = 960  # Very complex operations (e.g. full test suite)
MCP_TOOL_TIMEOUT_EXTERNAL = 120     # External operations (30-120s)
MCP_TOOL_TIMEOUT_QUALITY_FIXES = 60  # Quality auto-fix tools (e.g. autofix)
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
- `query_memory_bank` (query_type: parse_links, validate_links, dependency_graph, version_history, link_graph)
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

- `load_context` (including `strategy="progressive"`)
- `query_memory_bank` (query_type: resolve_transclusions)
- `validate`
- `summarize_content`
- `get_relevance_scores`
- `run_quality_gate()` (Phase A preflight)
- `run_docs_gate()` (Phase B docs/memory sync)

### Very Complex Operations (960 seconds / 16 minutes)

**Use for**: Operations that perform comprehensive analysis, refactoring, or large-scale processing (e.g. full test suite in commit pipeline).

**Examples**:

- Refactoring analysis and execution
- Comprehensive analysis operations
- Large-scale file operations
- Rules indexing and retrieval

**Tools using this category**:

- `suggest_refactoring`
- `apply_refactoring`
- `analyze`
- `query_memory_bank` (query_type: stats)
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

- `synapse` (sync, update_rule, update_prompt)
- `get_synapse_rules`
- `get_synapse_prompts`
- `run_quality_gate`
- `autofix`

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
- **Very Complex (960s)**: Comprehensive analysis, refactoring, full test run
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

## Commit pipeline: long-running tools and client timeout

The commit pipeline (e.g. `/cortex/commit`) uses these MCP tools that can run for a long time:

| Tool | Typical duration | Server behavior | Client timeout recommendation |
|------|------------------|-----------------|-------------------------------|
| `run_quality_gate` (Step 12.7: tests inside Phase A) | 300–600 s (driven by `test_timeout` from the pipeline task file, often 300–600) | Very-complex timeout (960 s); frequent progress reports to reduce idle timeout | If the client exposes a tool-call timeout, set it to **≥ test_timeout + buffer** (e.g. 600 + 60 s). Otherwise rely on retry and runbook. |
| `fix_markdown_lint` (Step 12.5) | 30–120 s (depends on repo size; scoped to git-modified when possible) | Batched runs, 5 s heartbeat, progress after each file | Same as above; use local markdownlint for faster runs (see [troubleshooting](guides/troubleshooting.md#issue-mcp-error-32000-connection-closed)). |
| `autofix` (pre-flight / Step 12.1) | 30–120 s | Progress and timeout; serialized with other long tools | Retry once; then use fallback scripts per commit prompt. |

- **Keepalive / progress**: The server sends progress or heartbeat for all of these (see "Tools that need more frequent progress" in `mcp_stability_config` and "Client connection closed during long tools" below). This reduces the chance of client idle timeout (-32000).
- **If Cursor or the MCP client exposes a configurable tool-call timeout**: Set it to at least the longest expected run (e.g. `test_timeout` + 60 s for Step 12.7). For Cursor IDE, community-documented settings (`mcp.server.timeout`, `mcp.elicitation.timeout` in milliseconds) and recommended values are in [Cursor IDE: MCP tool timeout configuration](guides/troubleshooting.md#cursor-ide-mcp-tool-timeout-configuration). If the client does not expose a configurable timeout, the only mitigations are server-side progress and the pipeline retry/fallback behavior; see [MCP disconnect runbook (commit pipeline)](guides/troubleshooting.md#mcp-disconnect-runbook-commit).

## Client connection closed during long tools

Long-running MCP tools may complete on the server after the client has already closed the connection. In that case the transport can raise an error (e.g. `anyio.ClosedResourceError`) and the client may see a message like `{"error":"MCP error -32000: Connection closed"}`. Note: `fix_markdown_lint` now always scopes to git-modified + untracked files (not full-repo), which greatly reduces runtime and the chance of hitting this issue.

- **Meaning**: "Connection closed" in this context usually indicates the client disconnected or timed out, not that the tool failed. The tool may have completed successfully on the server.
- **Server-side mitigations**: To reduce the chance of client idle timeout, the server (1) sends progress more frequently (every 5s instead of 10s) for tools with timeout ≥ 300s, and (2) for `fix_markdown_lint`, reports progress after every file (and after every batch), runs a 5s heartbeat, and processes files in batches of 25 to reduce total duration.
- **Recommendation**: In the commit workflow, when an MCP tool reports "Connection closed" or "ClosedResourceError": (1) Retry the tool once. (2) If it fails again with the same class of error, perform the documented fallback for that step (see commit prompt "Connection Closed During Long Tool") and record "MCP connection closed; fallback used" so the pipeline can proceed.
- **Tool unavailability after disconnect**: After a connection closed error, a retry may fail with "tool not found" or similar (e.g. client/MCP reconnection or tool registration). In that case proceed with the documented fallback for that step (e.g. markdown lint via shell) and do not block the pipeline.

## Resource read timeouts and "unknown message ID"

When the client (e.g. Cursor) fetches many MCP **resources** in parallel (e.g. when opening the MCP resources panel or loading instructions), you may see:

- **`MCP error -32001: Request timed out`** on resource reads (`cortex://structure/health`, `cortex://memory-bank/stats`, `cortex://usage/stats`, etc.)
- **`Request X cancelled - duplicate response suppressed`** in server logs
- **`Received a response for an unknown message ID: Request cancelled`** on the client

**Cause**: The MCP server handles one request at a time over stdio. If a long-running **tool** is executing (e.g. `rules`, `manage_file`, `autofix`), all **ReadResource** requests are queued. The client applies its own timeout (often ~5–10 seconds) per request. Queued resource reads exceed that timeout, so the client cancels them. When the server later sends the response, the client has already discarded that request ID → "unknown message ID" and "duplicate response suppressed".

**Recommendations**:

1. **Prefer tools over resources during commit or long workflows**: Use MCP tools (e.g. `get_structure_info()`, `manage_file()`, `query_memory_bank(query_type="stats")`) instead of reading `cortex://...` resources when running the commit flow or other long operations. Tools are invoked explicitly and are not affected by the client’s parallel resource prefetch.
2. **Avoid resource-heavy UI during long tools**: If the commit prompt or a long tool is running, avoid opening views that trigger many parallel resource reads (e.g. MCP resources panel) until the run completes.
3. **Ignore transient resource errors in logs**: Timeout and "unknown message ID" for resources during or right after a long tool run are expected; they do not indicate a server bug and do not require action.

**Server-side mitigations (Cortex)**:

- **Short-TTL cache for expensive resources**: Cortex caches responses for `cortex://structure/info` and `cortex://structure/health` with a 30-second TTL (`MCP_RESOURCE_CACHE_TTL_SECONDS`). When many ReadResource requests are queued behind a long tool, the first read after the tool completes populates the cache; subsequent reads for the same resource return immediately. This speeds up queue draining and makes later resource panel loads fast. Other heavy resources may get the same treatment in future updates.
- **Stdio is sequential**: The MCP Python SDK over stdio processes one request at a time. The server cannot process ReadResource requests while a tool is running. Concurrency would require a different transport (e.g. HTTP/SSE); for stdio, caching and the recommendations above are the available mitigations. **Optional HTTP/SSE and Streamable HTTP** are supported (see [HTTP/SSE and Streamable HTTP transport](#http-sse-and-streamable-http-transport) and [Deployment and configuration](#deployment-and-configuration)).

## HTTP-SSE and Streamable HTTP transport

Cortex can run with **SSE** or **Streamable HTTP** transport in addition to the default **stdio**. HTTP-based transports allow the server to handle multiple requests concurrently (e.g. ReadResource while a long CallTool runs), which avoids resource read timeouts and "unknown message ID" when clients use a URL to connect.

- **When it helps**: Use HTTP/SSE or Streamable HTTP when you run Cortex as a long-lived server and connect from Cursor (or another client) via URL instead of a shell command. Same tools and resources; only the transport and concurrency behavior change.
- **Analysis and plan**: See [docs/mcp-transport-http-sse-analysis.md](mcp-transport-http-sse-analysis.md) for the design and [.cortex/plans/mcp-transport-http-sse-implementation.md](../.cortex/plans/archive/Transport/mcp-transport-http-sse-implementation.md) for the implementation plan.

### Stdio–Streamable HTTP bridge (one switch, concurrent requests)

To get **concurrent MCP request handling** (e.g. ReadResource while a long tool runs) without running a separate server or changing the Cursor “on/off” flow, use the **bridge**:

- **Command**: Run `python -m cortex.bridge` (or the `cortex-bridge` script) as the Cursor MCP server command instead of `cortex.main`. The bridge starts Cortex with Streamable HTTP on a fixed port and proxies between Cursor (stdio) and Cortex (HTTP).
- **Requirements**: `uv sync --extra server` (or `pip install cortex[server]`). Optional env: `CORTEX_BRIDGE_URL` (default `http://127.0.0.1:8000/mcp`), `CORTEX_MCP_PORT` (default `8000`).
- **Result**: One switch in Cursor; Cortex runs with Streamable HTTP and can handle multiple requests concurrently, reducing resource read timeouts and "unknown message ID" issues.

## Deployment and configuration

### Transport selection (Option C)

- **Environment variables** (optional):
  - `CORTEX_MCP_TRANSPORT`: `stdio`, `sse`, or `streamable-http`. Overrides the default when set.
  - `CORTEX_MCP_PORT`: Port for HTTP transport (e.g. `8000`). When set, values are passed through to the MCP server (e.g. `FASTMCP_PORT`).
  - `CORTEX_MCP_HOST`: Bind address (default `127.0.0.1`). Use `127.0.0.1` or `localhost` for localhost-only; document any use of `0.0.0.0` for your environment.
- **Default (Option C)**: When **port is set**, default transport is **sse** (HTTP/SSE). When **port is unset**, default is **stdio**. Set `CORTEX_MCP_TRANSPORT=stdio` to force stdio even when port is set (e.g. for clients that do not support URL).
- **HTTP transport**: With port set, the server uses SSE by default. To use Streamable HTTP instead, set `CORTEX_MCP_TRANSPORT=streamable-http`. Requires optional dependencies: `uv sync --extra server` or `pip install cortex[server]`.

### Security (Phase 1)

- **Binding**: Server binds to **localhost** (`127.0.0.1`) by default. Do not bind to `0.0.0.0` unless you have appropriate network and auth controls.
- **Optional auth**: The MCP SDK supports optional auth (e.g. query token for SSE URL). See SDK and Cursor docs for URL-based auth if you expose the server beyond localhost.

### Resource read timeouts (-32001)

Error code **-32001** is the standard MCP "Request timed out" response. For **resource** reads it usually means the client gave up before the server responded.

**Root causes**:

1. **Client timeout shorter than server duration**: The client (e.g. IDE) applies a per-request timeout (often 5–30 seconds). If the server handler or queueing delay exceeds that, the client cancels the request and reports -32001.
2. **Queueing behind tools**: Resource reads and tool calls share the same request stream. If five long tools are running (server limit `MCP_MAX_CONCURRENT_TOOLS`), additional resource reads wait in line. By the time the server serves them, the client may have already timed them out.
3. **Slow or heavy handler**: A resource handler that does a lot of work (e.g. scanning many files) can exceed the client timeout even without queueing.

**Server timeout strategy (Phase 69)**:

- **Separate concurrency for resources**: Resource reads use a dedicated semaphore (`MCP_MAX_CONCURRENT_RESOURCES`, default 10) so they do **not** consume tool slots and do **not** queue behind long-running tools. Up to 10 resource reads can run concurrently. This reduces -32001 when the client opens many resources at once (e.g. memory-bank/stats, links/graph, usage/*, scripts/*, synapse/prompts).
- **Per-handler timeouts**: Every resource handler is wrapped with `@mcp_resource_wrapper(timeout=...)` using the same constants as tools (`MCP_TOOL_TIMEOUT_FAST`, `MCP_TOOL_TIMEOUT_MEDIUM`, `MCP_TOOL_TIMEOUT_COMPLEX`). Handlers should complete within that timeout; if a handler routinely exceeds it, optimize the handler or use a higher category.
- **Client timeout unknown**: If the client timeout cannot be determined, the server uses timeouts (60–300s depending on handler) and relies on the separate resource semaphore so resource reads are not delayed by tool execution.

**Guidance**:

- Prefer **tools** over **resources** when you need bulk or structured data during commit or long operations (e.g. `query_memory_bank(query_type="stats")`, `get_structure_info()` instead of reading `cortex://memory-bank/stats`, `cortex://structure/info`).
- Avoid opening many resource-backed views in parallel while a long tool is running; or use the corresponding tools instead.

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
