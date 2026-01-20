# Phase 49: Introduce Anthropic Advanced Tool Use Features

**Status:** PLANNING
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

- [ ] Verify FastMCP 2.0 support for `defer_loading`, `allowed_callers`, `input_examples`
- [ ] Check MCP protocol compatibility for each feature
- [ ] Determine if Claude API beta access is required (`betas=["advanced-tool-use-2025-11-20"]`)
- [ ] Document compatibility findings and limitations
- [ ] Create proof-of-concept for each feature

### Step 2: Tool Use Examples - Tool Selection

- [ ] Identify top 10 tools with complex parameters:
  - `manage_file` (operation: read/write/metadata)
  - `validate` (check_type: schema/duplications/quality/infrastructure/timestamps/roadmap_sync)
  - `suggest_refactoring` (type: consolidation/splits/reorganization)
  - `apply_refactoring` (action: approve/apply/rollback)
  - `rules` (operation: index/get_relevant)
  - `configure` (component: validation/optimization/learning)
  - `check_structure_health` (cleanup_actions options)
  - `execute_pre_commit_checks` (checks options)
  - `optimize_context` (strategy options)
  - `summarize_content` (strategy options)
- [ ] Document common use cases for each tool
- [ ] Create example parameter combinations

### Step 3: Tool Use Examples - Implementation

- [ ] Add `input_examples` to tool definitions in FastMCP
- [ ] Create 2-3 examples per tool showing:
  - Basic usage
  - Advanced usage with optional parameters
  - Common error scenarios
- [ ] Test with Claude to verify accuracy improvement
- [ ] Measure before/after accuracy metrics

### Step 4: Tool Search Tool - Categorization

- [ ] Categorize all 53+ tools by usage frequency:
  - **Always loaded** (high-frequency): manage_file, validate, get_memory_bank_stats
  - **Deferred** (medium-frequency): suggest_refactoring, apply_refactoring, rules
  - **Deferred** (low-frequency): rollback_file_version, fix_roadmap_corruption
- [ ] Use Phase 29 data if available (Track MCP Tool Usage)
- [ ] Document categorization rationale

### Step 5: Tool Search Tool - Infrastructure

- [ ] Implement `defer_loading` support in tool registration
- [ ] Create tool search mechanism (regex or BM25)
- [ ] Update server.py to support deferred tool loading
- [ ] Configure tool categories in optimization.json

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
