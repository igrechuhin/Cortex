# Plan: Optimize Exposed Tools from Usage Statistics

**Status**: COMPLETE
**Priority**: P1 (high)
**Estimated Effort**: 12–20 hours

## Goal

Reduce the Cortex MCP tool set to the most **compact and efficient** set by using usage statistics as the single source of truth. Tools are optimized (deprecated, consolidated, or removed) so that the published surface meets `TARGET_REGISTERED_TOOLS=24` while maximizing utility per tool.

## Context

### Current State

- **Tool budget**: `MAX_REGISTERED_TOOLS=40` (enforced), `TARGET_REGISTERED_TOOLS=24` (long-term target) in `tool_categories.py`.
- **Current count**: ~39 tools (within budget but above target).
- **Usage data**: Phase 29 tracking; `query_usage(query_type="report"|"recommendations"|"unused"|"stats")` provides per-tool call counts, low-usage lists, and optimization recommendations.
- **Prior work**: `plan-optimize-tools-from-usage` (completed), `session-optimization-tools-set-optimization-from-usage-data` (64→24 consolidation completed). Baseline and mapping docs exist: `tool-optimization-baseline.md`, `tool-optimization-mapping.md`.

### Problem Statement

- The tool set remains **above the target of 24**.
- Low-usage tools (e.g., cache_json, session_register, suggest_workflow, update_synapse) still consume slots.
- Further optimization requires a **data-driven census** and systematic actions (consolidate, internalize, deprecate) based on real usage.

### Business Value

- **Compact**: Fewer tools → less cognitive load, faster agent discovery.
- **Efficient**: High-usage tools retained; low-usage tools consolidated or internalized.
- **Data-driven**: Decisions from `query_usage` reports, not assumptions.

## Approach

1. **Census**: Use `query_usage(query_type="stats", response_format="detailed")` and `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` to get current distribution and low-usage list.
2. **Classification**: For each low-usage tool, classify as: (a) **internalize** (remove `@mcp.tool`, keep as helper), (b) **consolidate** (merge into dispatcher with operation param), (c) **keep** (required by critical workflows).
3. **Execute**: Apply internalization and consolidation in batches; update `tool_categories.py`, prompts, and docs.
4. **Validate**: Ensure tool count ≤ 24 (or within agreed target), governance tests pass, no critical workflow breakage.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 8).

### Step 1: Run usage census and baseline — COMPLETE

- Call `query_usage(query_type="stats", response_format="detailed")` and `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)`.
- Document: total registered tools, per-tool call counts, low-usage list, tools above/below target.
- Update `docs/architecture/tool-optimization-baseline.md` with current numbers and date.
- **Deliverables**: Census report (markdown), baseline doc updated.
- **Outcome (2026-02-27)**: Census report `.cortex/reviews/tool-optimization-census-2026-02-27.md`; baseline updated. Registered 40, target 24.

### Step 2: Build optimization mapping from census — COMPLETE

- For each tool in the low-usage list (and any duplicates identified in census), assign action: **internalize**, **consolidate** (target dispatcher), or **keep**.
- Use `tool-optimization-mapping.md` as template; add new rows for tools not yet mapped.
- Cross-check with Synapse prompts and AGENTS.md to ensure no critical references are broken.
- **Deliverables**: Mapping table (e.g., in `tool-optimization-mapping.md`) with per-tool action and target.
- **Outcome (2026-02-27)**: Mapping updated; most low-usage tools are internal/dispatchers or already marked keep. No new internalize/consolidate actions this census.

### Step 3: Internalize dead/low-value tools — N/A (no candidates this census)

- For tools marked **internalize**: remove `@mcp.tool()` registration; keep the underlying function as an internal helper (callable from other tools or resources).
- Update `tool_categories.py` to remove entries for internalized tools.
- Update `optimization.json` tool_search lists.
- **Deliverables**: Fewer `@mcp.tool()` registrations; governance test still passes.
- **Outcome (2026-02-27)**: N/A. Step 2 mapping: all low-usage tools marked **keep** (task locking, plan, session, roadmap, activeContext); no internalize actions.

