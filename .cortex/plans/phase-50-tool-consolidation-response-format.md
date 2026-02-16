# Phase 50: Tool Consolidation and Response Format Optimization

**Status:** IN PROGRESS
**Created:** 2026-02-11
**Priority:** HIGH
**Estimated Effort:** 2-3 sprints
**Related:** Phase 49 (Advanced Tool Use), Phase 43 (Tools vs Resources)

## Goal

Reduce Cortex MCP's tool count from 53+ to ~30 highly focused tools, and add a `response_format` parameter (concise/detailed) to verbose tools, following Anthropic's engineering guidance that "too many tools or overlapping tools can distract agents from pursuing efficient strategies."

## Context

Anthropic's "Writing Effective Tools for Agents" article identifies a key anti-pattern: wrapping existing API functionality into too many individual tools rather than consolidating into workflow-oriented tools. Cortex currently has 53+ tools with significant overlap:

- `manage_file` (read/write/metadata) + `write_file` (write-only) — overlapping write functionality
- `load_context` + `load_progressive_context` — overlapping context loading
- `configure` + `update_config` — overlapping configuration
- `get_memory_bank_stats`, `get_version_history`, `get_dependency_graph`, `get_link_graph` — could be unified into a single `query_memory_bank` tool with a `query_type` parameter
- `suggest_refactoring` + `apply_refactoring` + `provide_feedback` — three tools for one workflow

Additionally, many tools return verbose JSON responses (200+ tokens) when a concise summary (50 tokens) would suffice for most use cases, following Anthropic's recommendation for a `response_format` enum parameter.

**Reference:** <https://www.anthropic.com/engineering/writing-tools-for-agents>

## Approach

1. Audit all 53+ tools, categorize by usage frequency and overlap
2. Merge overlapping tools into consolidated interfaces
3. Add `response_format` parameter to high-token-output tools
4. Remove redundant tools immediately (no deprecation period needed)
5. Measure token savings before/after

## Implementation Steps

### Step 1: Tool Usage Audit and Overlap Analysis

- [ ] Run `get_tool_usage_stats` to get current usage data for all 53+ tools
- [ ] Run `get_unused_tools(days=90)` to identify rarely-used tools
- [ ] Map all tools into a usage matrix: (tool_name, calls/month, avg_tokens_returned, overlap_group)
- [ ] Identify consolidation groups:
  - File operations group: `manage_file`, `write_file`
  - Context group: `load_context`, `load_progressive_context`, `get_relevance_scores`
  - Config group: `configure`, `update_config`
  - Memory bank query group: `get_memory_bank_stats`, `get_version_history`, `get_dependency_graph`, `get_link_graph`, `parse_file_links`, `validate_links`
  - Refactoring group: `suggest_refactoring`, `apply_refactoring`, `provide_feedback`
  - Roadmap group: `add_roadmap_entry`, `remove_roadmap_entry`, `register_plan_in_roadmap`, `complete_plan`
  - Usage analytics group: `get_tool_usage_stats`, `get_unused_tools`, `get_tool_usage_report`, `get_optimization_recommendations`, `search_usage`, `get_usage_events`, `get_usage_observation`, `get_usage_timeline`
- [ ] Document consolidation rationale for each group

#### 2026-02-12 Progress and Preliminary Audit

- **Usage data collection status**: Attempts to run `get_tool_usage_stats` and `get_unused_tools` for the last 90 days are currently failing because `read_cache_json` cannot acquire a lock for recent usage JSON files (e.g., `2026-02-07.json`, `2026-02-08.json`), which is most likely due to **stale `.lock` files from a previous broken session** rather than any active concurrent process. Tool implementations remain healthy, but full quantitative stats (calls/month, avg_tokens_returned) could not be retrieved in this session; a future session should clean up any `usage/events/*.json.lock` files under `.cortex/.cache` if present and then retry to populate the numeric columns of the usage matrix.
- **Qualitative overlap confirmation**: Based on the current MCP tool inventory, the consolidation groups listed above accurately capture the main overlap clusters:
  - **File operations group**: `manage_file`, `write_file`
  - **Context group**: `load_context`, `load_progressive_context`, `get_relevance_scores`
  - **Config group**: `configure`, `update_config`
  - **Memory bank query group**: `get_memory_bank_stats`, `get_version_history`, `get_dependency_graph`, `get_link_graph`, `parse_file_links`, `validate_links`, `resolve_transclusions`
  - **Refactoring group**: `suggest_refactoring`, `apply_refactoring`, `provide_feedback`
  - **Roadmap group**: `add_roadmap_entry`, `remove_roadmap_entry`, `register_plan_in_roadmap`, `complete_plan`
  - **Usage analytics group**: `get_tool_usage_stats`, `get_unused_tools`, `get_tool_usage_report`, `get_optimization_recommendations`, `search_usage`, `get_usage_events`, `get_usage_observation`, `get_usage_timeline`
