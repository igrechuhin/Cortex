# Plan: Tools-to-Resources Conversion Analysis

**Status**: PENDING
**Priority**: Medium
**Type**: Architecture / MCP protocol alignment
**Effort**: 8–12 hours
**Created**: 2026-03-02

## Goal

Analyze every Cortex MCP tool to determine whether it can be converted to a resource, partially exposed as a resource, or must remain a tool. Produce a per-tool assessment and implementation roadmap.

## Context

### Why Some Operations Are Tools Instead of Resources

Per MCP semantics and [docs/api/tools.md](docs/api/tools.md):

- **Resources** are GET-like: read-only, load data into LLM context, identified by `cortex://` URIs.
- **Tools** are POST-like: side effects (write, update, run), take arbitrary parameters.

Read-only operations (e.g., `check_mcp_connection_health`, `get_structure_info`, `load_context`, `query_usage`, `rules`, `validate`) are exposed as **both tool and resource** for backward compatibility. Phase 43 added resources alongside tools so that:

1. **Client support**: Not all MCP clients support resource fetching; tools remain the primary invocation path.
2. **Parameter complexity**: Resources use URI paths (e.g., `cortex://optimization/load-context/{task_description}`). Complex parameters (e.g., `token_budget`, `strategy`, `depth`) are easier to pass via tool arguments than as URI path segments.
3. **Uniform interface**: Tools provide a single call interface for all clients.

### Conversion Criteria for Resources

A tool can be converted to (or supplemented by) a resource only if:

| Criterion | Requirement |
|-----------|-------------|
| **Read-only** | No side effects (no writes, no state changes) |
| **URI expressibility** | Required parameters can be encoded in a `cortex://{domain}/{path}` URI |
| **Idempotent** | Same inputs produce same output |
| **Stateless** | No session-dependent state beyond what is in the URI |

### User Questions Addressed

- Why are `check_mcp_connection_health`, `rules`, `validate`, `query_usage`, `load_context`, `get_relevance_scores`, `think`, `check_structure_health`, `get_structure_info`, `query_memory_bank` tools?  
  **Answer**: They are tools for client compatibility and parameter flexibility. Many already have corresponding resources; the tool remains as fallback and for complex params.

- Which tools can become resources (or resource-primary)?  
  **Answer**: This plan delivers that analysis.

## Current State

### Tools with Existing Resources (from grep)

| Tool | Resource URI | Notes |
|------|--------------|-------|
| check_mcp_connection_health | cortex://health/connection | No params |
| get_structure_info | cortex://structure/info | No params |
| check_structure_health | cortex://structure/health | Tool has optional params |
| load_context | cortex://optimization/load-context/{task_description} | Default token_budget/strategy/depth |
| get_relevance_scores | cortex://optimization/relevance-scores/{task_description} | Default include_sections |
| validate | cortex://validation/validate/{check_type} | file_name, strict optional |
| rules | cortex://rules/relevant/{task_description}, cortex://synapse/rules/{task} | operation, force vary |
| query_memory_bank | cortex://memory-bank/stats, /dependency-graph, /version-history/{file_name}, /file/{file_name}, cortex://links/parse, validate, graph, transclusions | query_type-driven |
| query_usage | cortex://usage/stats, /unused, /report, /optimization-recommendations, /observation/{id} | query_type-driven |
| manage_file (read) | cortex://memory-bank/file/{file_name} | read only |
| suggest_refactoring | cortex://analysis/suggest-refactoring/{type} | type in URI |
| configure (view) | cortex://config/{component} | view only |
| summarize_content | cortex://optimization/summarize/{file_name} | partial |
| analyze | cortex://analysis/analyze/{target} | target in URI |

### Tools Without Resources (candidates for analysis)

- think
- session
- plan
- roadmap
- append_entry
- execute_pre_commit_checks
- fix_quality_issues
- fix_markdown_lint
- search_tools
- apply_refactoring
- synapse
- run_composite_workflow
- manage_session_scripts
- cleanup_metadata_index
- analyze_error_patterns
- run_tool_evaluation
- benchmark_model

### Tools That Cannot Be Resources (inherent side effects)

