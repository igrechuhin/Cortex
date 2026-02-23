# Plan: Optimize MCP Tools Based on Usage Data

**Status**: COMPLETED (Steps 1–8 complete)
**Priority**: P1 (high)
**Estimated Effort**: 20–35 hours

## Goal

Reduce the Cortex MCP tool set to a smaller, more effective set by using existing usage data. Tools that fall **below a defined usage threshold** must be optimized: deprecated, consolidated into existing entry points (e.g. `query_usage`, `query_memory_bank`), or removed, so that the published surface is easier to maintain and for agents to use.

## Context

### Current State

- **Phase 29 (COMPLETE)** implemented usage tracking: `UsageTracker`, tool instrumentation, and analytics. Usage data is stored under `.cortex/.cache/usage/` and is queryable.
- **Phase 50** consolidated many read operations into `query_memory_bank` and `query_usage`. Single-entry tools (e.g. `get_unused_tools`, `get_tool_usage_report`) remain callable and are dispatched via `query_usage(query_type="unused"|"report"|"recommendations"|...)`.
- The **published tool set is very large** (100+ tools across phases). Many tools are rarely or never used, which:
  - Increases cognitive load and discovery cost for agents
  - Increases maintenance and documentation burden
  - Makes the API surface feel ineffective and hard to navigate

### Problem Statement

- The current set is **extremely large and ineffective** from a UX and maintenance perspective.
- **Tools below a usage threshold** are candidates for optimization but are not yet systematically identified, classified, or acted upon.
- We have the data (`query_usage(query_type="unused", ...)` and `query_usage(query_type="recommendations", ...)`) but no formal process or implementation plan to reduce the tool set based on it.

### Business Value

- **Smaller, clearer surface**: Fewer tools to document, test, and maintain.
- **Better agent UX**: Less noise in tool lists and search; focus on high-value tools.
- **Data-driven**: Decisions driven by real usage (Phase 29 data) rather than assumptions.
- **Alignment with consolidation**: Continue Phase 50 style consolidation where it makes sense.

## Approach

1. **Baseline**: Use `query_usage` (unused, report, recommendations) to establish a baseline list of low-usage tools and current counts.
2. **Policy**: Define a usage threshold (e.g. ≤ N calls in last 30 days) and tiers (e.g. zero use vs. low use) for classification.
3. **Classification**: For each tool below threshold, classify as: (a) safe to deprecate (redirect to consolidated tool or resource), (b) consolidate into an existing entry point, or (c) remove (with migration path if any).
4. **Execute in phases**: Deprecate first (warnings, docs, redirects), then consolidate or remove with backward compatibility where required.
5. **Docs and prompts**: Update tools.md, guides, and Synapse prompts so that recommended workflows use the reduced set and consolidated entry points.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 8).

### Step 1: Establish usage baseline and threshold policy ✅ COMPLETED (2026-02-23)

- Run `query_usage(query_type="report", include_recommendations=True)` and `query_usage(query_type="unused", days=30, min_usage_count=0)` to get full baseline.
- Run `query_usage(query_type="stats")` to get per-tool counts over a defined window (e.g. 30 days).
- Document current tool count (published tools + resources) and the list of tools below a chosen threshold (e.g. ≤ 5 calls in 30 days).
- Define and document **threshold policy**: e.g. `min_usage_count` and `days` for “unused” vs “low use”; criteria for “must optimize” (e.g. zero or below-threshold usage).
- **Deliverables**: Baseline report (markdown or JSON), threshold policy in plan or docs. → **Done:** `docs/architecture/tool-optimization-baseline.md`

### Step 2: Map low-usage tools to consolidation targets ✅ COMPLETED (2026-02-23)

- For each tool in the below-threshold list, determine:
  - Whether it is already redundant with a consolidated tool (e.g. standalone `get_unused_tools` vs `query_usage(query_type="unused")`).
  - Whether it can be **deprecated** in favor of `query_usage`, `query_memory_bank`, `load_context`, or a resource URI.
  - Whether it must be **kept** (e.g. required by commit/implement flows or critical path).
- Produce a **mapping table**: tool name → action (deprecate | consolidate | keep) and target (e.g. `query_usage`, resource URI, or “remove”).
- **Deliverables**: Mapping table (e.g. in plan or `docs/architecture/tool-optimization-mapping.md`). → **Done:** `docs/architecture/tool-optimization-mapping.md`

### Step 3: Implement deprecation path for first batch ✅ COMPLETED (2026-02-23)

- Select a first batch of tools that are clearly redundant (e.g. standalone usage analytics tools that are fully covered by `query_usage`).
- Add deprecation mechanism: e.g. docstring/deprecation notice and optional runtime warning when tool is called, pointing to the consolidated alternative (e.g. `query_usage(query_type="unused", ...)`).
- Ensure no critical prompts or commit/implement flows break; update any references in Synapse prompts to use consolidated tools.
- **Deliverables**: Deprecation notices and one or more tools marked deprecated with migration path; prompt updates if needed. → **Done:** `run_tool_optimization_workflow` docstring + log message; migration path to query_usage.

### Step 4: Extend query_usage / docs for discoverability ✅ COMPLETED (2026-02-23)

