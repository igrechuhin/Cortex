# Advanced Tool Use (Anthropic)

## Overview

This guide documents research and recommendations for using Anthropic's advanced tool use features (November 2025) with Cortex MCP tools: Tool Use Examples, Tool Search (defer loading), and Programmatic Tool Calling.

**Reference**: [Anthropic Engineering – Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

## Research Findings (Phase 49)

### MCP SDK Support

Cortex uses the official **MCP SDK** (`mcp` package, `mcp.server.fastmcp.FastMCP`). As of the current SDK version:

- **`mcp.tool()` decorator parameters**: `name`, `title`, `description`, `annotations`, `icons`, `meta`, `structured_output`. There are **no** `input_examples`, `defer_loading`, or `allowed_callers` parameters in the decorator.
- **`Tool` model fields** (MCP protocol): `name`, `title`, `description`, `inputSchema`, `outputSchema`, `icons`, `annotations`, `meta`, `execution`. The protocol does not define top-level `input_examples`, `defer_loading`, or `allowed_callers`; these are **Anthropic API** concepts.

### Anthropic Features vs MCP

| Feature | Anthropic API | MCP SDK / Protocol |
|--------|----------------|---------------------|
| Tool Use Examples | `input_examples` in tool definition | Not in Tool model; can be placed in **meta** for client forwarding |
| Tool Search | `defer_loading: true` | Not in SDK; client/server config may support lazy tool listing |
| Programmatic Tool Calling | `allowed_callers: ["code_execution_20250825"]` | Not in Tool model |

### Compatibility and Beta

- **Claude API**: Advanced tool use may require beta access (e.g. `betas=["advanced-tool-use-2025-11-20"]`). Check Anthropic documentation for current requirements.
- **MCP clients**: Cursor and other MCP clients that forward tool definitions to Anthropic may inject or interpret `meta` (e.g. `input_examples`) when calling the API. Behavior is client-dependent.

## Recommendations

### 1. Tool Use Examples (Accuracy)

- **Docstrings**: Cortex tools already include USE WHEN, EXAMPLES, and RETURNS. For complex tools (`manage_file`, `validate`, `run_quality_gate`, `suggest_refactoring`, etc.), add concrete **input examples** in the docstring (e.g. "Example inputs" with sample parameter combinations). This improves model accuracy when the model reads the tool description, without requiring SDK support.
- **meta field**: The MCP SDK supports `@mcp.tool(meta={"input_examples": [...]})`. If your MCP client forwards `meta` to Anthropic and Anthropic supports `input_examples` in tool definitions, adding `meta` with example payloads can improve tool selection. Use the same structure as in docstrings (e.g. list of dicts with parameter names and values).

### 2. Tool Search (Defer Loading)

- **Current state**: The MCP SDK does not expose `defer_loading` in tool registration. Lazy or on-demand tool loading would require client-side or server-side custom logic (e.g. listing a subset of tools initially and expanding on request).
- **Tracking**: Monitor MCP spec and Anthropic docs for standard support; consider documenting desired behavior in configuration (e.g. `.cortex/config/optimization.json`) for when support is available.

### 3. Programmatic Tool Calling

- **Current state**: The MCP SDK does not expose `allowed_callers` in the Tool model. Programmatic tool calling (e.g. from a code execution environment) would be handled by the client and Anthropic API.
- **Recommendation**: Document which tool chains are good candidates for code orchestration (e.g. validate → quality → duplications; suggest_refactoring → apply_refactoring) for when client/API support exists.

## Tool Categorization (Phase 49 Step 4)

All 63 Cortex MCP tools are categorized into three loading priority tiers in `src/cortex/tools/categories.py`:

| Tier | Count | Description | Examples |
|------|-------|-------------|----------|
| **always_loaded** | 15 | Core tools used in nearly every session | `manage_file`, `validate`, `load_context`, `run_quality_gate`, `rules` |
| **deferred_medium** | 26 | Tools for specific workflows (refactoring, analysis, synapse, link ops) | `suggest_refactoring`, `analyze`, `sync_synapse`, `create_plan` |
| **deferred_low** | 22 | Rarely used admin/analytics tools | `rollback_file_version`, `fix_roadmap_corruption`, usage analytics (8 tools), script capture (5 tools) |

### Categorization Rationale

- **always_loaded**: Tools that appear in the implement-prompt workflow, session startup (`load_context`), quality gates (`run_quality_gate`, `fix_quality_issues`), and memory bank updates (`complete_plan`, `append_entry`, etc.).
- **deferred_medium**: Tools used in specific workflows (plan creation, refactoring, synapse sync, commit pipeline phases) but not every session.
- **deferred_low**: Usage analytics, script capture/promotion, admin operations (rollback, corruption fix, cleanup). These are used infrequently and can be loaded on-demand.

### API

```python
from cortex.tools.structure.categories import (
    get_tool_category,
    get_always_loaded_tool_names,
    get_deferred_tool_names,
    build_category_config,
    get_category_summary,
)

# Look up a single tool
get_tool_category("manage_file")  # ToolCategory.ALWAYS_LOADED

# Get all always-loaded tool names (sorted)
get_always_loaded_tool_names()  # ["roadmap", "append_entry", ...]

# Build config for optimization.json
config = build_category_config()
config.model_dump()  # {"enabled": False, "always_loaded": [...], ...}

# Summary counts
get_category_summary()  # {"always_loaded": 15, "deferred_medium": 26, "deferred_low": 22}
```

### Configuration

The `tool_search` section is part of the optimization config default (Phase 49 Step 5). It is merged from defaults when loading `.cortex/config/optimization.json`; you can override it in that file:

```json
{
  "tool_search": {
    "enabled": false,
    "always_loaded": ["manage_file", "validate", "load_context", "..."],
    "deferred_medium": ["suggest_refactoring", "analyze", "..."],
    "deferred_low": ["rollback_file_version", "query_usage", "..."]
  }
}
```

When `enabled: false` (default), all tools are listed as today. When MCP SDK supports `defer_loading`, setting `enabled: true` will allow the server to list only `always_loaded` tools initially. The **search_tools** MCP tool is always available so clients can discover deferred tools by query (regex over name and rationale).

### Tool Search - Configuration options and testing (Phase 49 Step 6)

| Option | Type | Description |
|--------|------|-------------|
| `enabled` | boolean | When `true`, only `always_loaded` tools are listed initially (once MCP supports `defer_loading`). Default: `false`. |
| `always_loaded` | list of strings | Tool names loaded in every session (file ops, validate, load_context, quality gates, memory bank helpers, search_tools). |
| `deferred_medium` | list of strings | Tools for specific workflows (refactoring, analysis, synapse, plans); discoverable via `search_tools`. |
| `deferred_low` | list of strings | Rarely used tools (analytics, script capture, admin); discoverable via `search_tools`. |

**Reading config:** Use `OptimizationConfig(project_root).get_tool_search_config()` to get the current tool_search dict (or canonical defaults if the key is missing). Use `build_category_config()` from `cortex.tools.structure.categories` for the canonical list without loading the file.

**Token savings:** When deferred loading is enabled, initial tool list size equals `len(always_loaded)` instead of all tools; the difference is the number of tools loaded on demand via `search_tools`. Tests in `tests/tools/test_tool_search_operations.py` and `tests/unit/test_optimization_config.py` assert `always_loaded < total` so that when `defer_loading` is implemented, token savings are realized.

**Tool frequency and token impact (Step 6):** Use `query_usage(query_type="tool_frequency", days=30)` to see tools by session presence (core ≥80%, medium 10–80%, rare &lt;10%) and `token_impact.reduction_pct_when_tiered` — the estimated reduction in initial context tokens when only tier1 tools are sent. With current tiers, this is typically ≥15%.

**Verifying tool discovery:** Call the **search_tools** MCP tool with a query (e.g. `query="refactor"`, `query="usage"`, `category="deferred_low"`). Results are only from deferred tiers; always_loaded tools are not in the search index. Unit tests assert that search results are a subset of deferred tools and disjoint from always_loaded.

## Programmatic Tool Calling – Orchestration Analysis (Phase 49 Step 7)

When Anthropic API and MCP clients support `allowed_callers: ["code_execution_20250825"]`, Claude can orchestrate multiple tool calls from a single code block, reducing token use and inference passes. This section documents tool chains suitable for code orchestration and which tools are candidates for `allowed_callers`.

### Tool chains suitable for code orchestration

| Workflow | Tools | Pattern |
|----------|--------|--------|
| **Validation** | `validate` | Run multiple `check_type` values in sequence: `schema` → `quality` → `duplications` (optionally `infrastructure`, `timestamps`, `roadmap_sync`). Single tool, different parameters per call. |
| **Refactoring** | `suggest_refactoring`, `apply_refactoring` | 1) `suggest_refactoring(type="consolidation" \| "splits" \| "reorganization")` to get suggestions; 2) `apply_refactoring(action="approve")` then `apply_refactoring(action="apply")`. No separate preview tool—suggest returns suggestions; apply handles approve/apply/rollback. |
| **Batch file operations** | `manage_file` | Multiple calls with `operation="read"` or `operation="write"` (or `metadata`) for different `file_name` and optional `content` / `sections`. Same tool, loop over files. |

