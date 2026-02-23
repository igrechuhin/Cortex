# Plan: Tools Set Optimization — Deprecate / Merge / Remove Poor Performers

**Status**: PENDING
**Priority**: P2
**Estimated Effort**: 4–8 hours

## Goal

Reduce the published tool set by deprecating, merging, or removing **poor performers** (tools below the usage threshold). Use usage data and the existing baseline/mapping so decisions are data-driven.

## Context

- **Baseline and policy**: [docs/architecture/tool-optimization-baseline.md](../../docs/architecture/tool-optimization-baseline.md) — threshold (e.g. ≤5 calls in 90 days), how to reproduce low-usage list via `query_usage`.
- **Mapping**: [docs/architecture/tool-optimization-mapping.md](../../docs/architecture/tool-optimization-mapping.md) — which tools to keep, deprecate, or consolidate.
- **Parent plan**: [plan-optimize-tools-from-usage.md](plan-optimize-tools-from-usage.md) — full optimization lifecycle (baseline, policy, mapping, deprecation, config, tests).

This plan focuses only on **executing** deprecate/merge/remove actions for tools already classified in the mapping.

## Implementation Steps

1. **Refresh low-usage list**  
   Run `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` and `query_usage(query_type="unused", days=90, min_usage_count=5)`. Confirm the list matches the mapping (or update the mapping if the list has changed).

2. **Deprecate (done for first tool)**  
   - `run_tool_optimization_workflow`: already has deprecation notice and log message; migration path to `query_usage(query_type="unused"|"recommendations")` and docs. No further code change unless removing the tool later.
   - `get_session_tool_anomalies`: add deprecation notice and docstring pointing to future `query_usage(query_type="anomalies")` or keep as optional; ensure analyze.md and other prompts can work if callers switch.

3. **Merge (optional)**  
   - If adding `query_type="anomalies"` to `query_usage`: implement handler, then deprecate `get_session_tool_anomalies` with redirect. Otherwise leave as deprecate-only.

4. **Remove (only after deprecation period)**  
   - Do not remove tools in this plan until deprecation has been documented and callers have had time to migrate. Track in roadmap or a follow-up plan.

5. **Docs and prompts**  
   - Ensure docs/api/tools.md (and any guides) list deprecated tools and alternatives.
   - Ensure Analyze and other Synapse prompts that reference tool optimization use `query_usage` and point to this plan or the baseline/mapping docs.

## Success Criteria

- Low-usage list is reproducible via `query_usage`.
- All tools in the mapping with action **deprecate** have a deprecation notice and migration path.
- No tools removed without a prior deprecation and documented alternative.
- Documentation and Analyze prompt consider tools optimization and plans to deprecate/merge/remove poor performers.

## References

- [Tool optimization baseline](../../docs/architecture/tool-optimization-baseline.md)
- [Tool optimization mapping](../../docs/architecture/tool-optimization-mapping.md)
- [Plan: Optimize MCP tools from usage](plan-optimize-tools-from-usage.md)