- **Preliminary usage matrix shape**: The planned usage matrix remains the same:

  | Tool name | Calls/month (TBD) | Avg tokens returned (TBD) | Overlap group |
  |-----------|-------------------|---------------------------|---------------|
  | `manage_file` | _TBD_ | _TBD_ | File operations |
  | `write_file` | _TBD_ | _TBD_ | File operations |
  | `load_context` | _TBD_ | _TBD_ | Context |
  | `load_progressive_context` | _TBD_ | _TBD_ | Context |
  | `get_relevance_scores` | _TBD_ | _TBD_ | Context |
  | `configure` | _TBD_ | _TBD_ | Config |
  | `update_config` | _TBD_ | _TBD_ | Config |
  | `get_memory_bank_stats` | _TBD_ | _TBD_ | Memory bank query |
  | `get_version_history` | _TBD_ | _TBD_ | Memory bank query |
  | `get_dependency_graph` | _TBD_ | _TBD_ | Memory bank query |
  | `get_link_graph` | _TBD_ | _TBD_ | Memory bank query |
  | `parse_file_links` | _TBD_ | _TBD_ | Memory bank query |
  | `validate_links` | _TBD_ | _TBD_ | Memory bank query |
  | `resolve_transclusions` | _TBD_ | _TBD_ | Memory bank query |
  | `suggest_refactoring` | _TBD_ | _TBD_ | Refactoring |
  | `apply_refactoring` | _TBD_ | _TBD_ | Refactoring |
  | `provide_feedback` | _TBD_ | _TBD_ | Refactoring |
  | `add_roadmap_entry` | _TBD_ | _TBD_ | Roadmap |
  | `remove_roadmap_entry` | _TBD_ | _TBD_ | Roadmap |
  | `register_plan_in_roadmap` | _TBD_ | _TBD_ | Roadmap |
  | `complete_plan` | _TBD_ | _TBD_ | Roadmap |
  | `get_tool_usage_stats` | _TBD_ | _TBD_ | Usage analytics |
  | `get_unused_tools` | _TBD_ | _TBD_ | Usage analytics |
  | `get_tool_usage_report` | _TBD_ | _TBD_ | Usage analytics |
  | `get_optimization_recommendations` | _TBD_ | _TBD_ | Usage analytics |
  | `search_usage` | _TBD_ | _TBD_ | Usage analytics |
  | `get_usage_events` | _TBD_ | _TBD_ | Usage analytics |
  | `get_usage_observation` | _TBD_ | _TBD_ | Usage analytics |
  | `get_usage_timeline` | _TBD_ | _TBD_ | Usage analytics |

This section should be updated in a future session once locks on usage JSON files are released, filling in the numeric columns from `get_tool_usage_stats` / `get_unused_tools` and adding any newly introduced tools to the appropriate overlap group.

### Step 2: Design Consolidated Tool Interfaces

- [ ] Design unified interfaces for each consolidation group:
  - `manage_file` absorbs `write_file` (already has write operation)
  - `load_context` absorbs `load_progressive_context` via `strategy` parameter
  - `configure` absorbs `update_config` (already has view/update/reset actions)
  - New `query_memory_bank(query_type=...)` for stats/history/graph/links
  - New `manage_refactoring(action=...)` for suggest/apply/feedback
  - New `manage_roadmap(action=...)` for add/remove/register/complete
  - New `query_usage(query_type=...)` for stats/unused/report/recommendations/search/events/timeline
- [ ] Define parameter schemas for each consolidated tool
- [ ] Ensure no functionality is lost in consolidation
- [ ] Remove redundant tools immediately (no deprecation period)

### Step 3: Implement response_format Parameter

- [x] Add `response_format: Literal["concise", "detailed"]` parameter to tools with verbose output:
  - `get_memory_bank_stats` — concise returns just: total_files, total_tokens, usage_percentage, status
  - `validate` — concise returns just: valid/invalid, error_count, warning_count
  - `load_context` — concise returns just: file_names, total_tokens, utilization
  - `suggest_refactoring` — concise returns just: suggestion_id, type, confidence, one-line recommendation
  - `get_tool_usage_stats` — concise returns just: top_5_tools with call_counts
