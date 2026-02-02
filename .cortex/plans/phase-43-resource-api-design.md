# Phase 43: Resource API Design (Step 2 Deliverable)

**Status**: Complete  
**Created**: 2026-02-02  
**Plan**: .cortex/plans/phase-43-reconsider-tools-registration.md  
**Audit**: .cortex/plans/phase-43-tool-audit.md

## 1. FastMCP / MCP SDK Resource Support (Step 2.1)

**Verified**: The project uses the official **MCP SDK** (`mcp` package). `FastMCP` from `mcp.server.fastmcp` exposes:

- `mcp.resource(uri, *, name=None, description=None, mime_type=None)` — decorator to register a resource
- `add_resource`, `list_resources`, `list_resource_templates`, `read_resource` — server methods

**Signature** (from runtime inspection):

```text
FastMCP.resource(uri: str, *, name: str | None = None, description: str | None = None, mime_type: str | None = None) -> Callable[[AnyFunction], AnyFunction]
```

**Behavior**:

- The decorated function is called when the resource is read.
- Return types: `str` (text), `bytes` (binary), or other (converted to JSON).
- If the URI contains parameters (e.g. `"resource://{param}"`) or the function has parameters, it is registered as a **template resource**.

**Example** (from SDK):

```python
@server.resource("resource://my-resource")
async def get_data() -> str:
    return "Hello, world!"

@server.resource("resource://{city}/weather")
async def get_weather(city: str) -> str:
    return f"Weather for {city}"
```

**Conclusion**: Resource support is available. Use `mcp.resource(uri=...)` for read-only operations. No separate “FastMCP 2.0” product; the in-repo dependency is the official MCP SDK.

---

## 2. Resource API Pattern (Step 2.2)

### 2.1 Decorator stack (MANDATORY)

Every resource handler MUST use this stack (same order as tools):

1. `@mcp.resource(uri=...)`
2. `@ensure_usage_context`
3. `@mcp_resource_wrapper(timeout=...)`

No resource may be registered without this stack. Verification: add a test or CI check that every `@mcp.resource()`-decorated function is also wrapped with `ensure_usage_context` and `mcp_resource_wrapper` (e.g. by scanning decorator lists or by requiring a single registration helper).

### 2.2 URI scheme

- **Scheme**: `cortex://` to namespace Cortex resources.
- **Patterns**:
  - **Static**: `cortex://memory-bank/stats`, `cortex://structure/info`, `cortex://health/connection`
  - **Template**: `cortex://memory-bank/file/{file_name}` for file reads (when splitting `manage_file` into `get_file` resource and `write_file` tool).

Examples:

| Resource           | URI (static) or template        |
|--------------------|----------------------------------|
| get_memory_bank_stats | `cortex://memory-bank/stats`   |
| get_structure_info | `cortex://structure/info`        |
| get_file (read)    | `cortex://memory-bank/file/{file_name}` |

### 2.3 Response format

- Align with current tool responses where possible: return **JSON-serializable** content.
- Handlers may return `str` (JSON string) or `dict` (FastMCP will serialize to JSON when not str/bytes).
- MIME type: use `mime_type="application/json"` for JSON resources when appropriate.

### 2.4 Naming conventions

- **Resource URIs**: `cortex://<category>/<resource>` or `cortex://<category>/<resource>/{param}`.
- **Handler names**: Match current tool names for clarity (e.g. `get_memory_bank_stats`); the URI is the public identifier for listing/reading.
- **Categories**: `memory-bank`, `structure`, `health`, `links`, `validation`, `optimization`, `analysis`, `synapse`, `config`, `scripts`, `usage` — align with audit tool grouping.

### 2.5 Timeout constants

Reuse existing constants from `cortex.core.constants`:

- `MCP_TOOL_TIMEOUT_FAST` — e.g. health, simple queries
- `MCP_TOOL_TIMEOUT_MEDIUM` — file reads, single validations
- `MCP_TOOL_TIMEOUT_COMPLEX` — analysis, multi-file
- `MCP_TOOL_TIMEOUT_VERY_COMPLEX` — heavy operations
- `MCP_TOOL_TIMEOUT_EXTERNAL` — network/git

Resources use the same timeout categories as the current tools they replace.

---

## 3. Hybrid operation strategy (Step 2.3)

Per audit §3 (phase-43-tool-audit.md):

| Current tool              | Read-only (→ Resource)     | Side effects (→ Tool)   |
|---------------------------|----------------------------|--------------------------|
| `manage_file`             | `get_file` (read/metadata) | `write_file`             |
| `configure`               | `get_config`               | `update_config`          |
| `rules`                   | `get_relevant_rules`       | `index_rules`            |
| `check_structure_health`  | `get_structure_health`     | `repair_structure_health`|

**Approach**: Option A (split). No backward compatibility: do not keep old tool names; clients use new Resource/Tool names.