- manage_file (write, rollback)
- configure (update)
- roadmap (add/remove entries)
- append_entry
- execute_pre_commit_checks
- fix_quality_issues
- fix_markdown_lint
- apply_refactoring
- synapse (sync, update_rule, update_prompt)
- plan (create, complete, register)
- session (register, deregister, compact)
- manage_session_scripts (capture)
- cleanup_metadata_index
- run_composite_workflow

### Special Case: think

`think` is a **reasoning tool**: it records thoughts and returns state. It is not a data-fetch operation. It has no natural resource equivalent (resources represent fetchable content; think produces incremental reasoning state). **Conclusion**: keep as tool-only.

## Implementation Steps

### Step 1: Full Tool Inventory (2 hours)

1. Enumerate all registered tools from `TOOL_CATEGORIES` and `@mcp.tool` decorators.
2. For each tool, list:
   - Parameters (required, optional)
   - Side effects (none / read metadata / write / subprocess / etc.)
   - Existing resource URI(s) if any
3. Create spreadsheet or markdown table: tool name, params, read-only?, resource exists?, conversion candidate?

**Deliverable**: `tools-resource-inventory.md` in plans or docs.

### Step 2: Per-Tool Conversion Assessment (3–4 hours)

For each tool, apply:

1. **Read-only?** If no → tool-only, skip.
2. **URI expressibility?** Can required params be encoded as path segments? (e.g., `{task_description}`, `{file_name}`, `{check_type}`)
3. **Optional params?** If optional params have sensible defaults, resource can use defaults; document in resource docstring.
4. **Existing resource?** If yes, compare coverage (does resource cover all common cases?); document gaps.
5. **Recommendation**: `resource_only` | `resource_primary_tool_fallback` | `tool_only` | `add_resource_partial`

**Deliverable**: Assessment matrix with rationale per tool.

### Step 3: Gap Analysis for Partial Resources (2 hours)

For tools with complex params (e.g., `load_context`, `query_usage`, `query_memory_bank`):

1. Map each `query_type` or operation to a resource URI pattern.
2. Identify query types / operations that have no resource.
3. Propose new URIs (e.g., `cortex://usage/search?q=...` if supported, or `cortex://usage/report` with defaults).
4. Document client constraints (e.g., URI length limits, query string support).

**Deliverable**: Gap analysis with proposed URIs for uncovered operations.

### Step 4: Migration Strategy (1–2 hours)

1. **Backward compatibility**: Tools remain; resources are additive. No tool removal in this phase.
2. **Documentation**: Update docs/api/tools.md and naming-conventions.md with:
   - When to use resource vs tool (prefer resource when client supports it and params fit).
   - URI reference table for all resources.
3. **Client guidance**: Add "Prefer Resources" section for clients that support `cortex://` fetching.
4. **Deprecation path** (optional, future): For tools that become resource-primary, document deprecation timeline if tool removal is ever considered.

**Deliverable**: Migration strategy document and doc updates.

### Step 5: Implement New Resources (Optional, 2–4 hours)

Based on gap analysis, implement 0–N new resources for high-value, currently uncovered read-only operations. Scope to be decided after Step 3.

**Deliverable**: New resource handlers and tests.

## Success Criteria

- [ ] Full tool inventory with side-effect classification
- [ ] Per-tool conversion assessment (resource_only / resource_primary / tool_only / add_resource_partial)
- [ ] Gap analysis for query-type and operation-based tools
- [ ] Documentation: when to use resource vs tool, URI reference
- [ ] (Optional) New resources for identified gaps

## Testing Strategy

- **Coverage target**: 95% for any new resource handlers
- **Unit tests**: Each new resource returns valid JSON for documented URIs
- **Integration tests**: Resource and tool return equivalent data for same logical request (when both exist)
- **Regression**: All existing resource tests pass

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| URI length limits | Use short path segments; avoid encoding large blobs in URI |
| Client resource support | Keep tools; resources are additive |
| Breaking clients that parse tool names | No tool removal; only additions |

## References

- [docs/api/tools.md](docs/api/tools.md) — Tools vs Resources semantics
- [docs/architecture/naming-conventions.md](docs/architecture/naming-conventions.md) — URI scheme
- Phase 43 plan (archived): `.cortex/plans/archive/Phase43/phase-43-reconsider-tools-registration.md`
- [docs/architecture/naming-inventory-2026-02.md](docs/architecture/naming-inventory-2026-02.md)
