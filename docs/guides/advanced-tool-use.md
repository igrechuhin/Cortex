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

## Implementation Status

- **Phase 49 Step 1**: Research and feasibility documented in this guide.
- **Tool docstrings**: High-value tools include USE WHEN, EXAMPLES, RETURNS; additional input examples are added in docstrings and, where useful, in `meta` for compatible clients.
- **Future**: When MCP or Anthropic standardizes `input_examples`, `defer_loading`, or `allowed_callers`, Cortex can adopt them via SDK updates or protocol extensions.

## Related Documentation

- [MCP Tool Timeouts](../mcp-tool-timeouts.md) – timeout strategy and constants
- [API Tools](../api/tools.md) – list and description of Cortex MCP tools
