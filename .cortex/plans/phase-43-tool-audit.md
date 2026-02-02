# Phase 43: Tool Audit — Resource vs Tool Categorization

**Status**: Complete (Step 1 deliverable)  
**Created**: 2026-02-02  
**Plan**: .cortex/plans/phase-43-reconsider-tools-registration.md

## 1. Tool Inventory and Categorization

All tools are registered via `@mcp.tool()`; 0 resources currently. Count: **45 tools**.

| # | Tool | Module | Purpose | Category | Rationale |
|---|------|--------|---------|----------|-----------|
| 1 | `manage_file` | file_operations | Read/write/metadata memory bank files | **Hybrid** | read/metadata → read-only; write → side effects |
| 2 | `get_memory_bank_stats` | phase1_foundation_stats | Memory bank statistics | Resource | Read-only stats |
| 3 | `get_version_history` | phase1_foundation_version | File version history | Resource | Read-only history |
| 4 | `get_dependency_graph` | phase1_foundation_dependency | Dependency graph | Resource | Read-only graph |
| 5 | `rollback_file_version` | phase1_foundation_rollback | Rollback file to version | Tool | Writes file, creates snapshot |
| 6 | `cleanup_metadata_index` | phase1_foundation_cleanup | Clean stale index entries | Tool | Modifies index |
| 7 | `parse_file_links` | link_parser_operations | Parse links in file | Resource | Read-only parse |
| 8 | `validate_links` | link_validation_operations | Validate link integrity | Resource | Read-only validation |
| 9 | `resolve_transclusions` | transclusion_operations | Resolve transclusions | Resource | Read-only resolve |
| 10 | `get_link_graph` | link_graph_operations | Link dependency graph | Resource | Read-only graph |
| 11 | `validate` | validation_operations | Schema/duplication/quality checks | Resource | Read-only validation |
| 12 | `load_context` | phase4_optimization_handlers | Load context within budget | Resource | Read-only load |
| 13 | `load_progressive_context` | phase4_optimization_handlers | Progressive context load | Resource | Read-only load |
| 14 | `get_relevance_scores` | phase4_optimization_handlers | Relevance scores for files | Resource | Read-only scores |
| 15 | `summarize_content` | phase4_optimization_handlers | Summarize content | Resource | Read-only summarize |
| 16 | `analyze_context_effectiveness` | context_analysis_handlers | Context effectiveness analysis | Resource | Read-only analysis |
| 17 | `get_context_usage_statistics` | context_analysis_handlers | Context usage stats | Resource | Read-only stats |
| 18 | `analyze` | analysis_operations | Usage/structure/insights analysis | Resource | Read-only analysis |
| 19 | `suggest_refactoring` | refactoring_operations | Refactoring suggestions | Resource | Read-only suggestions |
| 20 | `apply_refactoring` | phase5_execution | Execute refactoring | Tool | Modifies files |
| 21 | `provide_feedback` | phase5_execution | Submit learning feedback | Tool | Updates learning state |
| 22 | `get_synapse_rules` | synapse_tools | List/get Synapse rules | Resource | Read-only |
| 23 | `get_synapse_prompts` | synapse_tools | List/get Synapse prompts | Resource | Read-only |
| 24 | `sync_synapse` | synapse_tools | Git pull/push Synapse | Tool | Git operations |
| 25 | `update_synapse_rule` | synapse_tools | Update Synapse rule file | Tool | Writes file |
| 26 | `update_synapse_prompt` | synapse_tools | Update Synapse prompt file | Tool | Writes file |
| 27 | `configure` | configuration_operations | View/update/reset config | **Hybrid** | view → read-only; update/reset → side effects |
| 28 | `rules` | rules_operations | get_relevant or index rules | **Hybrid** | get_relevant → read-only; index → side effects |
| 29 | `check_structure_health` | phase8_structure | Structure health ± cleanup | **Hybrid** | no cleanup → read-only; perform_cleanup → side effects |
| 30 | `get_structure_info` | phase8_structure | Structure paths and config | Resource | Read-only |
| 31 | `execute_pre_commit_checks` | pre_commit_tools | Run format/type/quality/tests | Tool | Runs commands, may fix |
| 32 | `fix_quality_issues` | pre_commit_tools | Fix format/lint/types | Tool | Modifies files |
| 33 | `fix_markdown_lint` | markdown_operations | Fix markdown lint | Tool | Modifies files |
| 34 | `fix_roadmap_corruption` | roadmap_corruption | Fix roadmap corruption | Tool | Writes file |
| 35 | `check_mcp_connection_health` | connection_health | Connection health check | Resource | Read-only check (no state change) |
| 36 | `analyze_health_check` | health_check_operations | Health-check analysis | Resource | Read-only analysis |
| 37 | `capture_session_script` | script_capture_tools | Capture session script | Tool | Writes/captures |
| 38 | `list_session_scripts` | script_capture_tools | List captured scripts | Resource | Read-only list |
| 39 | `analyze_session_scripts` | script_capture_tools | Analyze session scripts | Resource | Read-only analysis |
| 40 | `suggest_tool_improvements` | script_capture_tools | Suggest tool improvements | Resource | Read-only suggestions |
| 41 | `promote_session_script` | script_capture_tools | Promote script to template | Tool | Writes/promotes |
| 42 | `get_tool_usage_stats` | usage_analytics | Tool usage statistics | Resource | Read-only stats |
| 43 | `get_unused_tools` | usage_analytics | Unused tools report | Resource | Read-only |
| 44 | `get_tool_usage_report` | usage_analytics | Tool usage report | Resource | Read-only |
| 45 | `get_optimization_recommendations` | usage_analytics | Optimization recommendations | Resource | Read-only |