### Validation workflow detail

- **Tool**: `validate` (single MCP tool).
- **Check types** (from `ValidationCheckType`): `schema`, `duplications`, `quality`, `infrastructure`, `timestamps`, `roadmap_sync`.
- **Orchestration**: In code, call `validate(check_type="schema", ...)`, then `validate(check_type="quality", ...)`, then `validate(check_type="duplications", ...)` (and optionally others). Each call returns JSON; aggregate or short-circuit on failure as needed.

### Refactoring workflow detail

- **Tools**: `suggest_refactoring`, `apply_refactoring`.
- **Flow**: `suggest_refactoring(type=...)` → inspect result → `apply_refactoring(action="approve")` → `apply_refactoring(action="apply")`. Rollback via `apply_refactoring(action="rollback")`.
- **Types for suggest**: `consolidation`, `splits`, `reorganization`.

### Batch file operations detail

- **Tool**: `manage_file`.
- **Orchestration**: Loop over a list of `(file_name, operation, content?)` and call `manage_file(file_name=..., operation="read"|"write"|"metadata", ...)` per item. Use for bulk read (e.g. all memory bank files) or bulk write (e.g. apply template to several files).

### Tools recommended for `allowed_callers`

When the API supports it, the following tools are the best candidates for `allowed_callers: ["code_execution_20250825"]` so Claude can orchestrate them from code:

