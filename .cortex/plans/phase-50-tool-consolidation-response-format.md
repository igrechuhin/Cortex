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
4. Deprecate redundant tools with backward-compatible aliases
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
- [ ] Create backward-compatibility plan (deprecated aliases)

### Step 3: Implement response_format Parameter

- [x] Add `response_format: Literal["concise", "detailed"]` parameter to tools with verbose output:
  - `get_memory_bank_stats` — concise returns just: total_files, total_tokens, usage_percentage, status
  - `validate` — concise returns just: valid/invalid, error_count, warning_count
  - `load_context` — concise returns just: file_names, total_tokens, utilization
  - `suggest_refactoring` — concise returns just: suggestion_id, type, confidence, one-line recommendation
  - `get_tool_usage_stats` — concise returns just: top_5_tools with call_counts
- `search_usage` — concise returns just: ids and one-line summaries
- **2026-02-12 status:** Implemented `response_format` for `load_context`, `get_memory_bank_stats`, `get_tool_usage_stats`, `search_usage`, `validate`, and `suggest_refactoring` (concise vs detailed).
- [ ] Default to "concise" for most tools (agents can request "detailed" when needed)
- [ ] Implement response formatting logic in each tool handler
- [ ] Measure token savings: target 50-70% reduction on concise responses

### Step 4: Implement Tool Consolidation

- [ ] Implement consolidated tool handlers (Phase 1: low-risk merges)
  - Merge `write_file` into `manage_file` (add deprecation warning on `write_file`)
  - Merge `load_progressive_context` into `load_context` with `strategy="progressive"`
  - Merge `update_config` into `configure` (add deprecation warning)
- [ ] Implement consolidated tool handlers (Phase 2: new unified tools)
  - Create `query_memory_bank` tool
  - Create `query_usage` tool
- [ ] Implement backward-compatible aliases for deprecated tools
- [ ] Update tool registration in server.py

### Step 5: Update Documentation and Tool Descriptions

- [ ] Update all tool descriptions following Anthropic's guidance:
  - Clear, descriptive names reflecting natural task subdivisions
  - Unambiguous parameter names (e.g., `user_id` not `user`)
  - Include when-to-use and when-not-to-use guidance
- [ ] Update AGENTS.md tool reference table
- [ ] Update docs/api/tools.md
- [ ] Add migration guide for deprecated tools

### Step 6: Testing and Validation

- [ ] Unit tests for all consolidated tools (95%+ coverage)
- [ ] Integration tests verifying backward compatibility of deprecated aliases
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
4. Zero breaking changes (deprecated tools still work via aliases)
5. 95%+ test coverage for all new/modified tools
6. Documentation updated for all changes

## Testing Strategy

- **Coverage Target:** 95%+ for all new/modified tools
- **Unit Tests:** Test each consolidated tool with all action/query_type values, test response_format concise vs detailed output, test backward-compatible aliases
- **Integration Tests:** Verify full workflows (validate → fix → commit) work with consolidated tools
- **Edge Cases:** Test deprecated tool aliases, invalid response_format values, missing required parameters
- **Regression Tests:** Run full existing test suite to verify no breakage
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** Use Pydantic models for response validation in tests

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing agent workflows | High | Backward-compatible aliases, gradual deprecation |
| Consolidated tools too complex | Medium | Clear parameter documentation, input_examples |
| Concise responses lose critical info | Medium | Test with real agent workflows before defaulting |
| Large migration effort | Medium | Phase implementation over 2-3 sprints |

## Notes

- Anthropic's guidance: "Tools should enable agents to subdivide and solve tasks in much the same way that a human would"
- Naming convention: prefix-based namespacing (e.g., `memory_bank_*`, `usage_*`) helps agents select right tools
- Consider adding `response_format` to tool descriptions: "Returns concise summary by default; use response_format='detailed' for full data"