---

## 4. Backward compatibility (Step 2.4)

**Decision**: No backward compatibility. Clients use new Resource URIs and new Tool names directly. Do not retain `manage_file`, `configure`, `rules`, or `check_structure_health` as aliases.

---

## 5. Resource wrappers and usage tracking (Step 2.5 — MANDATORY)

### 5.1 Current tool stack

- **ensure_usage_context**: Sets `get_current_managers()` so UsageTracker can resolve; enables usage recording.
- **mcp_tool_wrapper(timeout=...)**: Runs handler via `with_mcp_stability` (timeout, semaphore, retry, connection health), then `_record_usage_if_available(tool_name, duration_ms, success, error_type)` and `_handle_tool_exception_if_failure`.

### 5.2 mcp_resource_wrapper

- **Location**: `cortex.core.mcp_stability`
- **Behavior**: Same stability as `mcp_tool_wrapper`: timeout, semaphore, connection check, retry (reuse `with_mcp_stability` and existing retry/health logic). In the “finally” path, call usage recording with **kind=resource** (see below). Do **not** call `_handle_tool_exception_if_failure` for protocol-driven tool failures (that is for tools); resource read failures are still raised as normal exceptions.
- **Signature**: `mcp_resource_wrapper(timeout: float = MCP_TOOL_TIMEOUT_SECONDS) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]`

### 5.3 Usage recording for resources

- **Option A (recommended)**: Extend `_record_usage_if_available` with an optional parameter `kind: Literal["tool", "resource"] = "tool"`. When `kind="resource"`, call a UsageTracker method that records a resource read (same event shape as tool for aggregation, with a way to distinguish).
- **Option B**: Add `record_resource_usage(name, duration_ms, success, error_type)` on UsageTracker; `mcp_resource_wrapper` calls it instead of `_record_usage_if_available`.

**Event model** (Option A): Extend `ToolUsageEvent` (or add a shared event model) with `handler_kind: Literal["tool", "resource"] = "tool"`. Existing events remain valid (default `tool`). Analytics (`get_tool_usage_stats`, `get_unused_tools`, `get_optimization_recommendations`) include both tools and resources; reporting can filter or group by `handler_kind`.

**Naming**: Record resource reads under the same logical name as the handler (e.g. `get_memory_bank_stats`) so “tool” usage stats and “resource” usage stats can be merged or shown separately by `handler_kind`.

### 5.4 Analytics inclusion

- `get_tool_usage_stats`: Include resource reads (events with `handler_kind="resource"`). Optionally expose a breakdown by tool vs resource.
- `get_unused_tools`: Consider “handlers” (tools + resources) so unused resources are also reported.
- `get_optimization_recommendations`: Include resource usage in recommendations.

Implementation detail: extend `UsageTracker.record_tool_usage` to accept optional `handler_kind`, or add `record_resource_usage` that persists an event with `handler_kind="resource"`. Use the same persistence and aggregation path so one code path serves both.

---

## 6. Implementation checklist (Step 3 prep)

1. **mcp_stability.py**
   - Add `mcp_resource_wrapper(timeout=...)` that uses `with_mcp_stability` and records usage with `kind="resource"`.
   - Extend `_record_usage_if_available(..., kind="tool"|"resource")` and wire resource wrapper to `kind="resource"`.

2. **usage_models.py**
   - Add `handler_kind: Literal["tool", "resource"] = "tool"` to `ToolUsageEvent` (or equivalent) for analytics.

3. **usage_tracker.py**
   - Support recording with `handler_kind` (e.g. extend `record_tool_usage` or add `record_resource_usage` that writes `handler_kind="resource"`).

4. **usage_analytics tools**
   - Ensure `get_tool_usage_stats`, `get_unused_tools`, `get_optimization_recommendations` include resource events (and optionally expose tool vs resource breakdown).

5. **Verification**
   - Add test or CI check: every `@mcp.resource()` handler has `@ensure_usage_context` and `@mcp_resource_wrapper(timeout=...)`.

6. **Pilot resources (Step 3)**
   - Implement 1–2 pilot resources (e.g. `get_memory_bank_stats`, `get_structure_info`) with the full stack and URI scheme above, then migrate remaining read-only tools.

---

## 7. References

- Plan: .cortex/plans/phase-43-reconsider-tools-registration.md
- Audit: .cortex/plans/phase-43-tool-audit.md (§4 FastMCP Resource Support, §5 Resource Wrappers and Usage Tracking)
- Current tool stack: `src/cortex/core/mcp_stability.py` (`mcp_tool_wrapper`, `ensure_usage_context`, `_record_usage_if_available`), `src/cortex/tools/phase1_foundation_stats.py` (example tool)
- Usage: `src/cortex/managers/usage_tracker.py`, `src/cortex/managers/usage_models.py`