| Tool | Rationale |
|------|-----------|
| `validate` | Validation workflow often runs schema → quality → duplications (and more) in one logical step; one code block can issue multiple `validate` calls. |
| `suggest_refactoring` | Always used in a chain with `apply_refactoring`; code can call suggest then approve/apply. |
| `apply_refactoring` | Used after `suggest_refactoring`; same code block can run approve then apply. |
| `manage_file` | Batch reads or writes (e.g. all memory bank files, or multi-file updates) are natural in a loop in one code block. |

Other tools (e.g. `load_context`, `run_quality_gate`, `rules`) are typically used once per step or with branching; they benefit less from code orchestration and can remain non-code-callable unless a concrete multi-call pattern emerges.

### Implementation note

The MCP SDK does not expose `allowed_callers` as a top-level Tool field. Cortex adds it via **tool `meta`** (e.g. `@mcp.tool(meta={"allowed_callers": ["code_execution_20250825"]})`) so that compatible clients can forward it to the Anthropic API. The four tools above have `allowed_callers` in their meta (Phase 49 Step 8).

## Usage Guide

### Using Tool Use Examples

- **Docstrings**: All complex tools (e.g. `manage_file`, `validate`) document USE WHEN, EXAMPLES, and RETURNS. Use these when prompting the model so it sees concrete parameter combinations.
- **meta.input_examples**: If your MCP client forwards tool `meta` to the Anthropic API and you have advanced-tool-use beta, the server already sends `input_examples` for `manage_file` and `validate`. No client configuration needed beyond using a Claude model that supports input examples.

### Using Tool Search

