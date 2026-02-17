# Phase 49: Introduce Anthropic Advanced Tool Use Features

**Status:** IN PROGRESS (Steps 1–4 complete; Step 4 2026-02-11)
**Created:** 2026-01-19
**Target Completion:** 2026-02-15
**Priority:** HIGH

## Goal

Optimize Cortex MCP tool usage by implementing Anthropic's advanced tool use features to reduce token consumption, improve tool selection accuracy, and enable more efficient tool orchestration.

## Context

Anthropic released three new beta features for advanced tool use (November 2025):

1. **Tool Search Tool** - Discovers tools on-demand instead of loading all definitions upfront
   - 85% reduction in token usage
   - Accuracy improvement: Opus 4 (49% → 74%), Opus 4.5 (79.5% → 88.1%)
   - Uses `defer_loading: true` flag

2. **Programmatic Tool Calling** - Claude writes Python code to orchestrate multiple tools
   - 37% token reduction on complex tasks
   - Eliminates multiple inference passes
   - Uses `allowed_callers: ["code_execution_20250825"]`

3. **Tool Use Examples** - Provides concrete example tool calls in definitions
   - Accuracy improved from 72% to 90% on complex parameters
   - Uses `input_examples` field

**Relevance to Cortex MCP:**

- Cortex has 53+ MCP tools - significant token overhead
- Many tools have complex parameters (manage_file, validate, suggest_refactoring)
- Some workflows involve multiple dependent tool calls (validation, refactoring)

**Reference:** <https://www.anthropic.com/engineering/advanced-tool-use>

## Approach

Implement features in order of risk/value:

1. Tool Use Examples (low-risk, high-value) - Start here
2. Tool Search Tool (medium-risk, high-value) - Requires infrastructure changes
3. Programmatic Tool Calling (high-risk, medium-value) - Requires code execution environment

## Implementation Steps

### Step 1: Research and Feasibility Analysis

- [x] Verify FastMCP 2.0 support for `defer_loading`, `allowed_callers`, `input_examples` (2026-02-03: MCP SDK has no decorator params for these; Tool model has `meta` only)
- [x] Check MCP protocol compatibility for each feature (documented in docs/guides/advanced-tool-use.md)
- [x] Determine if Claude API beta access is required (`betas=["advanced-tool-use-2025-11-20"]`) (documented: may require beta)
- [x] Document compatibility findings and limitations (docs/guides/advanced-tool-use.md)
- [x] Create proof-of-concept for each feature (meta input_examples PoC on manage_file and validate)

### Step 2: Tool Use Examples - Tool Selection

- [x] Identify top 10 tools with complex parameters (plan list; implemented for manage_file, validate first)
  - `manage_file` (operation: read/write/metadata)
  - `validate` (check_type: schema/duplications/quality/infrastructure/timestamps/roadmap_sync)
  - (others tracked for follow-up)
- [x] Document common use cases for each tool (docstring "Input examples" + meta)
- [x] Create example parameter combinations (MANAGE_FILE_INPUT_EXAMPLES, VALIDATE_INPUT_EXAMPLES)

### Step 3: Tool Use Examples - Implementation

- [x] Add `input_examples` to tool definitions in FastMCP (via `@mcp.tool(meta={"input_examples": ...})` for manage_file, validate)
- [x] Create 2-3 examples per tool showing:
  - Basic usage
  - Advanced usage with optional parameters
  - (Common error scenarios: docstring only)
- [ ] Test with Claude to verify accuracy improvement (manual; future)
- [ ] Measure before/after accuracy metrics (future)

### Step 4: Tool Search Tool - Categorization ✅

- [x] Categorize all 63 tools by usage frequency (2026-02-11):
  - **Always loaded** (15 tools): manage_file, write_file, validate, load_context, get_memory_bank_stats, rules, add_roadmap_entry, remove_roadmap_entry, complete_plan, append_progress_entry, append_active_context_entry, execute_pre_commit_checks, fix_quality_issues, check_mcp_connection_health, get_structure_info
  - **Deferred medium** (26 tools): analyze, load_progressive_context, summarize_content, get_relevance_scores, suggest_refactoring, apply_refactoring, configure, update_config, get_version_history, get_dependency_graph, parse_file_links, get_link_graph, validate_links, resolve_transclusions, fix_markdown_lint, create_plan, register_plan_in_roadmap, run_preflight_checks, run_docs_and_memory_bank_sync, sync_synapse, get_synapse_rules, get_synapse_prompts, check_structure_health, sequentialthinking, read_cache_json, write_cache_json, analyze_context_effectiveness
  - **Deferred low** (22 tools): analyze_health_check, provide_feedback, rollback_file_version, fix_roadmap_corruption, update_synapse_rule, update_synapse_prompt, 8 usage analytics tools, get_context_usage_statistics, 5 script capture tools, cleanup_metadata_index
- [x] Phase 29 data attempted but unavailable (lock error); categorized by tool purpose and implement-workflow usage patterns instead
- [x] Categorization documented in `src/cortex/tools/tool_categories.py` with Pydantic models and lookup helpers; rationale in `docs/guides/advanced-tool-use.md`
- [x] 41 comprehensive tests in `tests/tools/test_tool_categories.py` (100% coverage on new module)

### Step 5: Tool Search Tool - Infrastructure ✅

- [x] Implement `defer_loading` support in tool registration (metadata/config; full list_tools filtering when SDK supports it)
- [x] Create tool search mechanism (regex over name + rationale in tool_categories.search_deferred_tools)
- [x] Update server.py to support deferred tool loading (comment + get_tool_search_config in OptimizationConfig)
- [x] Configure tool categories in .cortex/config/optimization.json (tool_search in default config, ToolSearchConfigModel, lazy injection in_load_config)