## 2. Decision Matrix Summary

| Category | Count | Tools |
|----------|-------|--------|
| **Resource** (read-only) | 28 | get_memory_bank_stats, get_version_history, get_dependency_graph, parse_file_links, validate_links, resolve_transclusions, get_link_graph, validate, load_context, load_progressive_context, get_relevance_scores, summarize_content, analyze_context_effectiveness, get_context_usage_statistics, analyze, suggest_refactoring, get_synapse_rules, get_synapse_prompts, get_structure_info, check_mcp_connection_health, analyze_health_check, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, get_tool_usage_stats, get_unused_tools, get_tool_usage_report, get_optimization_recommendations |
| **Tool** (side effects) | 13 | rollback_file_version, cleanup_metadata_index, apply_refactoring, provide_feedback, sync_synapse, update_synapse_rule, update_synapse_prompt, execute_pre_commit_checks, fix_quality_issues, fix_markdown_lint, fix_roadmap_corruption, capture_session_script, promote_session_script |
| **Hybrid** | 4 | manage_file, configure, rules, check_structure_health |

## 3. Hybrid Operations — Proposed Handling

### 3.1 `manage_file`

- **Read-only**: `operation in ("read", "metadata")` → expose as **Resource** (e.g. URI `cortex://memory-bank/{file_name}` or tool `get_file`).
- **Write**: `operation == "write"` → **Tool** (e.g. `write_file`).
- **Strategy**: **Option A (recommended)** — Split into `get_file` (Resource) and `write_file` (Tool). No backward compatibility: do not keep `manage_file`; clients use `get_file` / `write_file` directly.

### 3.2 `configure`

- **Read-only**: `action == "view"` → **Resource** (e.g. `get_config` or resource URI by component).
- **Write**: `action in ("update", "reset")` → **Tool** (e.g. `update_config`; reset via `update_config(NULL)` or equivalent).
- **Strategy**: Split into `get_config` (Resource) and `update_config` (Tool). One Tool only: `update_config(config)` for update, `update_config(NULL)` for reset.

### 3.3 `rules`

- **Read-only**: `operation == "get_relevant"` → **Resource** (e.g. `get_relevant_rules`).
- **Write**: `operation == "index"` → **Tool** (e.g. `index_rules`).
- **Strategy**: Split into `get_relevant_rules` (Resource) and `index_rules` (Tool).

### 3.4 `check_structure_health`

- **Read-only**: `perform_cleanup == False` → **Resource** (e.g. `get_structure_health`).
- **Write**: `perform_cleanup == True` → **Tool** (e.g. `repair_structure_health`).
- **Strategy**: Split into `get_structure_health` (Resource) and `repair_structure_health` (Tool).

## 4. FastMCP / MCP SDK Resource Support (Step 2.1 Note)

- **Verified**: The project uses the official **MCP SDK** (`mcp` package, not gofastmcp.com). `FastMCP` from `mcp.server.fastmcp` exposes:
  - `mcp.resource` (decorator/method)
  - `add_resource`, `list_resources`, `list_resource_templates`, `read_resource`
- **Conclusion**: Resource support is available; use `mcp.resource()` for read-only operations. Exact signature and URI pattern to be confirmed in Step 2 (Design Resource API).

## 5. Resource Wrappers and Usage Tracking (MANDATORY)

Tools today use **guards and tracking** that must apply to resources as well:

- **ensure_usage_context** — Sets `get_current_managers()` so UsageTracker can resolve; enables usage recording.
- **mcp_tool_wrapper(timeout=...)** — Runs handler via `with_mcp_stability` (timeout, semaphore, retry, connection health), then `_record_usage_if_available(tool_name, duration_ms, success, error_type)` and `_handle_tool_exception_if_failure`.

**Requirement for resources:**

- Every `@mcp.resource()` handler MUST use the same pattern: **ensure_usage_context** + a **resource wrapper** (timeout, connection health, retry, usage recording). No resource handler may be registered without these guards.
- Implement **mcp_resource_wrapper(timeout=...)** in `mcp_stability.py` (or a shared handler wrapper) that:
  - Applies the same stability protections as `mcp_tool_wrapper` (timeout, semaphore, connection check, retry).
  - Records usage (e.g. extend `_record_usage_if_available` to accept `kind="tool"|"resource"` or add `record_resource_usage` / unified `record_usage(name, kind=...)` in UsageTracker so analytics can include or distinguish resources).
- **Usage analytics**: `get_tool_usage_stats`, `get_unused_tools`, `get_optimization_recommendations` (and any reporting) MUST include resource reads so we do not lose visibility. Extend models/reporting to "tools and resources" (or "handlers") as needed.

**Stack for resources (same order as tools):**

1. `@mcp.resource(uri=...)`
2. `@ensure_usage_context`
3. `@mcp_resource_wrapper(timeout=...)`

## 6. Next Steps (Plan Step 2)

- Design Resource API: URI scheme, `@mcp.resource()` usage, response format (align with current Tool JSON where possible).
- No backward compatibility: do not keep Tool aliases; clients use new Resource/Tool names directly.
- **Design and implement resource wrappers/tracking** per section 5 (mcp_resource_wrapper, usage recording for resources, analytics including resources).
- Implement 1–2 pilot Resources (e.g. `get_memory_bank_stats`, `get_structure_info`) and then migrate remaining read-only tools.
