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

- **Docstrings**: Cortex tools already include USE WHEN, EXAMPLES, and RETURNS. For complex tools (`manage_file`, `validate`, `execute_pre_commit_checks`, `suggest_refactoring`, etc.), add concrete **input examples** in the docstring (e.g. "Example inputs" with sample parameter combinations). This improves model accuracy when the model reads the tool description, without requiring SDK support.
- **meta field**: The MCP SDK supports `@mcp.tool(meta={"input_examples": [...]})`. If your MCP client forwards `meta` to Anthropic and Anthropic supports `input_examples` in tool definitions, adding `meta` with example payloads can improve tool selection. Use the same structure as in docstrings (e.g. list of dicts with parameter names and values).

### 2. Tool Search (Defer Loading)

- **Current state**: The MCP SDK does not expose `defer_loading` in tool registration. Lazy or on-demand tool loading would require client-side or server-side custom logic (e.g. listing a subset of tools initially and expanding on request).
- **Tracking**: Monitor MCP spec and Anthropic docs for standard support; consider documenting desired behavior in configuration (e.g. `.cortex/config/optimization.json`) for when support is available.

### 3. Programmatic Tool Calling

- **Current state**: The MCP SDK does not expose `allowed_callers` in the Tool model. Programmatic tool calling (e.g. from a code execution environment) would be handled by the client and Anthropic API.
- **Recommendation**: Document which tool chains are good candidates for code orchestration (e.g. validate → quality → duplications; suggest_refactoring → apply_refactoring) for when client/API support exists.

## Tool Categorization (Phase 49 Step 4)

All 63 Cortex MCP tools are categorized into three loading priority tiers in `src/cortex/tools/tool_categories.py`:

| Tier | Count | Description | Examples |
|------|-------|-------------|----------|
| **always_loaded** | 15 | Core tools used in nearly every session | `manage_file`, `validate`, `load_context`, `execute_pre_commit_checks`, `rules` |
| **deferred_medium** | 26 | Tools for specific workflows (refactoring, analysis, synapse, link ops) | `suggest_refactoring`, `analyze`, `sync_synapse`, `create_plan` |
| **deferred_low** | 22 | Rarely used admin/analytics tools | `rollback_file_version`, `fix_roadmap_corruption`, usage analytics (8 tools), script capture (5 tools) |

### Categorization Rationale

- **always_loaded**: Tools that appear in the implement-prompt workflow, session startup (`load_context`), quality gates (`execute_pre_commit_checks`, `fix_quality_issues`), and memory bank updates (`complete_plan`, `append_progress_entry`, etc.).
- **deferred_medium**: Tools used in specific workflows (plan creation, refactoring, synapse sync, commit pipeline phases) but not every session.
- **deferred_low**: Usage analytics, script capture/promotion, admin operations (rollback, corruption fix, cleanup). These are used infrequently and can be loaded on-demand.

### API

```python
from cortex.tools.tool_categories import (
    get_tool_category,
    get_always_loaded_tool_names,
    get_deferred_tool_names,
    build_category_config,
    get_category_summary,
)

# Look up a single tool
get_tool_category("manage_file")  # ToolCategory.ALWAYS_LOADED

# Get all always-loaded tool names (sorted)
get_always_loaded_tool_names()  # ["add_roadmap_entry", "append_active_context_entry", ...]

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
    "deferred_low": ["rollback_file_version", "get_tool_usage_stats", "..."]
  }
}
```

When `enabled: false` (default), all tools are listed as today. When MCP SDK supports `defer_loading`, setting `enabled: true` will allow the server to list only `always_loaded` tools initially. The **search_tools** MCP tool is always available so clients can discover deferred tools by query (regex over name and rationale).

## Implementation Status

- **Phase 49 Steps 1–3**: Research, feasibility, and tool use examples (`input_examples` on `manage_file`, `validate`) documented and implemented.
- **Phase 49 Step 4**: Tool categorization completed — 63 tools classified into three tiers with Pydantic models, lookup helpers, and comprehensive tests.
- **Phase 49 Step 5**: Tool Search infrastructure — `search_deferred_tools()` (regex over name/rationale), `search_tools` MCP tool (always_loaded), `tool_search` config in optimization default and `OptimizationConfig.get_tool_search_config()`, server comment for deferred loading. Config model `ToolSearchConfigModel` and optional `tool_search` field on `OptimizationConfigModel`.
- **Tool docstrings**: High-value tools include USE WHEN, EXAMPLES, RETURNS; additional input examples are added in docstrings and, where useful, in `meta` for compatible clients.
- **Future**: When MCP or Anthropic standardizes `defer_loading`, Cortex can filter `list_tools` using `get_tool_search_config()` and the categorization in `tool_categories.py`.

## Related Documentation

- [MCP Tool Timeouts](../mcp-tool-timeouts.md) – timeout strategy and constants
- [API Tools](../api/tools.md) – list and description of Cortex MCP tools