### Step 6: Tool Search Tool - Testing

- [ ] Test token savings with deferred loading
- [ ] Verify tool discovery works correctly
- [ ] Measure accuracy with Tool Search Tool enabled
- [ ] Document configuration options

### Step 7: Programmatic Tool Calling - Analysis

- [ ] Identify tool chains suitable for code orchestration:
  - Validation workflow: schema → quality → duplications
  - Refactoring workflow: suggest → preview → apply
  - Batch file operations: multiple manage_file calls
- [ ] Determine which tools should allow code execution callers
- [ ] Document orchestration patterns

### Step 8: Programmatic Tool Calling - Implementation

- [ ] Add `allowed_callers` to appropriate tool definitions
- [ ] Create code execution environment integration
- [ ] Implement tool invocation from code context
- [ ] Test with complex workflows

### Step 9: Documentation and Testing

- [ ] Update tool documentation with new features
- [ ] Add comprehensive tests for each feature
- [ ] Create usage guide for advanced features
- [ ] Measure overall improvements:
  - Token usage reduction
  - Accuracy improvement
  - Workflow efficiency

## Dependencies

- **Phase 41: FastMCP 2.0 Migration** - COMPLETE (prerequisite)
- **Phase 44: Pydantic Model Migration** - COMPLETE (prerequisite)
- **Phase 29: Track MCP Tool Usage** - PLANNED (would provide usage data for categorization)
- **Phase 43: Tools vs Resources** - PLANNED (related to tool organization)
- **Phase 45: MCP Annotations** - PLANNED (related to tool metadata)

## Success Criteria

1. **Tool Use Examples:**
   - 10+ tools have input_examples
   - Measurable accuracy improvement on complex parameters

2. **Tool Search Tool:**
   - 50%+ reduction in initial token usage
   - Tool discovery works correctly for all deferred tools
   - No regression in tool selection accuracy

3. **Programmatic Tool Calling:**
   - At least 3 workflow patterns implemented
   - Token savings on multi-tool workflows

4. **Overall:**
   - Documentation updated for all features
   - Comprehensive test coverage
   - No breaking changes to existing functionality

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| FastMCP doesn't support features | High | Research in Step 1, fallback to custom implementation |
| Claude API beta access required | Medium | Document requirements, provide fallback behavior |
| Breaking changes to tool registration | High | Comprehensive testing, gradual rollout |
| Performance regression | Medium | Benchmark before/after, rollback plan |

## Technical Design

### Tool Use Examples Schema

```python
@mcp.tool(
    name="manage_file",
    description="Manage Memory Bank file operations...",
    input_examples=[
        {
            "file_name": "projectBrief.md",
            "operation": "read",
            "include_metadata": True
        },
        {
            "file_name": "activeContext.md",
            "operation": "write",
            "content": "# Active Context\n\n## Current Focus...",
            "change_description": "Updated current work focus"
        }
    ]
)
async def manage_file(...):
    ...
```

### Tool Search Tool Configuration

```json
{
  "tool_search": {
    "enabled": true,
    "always_loaded": [
      "manage_file",
      "validate",
      "get_memory_bank_stats",
      "check_mcp_connection_health"
    ],
    "deferred": [
      "suggest_refactoring",
      "apply_refactoring",
      "rollback_file_version",
      "fix_roadmap_corruption"
    ]
  }
}
```

### Programmatic Tool Calling Pattern

```python
@mcp.tool(
    name="validate",
    allowed_callers=["code_execution_20250825"]
)
async def validate(...):
    ...
```

## Notes

- This plan is based on Anthropic's announcement from November 2025
- Features are in beta and may change
- Implementation should be modular to allow partial adoption
- Consider user feedback for tool categorization

## Related Plans

- [Phase 29: Track MCP Tool Usage](phase-29-track-mcp-tool-usage.md)
- [Phase 43: Reconsider Tools Registration](phase-43-reconsider-tools-registration.md)
- [Phase 45: Add MCP Annotations](phase-45-add-mcp-annotations.md)
- [Phase 50: Tool Consolidation and Response Format](phase-50-tool-consolidation-response-format.md) — complements this plan by reducing tool count and adding response_format
- [Phase 51: Just-in-Time Context with Section-Level Loading](phase-51-just-in-time-context-section-loading.md) — context engineering improvements
- [Phase 52: Consistent Helpful Error Responses](phase-52-consistent-helpful-error-responses.md) — better error messages for tool use
- [Phase 54: Session Start Initializer Pattern](phase-54-session-start-initializer-pattern.md) — session orientation optimization
- [Phase 55: Lightweight Think Tool](phase-55-lightweight-think-tool.md) — simplified think tool for reasoning
- [Phase 56: Session Compaction Workflow](archive/Phase56/phase-56-session-compaction-workflow.md) — context compaction and handoff
- [Phase 57: Evaluation-Driven Tool Improvement](phase-57-evaluation-driven-tool-improvement.md) — systematic tool evaluation framework
- [Phase 58: Multi-Agent Specialization](phase-58-multi-agent-specialization-task-locking.md) — role-based context and task locking

### New Input (2026-02-11): Anthropic Engineering Blog Deep Dive

Comprehensive analysis of 7 Anthropic engineering articles identified 9 improvement areas for Cortex MCP. This plan (Phase 49) covers ideas 2 (Deferred Tool Loading via Steps 4-6) and partially idea 1 (Tool Use Examples via Steps 2-3). The remaining 7 ideas are tracked as separate plans (Phases 50-58) listed above.