- `search_usage` — concise returns just: ids and one-line summaries
- **2026-02-12 status:** Implemented `response_format` for `load_context`, `get_memory_bank_stats`, `get_tool_usage_stats`, `search_usage`, `validate`, and `suggest_refactoring` (concise vs detailed).
- [x] Default to "concise" for most tools (agents can request "detailed" when needed)
- [x] Implement response formatting logic in each tool handler
- [ ] Measure token savings: target 50-70% reduction on concise responses

### Step 4: Implement Tool Consolidation

- [x] Implement consolidated tool handlers (Phase 1: low-risk merges)
  - [x] Merge `write_file` into `manage_file` - COMPLETE 2026-02-12
  - [x] Merge `load_progressive_context` into `load_context` with `strategy="progressive"` - COMPLETE 2026-02-12
  - [x] Merge `update_config` into `configure` - COMPLETE 2026-02-12
- [x] Remove redundant tools immediately:
  - [x] Remove `write_file` tool (functionality in `manage_file`) - COMPLETE 2026-02-12
  - [x] Remove `load_progressive_context` tool (functionality in `load_context`) - COMPLETE 2026-02-12
  - [x] Remove `update_config` tool (functionality in `configure`) - COMPLETE 2026-02-12
- [x] Implement consolidated tool handlers (Phase 2: new unified tools) - COMPLETE 2026-02-12
  - [x] Create `query_memory_bank` tool (query_type: stats, version_history, dependency_graph, link_graph, parse_links, validate_links, resolve_transclusions)
  - [x] Create `query_usage` tool (query_type: stats, unused, report, recommendations, search, events, observation, timeline)
  - [x] Remove @mcp.tool from 7 memory-bank and 8 usage tools; register query_memory_bank and query_usage only
- [x] Update tool registration: tool_categories.py, discovery/tool_registry.py, tools/**init**.py

### Step 5: Update Documentation and Tool Descriptions

- [x] Update all tool descriptions following Anthropic's guidance:
  - Clear, descriptive names reflecting natural task subdivisions
  - Unambiguous parameter names (e.g., `user_id` not `user`)
  - Include when-to-use and when-not-to-use guidance
- [x] Update AGENTS.md tool reference table
- [x] Update docs/api/tools.md
- [x] Remove references to removed tools from documentation
- **2026-02-13:** Completed. Added Phase 50 section (query_memory_bank, query_usage); updated Tools vs Resources and context workflow; replaced standalone get_* / load_progressive_context / write_file / update_config references across docs, AGENTS.md, mcp-tool-timeouts, tool-usage-tracking, troubleshooting, failure-modes, error-recovery, advanced-tool-use, setup-cursor-integration.

### Step 6: Testing and Validation

- [ ] Unit tests for all consolidated tools (95%+ coverage)
- [ ] Remove tests for removed tools
- [ ] Measure before/after metrics:
  - Total tool count reduction (target: 53 → ~30)
  - Average token savings per tool response (target: 50%+)
  - No regression in task completion accuracy
- [ ] Verify all existing workflows still function correctly

## Dependencies

- Phase 49 (Advanced Tool Use) — complementary, provides input_examples for consolidated tools
- Phase 43 (Tools vs Resources) — COMPLETE, informed read-only vs write tool split

## Success Criteria

1. Tool count reduced from 53+ to ~35 or fewer
2. `response_format` parameter available on 8+ high-token tools
3. Average concise response is 50%+ smaller than current default
4. Redundant tools removed (no deprecated aliases)
5. 95%+ test coverage for all new/modified tools
6. Documentation updated for all changes

## Testing Strategy

- **Coverage Target:** 95%+ for all new/modified tools
- **Unit Tests:** Test each consolidated tool with all action/query_type values, test response_format concise vs detailed output
- **Integration Tests:** Verify full workflows (validate → fix → commit) work with consolidated tools
- **Edge Cases:** Test invalid response_format values, missing required parameters
- **Regression Tests:** Run full existing test suite to verify no breakage
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** Use Pydantic models for response validation in tests

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing agent workflows | Low | Tools are internal MCP tools, immediate removal is safe |
| Consolidated tools too complex | Medium | Clear parameter documentation, input_examples |
| Concise responses lose critical info | Medium | Test with real agent workflows before defaulting |
| Large migration effort | Low | Direct removal, no migration needed |

## Notes

- Anthropic's guidance: "Tools should enable agents to subdivide and solve tasks in much the same way that a human would"
- Naming convention: prefix-based namespacing (e.g., `memory_bank_*`, `usage_*`) helps agents select right tools
- Consider adding `response_format` to tool descriptions: "Returns concise summary by default; use response_format='detailed' for full data"