- Ensure `query_usage` and `query_memory_bank` are clearly documented as the primary entry points for usage analytics and memory-bank read operations.
- Add a short “Tool optimization” or “Reduced surface” section in docs (e.g. `docs/api/tools.md` or `docs/guides/workflows.md`) explaining that low-usage tools may be deprecated in favor of consolidated tools.
- **Deliverables**: Doc updates; discoverability of consolidated tools improved. → **Done:** "Tool optimization (reduced surface)" in `docs/api/tools.md` with links to baseline and mapping.

### Step 5: Second batch — consolidate or remove ✅ COMPLETED (2026-02-23)

- For the next batch of below-threshold tools, perform consolidation (e.g. remove standalone tool, keep behavior only via `query_usage` or resource) or removal with explicit migration path.
- Prefer consolidation over hard removal where callers might exist (e.g. redirect or alias to consolidated tool).
- **Deliverables**: Reduced number of published tools; migration path documented.
- **Done:** Added `query_type="anomalies"` to `query_usage`; `get_session_tool_anomalies` now redirects to it with deprecation notice and docstring. analyze.md updated to prefer `query_usage(query_type="anomalies", hours=24)`. Mapping doc updated.

### Step 6: Configuration and threshold as single source of truth ✅ COMPLETED (2026-02-23)

- Where optimization logic uses a threshold (e.g. “unused” = ≤ 5 calls in 30 days), ensure it is configurable (e.g. in `.cortex/config/usage_tracking.json` or a dedicated optimization config) so that “tools below usage threshold” can be tuned without code changes.
- Document the threshold and how to run “unused tools” and “recommendations” reports.
- **Deliverables**: Configurable threshold (if not already), documentation of how to reproduce “below threshold” list.

### Step 7: Testing and regression ✅ COMPLETED (2026-02-23)

- Add or update tests that: (1) run `query_usage(query_type="unused", ...)` and `query_usage(query_type="recommendations", ...)` and assert structure of response; (2) verify that consolidated tools return equivalent results for deprecated paths where applicable.
- Regression: ensure commit pipeline and implement/analyze flows still pass; no removal of tools that are referenced by name in critical prompts without migration.
- **Deliverables**: Tests for usage-based optimization workflow; regression suite passing. → **Done:** `test_query_usage_unused_response_structure`, `test_query_usage_recommendations_response_structure` (structure assertions); `test_get_session_tool_anomalies_equivalent_to_query_usage_anomalies` (deprecated vs consolidated equivalence). Full test suite and quality gate passing.

### Step 8: Finalize documentation and roadmap

- Update API reference (e.g. `docs/api/tools.md`) to mark deprecated tools and point to consolidated alternatives.
- Update roadmap and activeContext to reflect completed optimization work.
- **Deliverables**: Docs updated; roadmap/activeContext reflect new tool surface.

## Dependencies

- **Phase 29**: Usage tracking and analytics (COMPLETE).
- **Phase 50**: Consolidated `query_usage` and `query_memory_bank` (COMPLETE).
- **Phase 43**: Resource naming and tool/resource split (reference for which tools have resources).
- No new external dependencies.

## Success Criteria

- A **usage threshold** is defined and documented; “tools below threshold” are identifiable via `query_usage` (unused/recommendations).
- At least one **batch of low-usage tools** is deprecated or consolidated, with clear migration path to `query_usage` or other consolidated entry points.
- **Documentation** explains the reduced surface and points agents to consolidated tools.
- **No critical workflow breakage**: Commit, implement, and analyze flows continue to work; any removed tool has a documented alternative.
- **Configurable threshold** (or documented default) so future optimization can be repeated.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new code (e.g. deprecation helpers, config for threshold). Existing `query_usage` and usage_analytics tests remain; add tests for new behavior only.
- **Unit tests**: Any new function that computes “below threshold” or builds the mapping table; response shape of `query_usage` for `unused` and `recommendations`.
- **Integration tests**: Call `query_usage(query_type="unused", days=30, min_usage_count=5)` and assert JSON structure and presence of `unused_tools` or equivalent; same for `recommendations`.
- **Regression**: Full pre-commit and commit-pipeline run; implement and analyze prompts run without broken tool references.
- **AAA**: All tests follow Arrange–Act–Assert.
- **Pydantic v2**: Use BaseModel and `model_validate_json()` for MCP JSON responses where new tests are added.

## Risks & Mitigation

- **Risk**: Removing a tool that is used by an external client or script.
  **Mitigation**: Deprecate first with warning and docs; remove only after consolidation path is clear and documented.
- **Risk**: Threshold too aggressive and flags important but rarely-used tools.
  **Mitigation**: Policy in docs; configurable threshold; manual override list for “always keep” tools.
- **Risk**: Prompt references break (e.g. commit prompt calls a removed tool).
  **Mitigation**: Audit prompts before removal; use consolidated tool names in prompts.

## Timeline

- **Steps 1–2**: 4–6 hours (baseline, policy, mapping).
- **Steps 3–4**: 6–8 hours (deprecation, docs).
- **Steps 5–6**: 6–8 hours (second batch, config).
- **Steps 7–8**: 4–6 hours (testing, final docs).
- **Total**: ~20–35 hours.

## Notes

- This plan **uses** existing usage data and analytics; it does not re-implement Phase 29.
- “Optimize” here means: reduce published tool count and improve effectiveness of the set by acting on tools **below a usage threshold**.
- Related: Phase 29 (tracking), Phase 50 (consolidation), Phase 43 (resources); plan-anthropic-context-engineering-alignment (token usage and tool UX).
