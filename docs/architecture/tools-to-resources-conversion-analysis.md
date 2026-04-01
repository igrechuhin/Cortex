# Tools-to-Resources Conversion Analysis

**Status**: Deliverable from plan-tools-to-resources-analysis  
**Created**: 2026-03-02  
**References**: [docs/api/tools.md](../api/tools.md), [naming-conventions.md](naming-conventions.md)

## Executive Summary

This document analyzes all 28 Cortex MCP tools (from `TOOL_CATEGORIES`) to determine which can be converted to resources, partially exposed as resources, or must remain tools. It includes a full inventory, per-tool conversion assessment, gap analysis for query-type tools, and migration strategy.

**Key Findings:**

- **14 tools** already have corresponding resources; tools remain for backward compatibility and parameter flexibility.
- **10 tools** have inherent side effects and must remain tool-only.
- **4 tools** are read-only candidates for new resources (partial coverage or no resource yet).
- **Recommendation**: Keep tools; resources are additive. No tool removal in this phase.

---

## Step 1: Full Tool Inventory

### 1.1 Tool List (from TOOL_CATEGORIES)

| Tool | Category | Side Effects | Read-Only? | Resource Exists? |
|------|----------|--------------|------------|------------------|
| manage_file | always_loaded | write, rollback | No (read/metadata yes) | cortex://memory-bank/file/{file_name} (read only) |
| validate | always_loaded | None | Yes | cortex://validation/validate/{check_type} |
| load_context | always_loaded | None | Yes | cortex://optimization/load-context/{task_description} |
| query_memory_bank | always_loaded | None | Yes | Multiple (stats, version-history, dependency-graph, links/*) |
| rules | always_loaded | None (index when operation=index) | Partial | cortex://rules/relevant/{task}, cortex://synapse/rules/{task} |
| plan | always_loaded | create, complete, register | No | No |
| roadmap | always_loaded | add, remove entries | No | No |
| append_entry | always_loaded | append to progress/activeContext | No | No |
| run_quality_gate | always_loaded | runs checks, may fix | No | No |
| autofix | always_loaded | fix format/lint/type | No | No |
| check_mcp_connection_health | always_loaded | None | Yes | cortex://health/connection |
| get_structure_info | always_loaded | None | Yes | cortex://structure/info |
| search_tools | always_loaded | None | Yes | No |
| session | always_loaded | register, compact | No | No |
| analyze | deferred_medium | None | Yes | cortex://analysis/analyze/{target} |
| summarize_content | deferred_medium | None | Yes | cortex://optimization/summarize/{file_name} |
| run_tool_evaluation | deferred_medium | writes cache files | No | No |
| benchmark_model | deferred_medium | writes cache files | No | No |
| get_relevance_scores | deferred_medium | None | Yes | cortex://optimization/relevance-scores/{task_description} |
| suggest_refactoring | deferred_medium | None | Yes | cortex://analysis/suggest-refactoring/{type} |
| apply_refactoring | deferred_medium | file writes | No | No |
| configure | deferred_medium | update config | No | cortex://config/{component} (view only) |
| fix_markdown_lint | deferred_medium | file writes | No | No |
| synapse | deferred_medium | sync, update_rule, update_prompt | No | No |
| check_structure_health | deferred_medium | None | Yes | cortex://structure/health |
| think | deferred_medium | records state | No | No |
| run_composite_workflow | deferred_medium | depends on sub-workflow | No | No |
| query_usage | deferred_low | None | Yes | All 16 query types (stats, unused, report, anomalies, tool-optimization, etc.) |
| manage_session_scripts | deferred_low | capture, write | No | cortex://scripts/list, analyze, suggest-improvements (read only) |
| cleanup_metadata_index | deferred_low | deletes/updates index | No | No |
| analyze_error_patterns | deferred_low | writes cache | No | No |

### 1.2 Registered Resources (from codebase grep)

| URI | Handler Location | Tool Equivalent |
|-----|------------------|-----------------|
| cortex://health/connection | connection_health.py | check_mcp_connection_health |
| cortex://structure/info | structure/main.py | get_structure_info |
| cortex://structure/health | structure/main.py | check_structure_health |
| cortex://project/root | structure/main.py | (subset of get_structure_info) |
| cortex://memory-bank/stats | foundation_stats.py | query_memory_bank(stats) |
| cortex://memory-bank/file/{file_name} | files/crud_operations.py | manage_file(read) |
| cortex://memory-bank/version-history/{file_name} | foundation_version.py | query_memory_bank(version_history) |
| cortex://memory-bank/dependency-graph | foundation_dependency.py | query_memory_bank(dependency_graph) |
| cortex://links/graph | linking/graph_operations.py | query_memory_bank(link_graph) |
| cortex://links/parse/{file_name} | linking/parser_operations.py | query_memory_bank(parse_links) |
| cortex://links/validate | linking/validation_operations.py | query_memory_bank(validate_links) |
| cortex://links/transclusions/{file_name} | linking/transclusion_operations.py | query_memory_bank(resolve_transclusions) |
| cortex://optimization/load-context/{task_description} | optimization/handlers.py | load_context |
| cortex://optimization/relevance-scores/{task_description} | optimization/handlers.py | get_relevance_scores |
| cortex://optimization/summarize/{file_name} | optimization/handlers.py | summarize_content |
| cortex://optimization/context-effectiveness | effectiveness_handlers.py | (analyze context) |
| cortex://optimization/context-usage-statistics | effectiveness_handlers.py | (analyze context) |
| cortex://usage/stats | usage_analytics.py | query_usage(stats) |
| cortex://usage/unused | usage_analytics.py | query_usage(unused) |
| cortex://usage/report | usage_analytics.py | query_usage(report) |
| cortex://usage/optimization-recommendations | usage_analytics.py | query_usage(recommendations) |
| cortex://usage/observation/{id} | usage_analytics.py | query_usage(observation) |
| cortex://usage/anomalies/{hours} | usage_analytics.py | query_usage(anomalies) |
| cortex://usage/tool-optimization/{tool_name} | usage_analytics.py | query_usage(tool_description_optimization) |
| cortex://usage/events | usage_analytics.py | query_usage(events) / recent search |
| cortex://usage/search/{query} | usage_analytics.py | query_usage(search) |
| cortex://usage/timeline/{around_id} | usage_analytics.py | query_usage(timeline) |
| cortex://usage/production-monitoring | usage_analytics.py | query_usage(production_monitoring) |
| cortex://usage/token-efficiency | usage_analytics.py | query_usage(token_efficiency) |
| cortex://usage/redundancy | usage_analytics.py | query_usage(redundancy) |
| cortex://usage/session-continuity | usage_analytics.py | query_usage(session_continuity) |
| cortex://usage/tool-frequency | usage_analytics.py | query_usage(tool_frequency) |
| cortex://usage/tool-classification | usage_analytics.py | query_usage(tool_classification) |
| cortex://validation/validate/{check_type} | validation/operations.py | validate |
| cortex://rules/relevant/{task_description} | synapse/rules_operations.py | rules(get_relevant) |
| cortex://synapse/rules/{task_description} | synapse/tools.py | rules(get_relevant) |
| cortex://synapse/prompts | synapse/tools.py | (prompts list) |
| cortex://analysis/analyze/{target} | context/analysis_operations.py | analyze |
| cortex://analysis/suggest-refactoring/{type} | refactoring/operations.py | suggest_refactoring |
| cortex://config/{component} | config/hybrid.py | configure(view) |
| cortex://health/analyze/{analysis_type} | session/health_check_operations.py | (analyze_health_check) |
| cortex://scripts/list | session/script_capture_tools.py | manage_session_scripts(list) |
| cortex://scripts/analyze | session/script_capture_tools.py | manage_session_scripts(analyze) |
| cortex://scripts/suggest-improvements/{task_description} | session/script_capture_tools.py | manage_session_scripts(suggest) |

---

## Step 2: Per-Tool Conversion Assessment

### 2.1 Assessment Matrix

| Tool | Read-Only? | URI Expressible? | Existing Resource? | Recommendation | Rationale |
|------|------------|------------------|--------------------|----------------|-----------|
| manage_file | Partial (read/metadata) | Yes (file_name) | cortex://memory-bank/file/{file_name} | resource_primary_tool_fallback | Read and metadata are resource; write/rollback stay tool |
| validate | Yes | Yes (check_type) | cortex://validation/validate/{check_type} | resource_primary_tool_fallback | Tool for file_name, strict; resource uses defaults |
| load_context | Yes | Partial (task in path; token_budget/strategy/depth complex) | cortex://optimization/load-context/{task} | resource_primary_tool_fallback | Resource covers common case; tool for complex params |
| query_memory_bank | Yes | Yes (query_type → URI) | Multiple resources | resource_primary_tool_fallback | All 7 query types have resources |
| rules | Partial (index writes) | Partial | cortex://synapse/rules/{task} | resource_primary_tool_fallback | get_relevant → resource; index → tool only |
| plan | No | N/A | No | tool_only | create, complete, register are writes |
| roadmap | No | N/A | No | tool_only | add/remove entries are writes |
| append_entry | No | N/A | No | tool_only | Appends to memory bank |
| run_quality_gate | No | N/A | No | tool_only | Runs subprocesses, may fix files |
| autofix | No | N/A | No | tool_only | Fixes format, lint, types |
| check_mcp_connection_health | Yes | Yes (no params) | cortex://health/connection | resource_primary_tool_fallback | No params; resource ideal |
| get_structure_info | Yes | Yes (no params) | cortex://structure/info | resource_primary_tool_fallback | No params; resource ideal |
| search_tools | Yes | Partial (query in path?) | No | add_resource_partial | Candidate: cortex://tools/search/{query} with defaults |
| session | No | N/A | No | tool_only | register, compact are writes |
| analyze | Yes | Yes (target) | cortex://analysis/analyze/{target} | resource_primary_tool_fallback | Resource exists |
| summarize_content | Yes | Yes (file_name) | cortex://optimization/summarize/{file_name} | resource_primary_tool_fallback | Resource exists |
| run_tool_evaluation | No | N/A | No | tool_only | Writes cache, runs subprocesses |
| benchmark_model | No | N/A | No | tool_only | Writes cache |
| get_relevance_scores | Yes | Yes (task) | cortex://optimization/relevance-scores/{task} | resource_primary_tool_fallback | Resource exists |
| suggest_refactoring | Yes | Yes (type) | cortex://analysis/suggest-refactoring/{type} | resource_primary_tool_fallback | Resource exists |
| apply_refactoring | No | N/A | No | tool_only | File writes |
| configure | Partial (view) | Yes (component) | cortex://config/{component} | resource_primary_tool_fallback | View → resource; update → tool |
| fix_markdown_lint | No | N/A | No | tool_only | File writes |
| synapse | No | N/A | No | tool_only | Sync, update_rule, update_prompt |
| check_structure_health | Yes | Yes (optional params) | cortex://structure/health | resource_primary_tool_fallback | Resource uses defaults |
| think | No | N/A | No | tool_only | Produces reasoning state; not fetchable content |
| run_composite_workflow | No | N/A | No | tool_only | Sub-workflows may write |
| query_usage | Yes | Partial (query_type → URI) | 16 of 16 query types | resource_primary_tool_fallback | All query types have resources |
| manage_session_scripts | Partial (list, analyze, suggest) | Yes (operation-like) | cortex://scripts/* | resource_primary_tool_fallback | Read ops have resources; capture → tool |
| cleanup_metadata_index | No | N/A | No | tool_only | Deletes/updates index |
| analyze_error_patterns | No | N/A | No | tool_only | Writes error_patterns.json |

### 2.2 Special Case: think

`think` is a **reasoning tool**: it records thoughts and returns incremental state. It is not a data-fetch operation. Resources represent fetchable content; `think` produces reasoning state. **Conclusion**: keep as tool-only.

---

## Step 3: Gap Analysis for Partial Resources

### 3.1 query_memory_bank → Resource Mapping

| query_type | Resource URI | Status |
|------------|--------------|--------|
| stats | cortex://memory-bank/stats | Exists |
| version_history | cortex://memory-bank/version-history/{file_name} | Exists |
| dependency_graph | cortex://memory-bank/dependency-graph | Exists |
| link_graph | cortex://links/graph | Exists |
| parse_links | cortex://links/parse/{file_name} | Exists |
| validate_links | cortex://links/validate | Exists |
| resolve_transclusions | cortex://links/transclusions/{file_name} | Exists |

**Gap**: None. All query_memory_bank query types have resources.

### 3.2 query_usage → Resource Mapping

| query_type | Resource URI | Status |
|------------|--------------|--------|
| stats | cortex://usage/stats | Exists |
| unused | cortex://usage/unused | Exists |
| report | cortex://usage/report | Exists |
| recommendations | cortex://usage/optimization-recommendations | Exists |
| observation | cortex://usage/observation/{id} | Exists |
| search | cortex://usage/search/{query} | Exists |
| events | cortex://usage/events | Exists |
| timeline | cortex://usage/timeline/{around_id} | Exists |
| anomalies | cortex://usage/anomalies/{hours} | Exists |
| tool_description_optimization | cortex://usage/tool-optimization/{tool_name} | Exists |
| production_monitoring | cortex://usage/production-monitoring | Exists |
| token_efficiency | cortex://usage/token-efficiency | Exists |
| redundancy | cortex://usage/redundancy | Exists |
| session_continuity | cortex://usage/session-continuity | Exists |
| tool_frequency | cortex://usage/tool-frequency | Exists |
| tool_classification | cortex://usage/tool-classification | Exists |

**All query_usage query types now have corresponding resources.** Path segments are used for parameters (e.g. `cortex://usage/anomalies/{hours}`, `cortex://usage/search/{query}`).

### 3.3 search_tools → Proposed Resource

- **Proposed URI**: `cortex://tools/search/{query}` (query URL-encoded)
- **Optional params**: category, limit → use defaults (e.g. limit=20)
- **Priority**: Low (search_tools is deferred, discovery-focused)

---

## Step 4: Migration Strategy

### 4.1 Backward Compatibility

- **Tools remain**. Resources are additive. No tool removal in this phase.
- Clients that support resources can prefer `cortex://` URIs for read-only operations.
- Clients that only support tools continue using tools.

### 4.2 Documentation Updates

1. **docs/api/tools.md**:
   - Add "Prefer Resources" section for clients that support `cortex://` fetching.
   - Include URI reference table for all resources (see 1.2 above).
   - Document when to use resource vs tool: prefer resource when client supports it and params fit URI.

2. **docs/architecture/naming-conventions.md**:
   - Already documents domain alignment and path rules.
   - Add note: "For read-only operations, prefer cortex:// resources when client supports them."

### 4.3 Client Guidance

Add to docs/api/tools.md:

**Prefer Resources** (when your MCP client supports resource fetching):

- For read-only operations (stats, load context, validate, rules, etc.), use the corresponding `cortex://` URI to load data into context.
- Resources avoid tool-call overhead and can be cached by the client.
- Use tools when: (1) operation has side effects, (2) you need parameters not expressible in the URI (e.g. token_budget, strategy), (3) client does not support resources.

### 4.4 Implementation Status

All query_usage gaps have been implemented (plan-query-usage-resources-implementation). Remaining candidate: `cortex://tools/search/{query}` for search_tools (low priority).

### 4.5 Deprecation Path (Future)

- For tools that become resource-primary, document that tool removal is not planned in the near term.
- If tool removal is ever considered, provide 6+ month deprecation timeline and migration guide.

---

## Success Criteria Checklist

- [x] Full tool inventory with side-effect classification
- [x] Per-tool conversion assessment (resource_only / resource_primary / tool_only / add_resource_partial)
- [x] Gap analysis for query-type and operation-based tools
- [x] Documentation: when to use resource vs tool, URI reference
- [x] New resources for query_usage gaps implemented (Phase: plan-query-usage-resources-implementation)

---

## References

- [docs/api/tools.md](../api/tools.md) — Tools vs Resources semantics
- [docs/architecture/naming-conventions.md](naming-conventions.md) — URI scheme
- [plan-tools-to-resources-analysis](../../.cortex/plans/archive/Other/plan-tools-to-resources-analysis.md) — Source plan
