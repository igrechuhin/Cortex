# Plan: Tool Consolidation — Next Analysis

## Status: PENDING

## Created: 2026-02-24

## Goal

Run the next tool consolidation analysis after the current consolidation (Phase 50 + P1 budget lock) is complete. Use usage data and governance to identify further reduction opportunities and produce an actionable list for a follow-up consolidation phase.

## Context

- Current state: 47 tools and 15 resources (MAX_REGISTERED_TOOLS=47 enforced).
- Target: ≤40 tools (stretch ~24). Next analysis should inform which tools to remove, internalize, or merge.
- Analyze prompt Step 2.5 (Tools optimization) and the archived plan `session-optimization-tools-set-optimization-from-usage-data.md` define the methodology.

## Implementation Steps

1. **Tool census** — Call `query_usage(query_type="stats", response_format="full")` and read `tool_categories.py` to confirm current registered count and category breakdown.
2. **Usage distribution** — Call `query_usage(query_type="report", include_recommendations=True)` for per-tool call counts.
3. **Low-usage list** — Call `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` for near-dead tools.
4. **Five problem classes** — Check: budget violation (>40), dead tools (<5 calls), duplicates, incomplete consolidations, consolidation candidates (3+ tools → 1 dispatcher).
5. **Report** — Add a Tools optimization subsection to the session-optimization report (or a dedicated memo) with: tool budget status, dead tools with counts, duplicates, incomplete consolidations, consolidation candidates, total reduction potential, and per-tool actions (remove/internalize/merge).
6. **Optional improvements plan** — If findings warrant, run Create Plan with the analysis as input so the next consolidation phase has a concrete implementation plan.

## Success Criteria

- Census and usage data gathered; five problem classes evaluated.
- Written report with tool budget, lists, and recommended actions.
- No code or tool removals in this plan — analysis and planning only.

## References

- `docs/architecture/tool-optimization-mapping.md`
- `src/cortex/tools/tool_categories.py`
- Archived: `.cortex/plans/archive/SessionOptimization/session-optimization-tools-set-optimization-from-usage-data.md`
- Analyze prompt Step 2.5 (Tools optimization)

## Testing Strategy

- No production code changes; validation is manual review of report and census outputs.
- If scripts are added for census/report formatting, unit tests for parsing and output shape; 95% coverage for new code.