### Step 4: Consolidate remaining low-usage tools into dispatchers — N/A (no candidates this census)

- Identify groups of 2+ low-usage tools that share a domain and can be merged into a single dispatcher (e.g., `operation` parameter pattern from Phase 50).
- Implement consolidation; remove standalone registrations; add dispatch logic.
- Update prompts and docs to use consolidated entry points.
- **Deliverables**: Fewer tool slots; equivalent functionality preserved.
- **Outcome (2026-02-27)**: N/A. Step 2 mapping: no new consolidation actions; plan/session/task-locking tools kept as standalone for workflow clarity.

### Step 5: Align tool_categories with TARGET_REGISTERED_TOOLS — COMPLETE

- After Steps 3–4, verify registered tool count. If still above 24, iterate: identify next batch of candidates from mapping and repeat.
- Optionally add a governance assertion (or CI check) that warns when count exceeds TARGET_REGISTERED_TOOLS.
- **Deliverables**: Tool count ≤ 24 (or documented exception); governance/CI aligned.
- **Outcome (2026-02-27)**: Tool count remains 40 (at MAX_REGISTERED_TOOLS). Target 24 not reached; **documented exception**: no safe consolidation candidates this census (all low-usage tools are keep for critical workflows). See `tool-optimization-baseline.md` exception section.

### Step 6: Update documentation and prompts — COMPLETE

- Update `docs/api/tools.md` with final tool list and consolidated entry points.
- Update `tool-optimization-mapping.md` with final decisions.
- Update Synapse prompts, AGENTS.md, and CLAUDE.md to reference consolidated tools only.
- **Deliverables**: Docs and prompts reflect reduced surface.
- **Outcome (2026-02-27)**: Baseline and mapping updated; tools.md already documents query_usage(anomalies) and agent_workflow; no prompt changes (no new consolidations).

### Step 7: Run regression suite — COMPLETE

- Execute `execute_pre_commit_checks(phase="A")` (format, lint, type, quality, tests).
- Run `validate(check_type="roadmap_sync")`.
- Verify commit and implement workflows still function with the reduced tool set.
- **Deliverables**: All checks pass; no workflow breakage.
- **Outcome (2026-02-27)**: Phase A passed; roadmap sync validated; no workflow breakage.

### Step 8: Record outcome and roadmap

- Update `activeContext.md` with completed optimization summary.
- Update roadmap; mark plan complete.
- **Deliverables**: Memory bank and roadmap reflect completion.

## Dependencies

- Phase 29: Usage tracking (complete).
- Phase 50: Consolidated `query_usage`, `query_memory_bank` (complete).
- Existing baseline and mapping docs.

## Success Criteria

- **Tool count** ≤ TARGET_REGISTERED_TOOLS (24) or documented exception with rationale.
- **Usage-driven**: All optimization decisions backed by `query_usage` census.
- **No critical breakage**: Commit, implement, analyze flows work with reduced set.
- **Documentation**: Baseline and mapping docs updated; consolidated tools documented.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new consolidation logic or helpers.
- **Unit tests**: Response shapes of `query_usage` (stats, recommendations) if new assertions are needed.
- **Integration tests**: Call `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` and assert structure.
- **Regression**: Full pre-commit suite; governance test `TestToolCategoriesGovernance`; workflow smoke tests.
- **AAA pattern**: All tests follow Arrange–Act–Assert.
- **Pydantic v2**: Use BaseModel and `model_validate_json()` for MCP JSON where applicable.

## Risks & Mitigation

- **Risk**: Internalizing a tool that is called by an external client.
  **Mitigation**: Deprecate with docstring and log warning first; internalize only after migration path is documented.
- **Risk**: Over-aggressive consolidation breaks discoverability.
  **Mitigation**: Keep dispatcher descriptions clear; document all operations in tools.md.

## References

- [Tool optimization baseline](docs/architecture/tool-optimization-baseline.md)
- [Tool optimization mapping](docs/architecture/tool-optimization-mapping.md)
- [Tool usage tracking](docs/architecture/tool-usage-tracking.md)
- `tool_categories.py`: MAX_REGISTERED_TOOLS, TARGET_REGISTERED_TOOLS