1. **Configuration**: In `.cortex/config/optimization.json`, set `tool_search.enabled` to `true` when your client and MCP stack support deferring tool loading. Default is `false` (all tools listed).
2. **Discovery**: Call the **search_tools** MCP tool with `query` (regex over name and rationale) and optional `category` (`deferred_medium` or `deferred_low`) to discover tools not in the initial list. Example: `search_tools(query="refactor", limit=10)`.
3. **Always-available**: `search_tools` is in the always_loaded set so it is available even when deferred loading is enabled.

### Using Programmatic Tool Calling

When your client and the Anthropic API support code execution with `allowed_callers`:

1. **Eligible tools**: `validate`, `suggest_refactoring`, `apply_refactoring`, `manage_file` expose `allowed_callers` in tool `meta`. The client must forward this meta to the API.
2. **Workflows**: Use one code block to run multiple tool calls (e.g. `validate(check_type="schema")` then `validate(check_type="quality")`, or `suggest_refactoring(type="consolidation")` then `apply_refactoring(action="approve")` and `apply_refactoring(action="apply")`). See the orchestration tables above for patterns.

## Measuring Improvements

- **Token usage**: Compare initial tool list size (e.g. number of tools × average tokens per tool) with always_loaded-only when `tool_search.enabled` is true. Current tests assert `always_loaded < total` so deferred loading yields fewer tools sent upfront. For end-to-end token counts, use Claude API usage metrics before/after enabling Tool Search or Programmatic Tool Calling.
- **Accuracy**: Run manual evaluations with Claude on tasks that require complex parameters (e.g. `manage_file` with `sections`, `validate` with multiple `check_type` values). Compare success rate or parameter correctness before and after adding input_examples or enabling advanced features.
- **Workflow efficiency**: For programmatic tool calling, measure end-to-end latency or number of inference steps for multi-tool workflows (e.g. validation chain, refactor suggest → apply). Future automation could run a fixed task suite and record token usage and step count.

## Implementation Status

- **Phase 49 Steps 1–3**: Research, feasibility, and tool use examples (`input_examples` on `manage_file`, `validate`) documented and implemented.
- **Phase 49 Step 4**: Tool categorization completed — 63 tools classified into three tiers with Pydantic models, lookup helpers, and comprehensive tests.
- **Phase 49 Step 5**: Tool Search infrastructure — `search_deferred_tools()` (regex over name/rationale), `search_tools` MCP tool (always_loaded), `tool_search` config in optimization default and `OptimizationConfig.get_tool_search_config()`, server comment for deferred loading. Config model `ToolSearchConfigModel` and optional `tool_search` field on `OptimizationConfigModel`.
- **Phase 49 Step 6**: Tool Search testing — token savings potential tests (`always_loaded` &lt; total), tool discovery tests (search_tools returns only deferred tools), `get_tool_search_config()` tests, and configuration options documented in this guide.
- **Phase 49 Step 7**: Programmatic Tool Calling analysis — tool chains identified (validation, refactoring, batch manage_file); tools recommended for `allowed_callers` (validate, suggest_refactoring, apply_refactoring, manage_file); orchestration patterns documented in this guide.
- **Phase 49 Step 8**: Programmatic Tool Calling implementation — `allowed_callers` added to tool `meta` for validate, suggest_refactoring, apply_refactoring, and manage_file. Constant `ALLOWED_CALLERS_CODE_EXECUTION` and list `TOOLS_WITH_ALLOWED_CALLERS` in `categories.py`; clients can forward meta to the API for code-execution orchestration.
- **Tool docstrings**: High-value tools include USE WHEN, EXAMPLES, RETURNS; additional input examples are added in docstrings and, where useful, in `meta` for compatible clients.
- **Future**: When MCP or Anthropic standardizes `defer_loading`, Cortex can filter `list_tools` using `get_tool_search_config()` and the categorization in `categories.py`.
- **Phase 49 Step 9**: Documentation and testing — API tools reference ([tools.md](../api/tools.md)) updated with Advanced Tool Use subsection; usage guide and measuring-improvements sections added to this guide; comprehensive tests extended (input_examples minimum count, allowed_callers category consistency, search_tools always_loaded).

## Related Documentation

- [MCP Tool Timeouts](../mcp-tool-timeouts.md) – timeout strategy and constants
- [API Tools](../api/tools.md) – list and description of Cortex MCP tools
