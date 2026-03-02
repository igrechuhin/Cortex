# Plan: Remove / Unpublish Dead Tools

**Status**: COMPLETE
**Priority**: P2
**Estimated Effort**: 2–4 hours

## Goal

Remove or unpublish MCP tools identified as dead in session optimization reports (≤5 calls over 30–90 days), reducing tool count and simplifying the API surface. Use usage data and [tool-optimization-mapping.md](../../docs/architecture/tool-optimization-mapping.md) to ensure only tools without workflow dependencies are affected.

## Context

- **Session optimization reports** consistently flag dead tools (e.g. session-optimization-2026-02-24T09-59, 2026-02-25T21-55, 2026-02-26T13-54).
- **tool-optimization-mapping.md** defines KEEP (task locking, plan discovery, session lifecycle, memory bank) and already-pruned tools.
- **Primary candidate**: `benchmark_model` — consistently dead, not in KEEP list, no prompt/workflow dependency. Functionality can be reproduced with `run_tool_evaluation` + manual save/compare.
- **Unpublish** = remove from `TOOL_CATEGORIES` so MCP does not expose to clients; handler code may remain for internal use.
- **Remove** = fully delete handler; use only after unpublish and verification.

## Implementation Steps

1. **Refresh low-usage list**
   - Run `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` and `query_usage(query_type="unused", days=90, min_usage_count=5)`.
   - Compare against [tool-optimization-mapping.md](../../docs/architecture/tool-optimization-mapping.md). Identify tools that are:
     - Below threshold
     - NOT marked KEEP
     - NOT already pruned (e.g. get_session_tool_anomalies, run_tool_optimization_workflow)

2. **Unpublish `benchmark_model`**
   - Remove `benchmark_model` from `TOOL_CATEGORIES` in `src/cortex/tools/structure/categories.py`.
   - Handler in `src/cortex/tools/evaluation/model_benchmark.py` may remain; it will no longer be exposed to MCP clients.

3. **Update skill**
   - Edit `src/cortex/resources/skills/evaluation.json`: remove `benchmark_model` from `tools` array and from description/keywords.

4. **Update docs**
   - [docs/api/tools.md](../../docs/api/tools.md): add entry for `benchmark_model` as **unpublished** with migration path: use `run_tool_evaluation` + manual store/compare.
   - [docs/architecture/tool-optimization-mapping.md](../../docs/architecture/tool-optimization-mapping.md): add row for `benchmark_model` with action **removed (unpublished)**.

5. **Verify no prompt references**
   - Grep Synapse prompts and rules for `benchmark_model`. Update or remove any references.

6. **Tests**
   - Ensure no tests assume `benchmark_model` is in the registered tool list.
   - If `benchmark_model` handler tests exist, keep them (handler code remains); add a unit test that the tool is not in `get_always_loaded_tool_names()` / `get_deferred_tool_names()`.
   - Run full test suite; coverage must remain ≥ 90%.

7. **Optional: further candidates**
   - If step 1 identifies other non-KEEP, non-pruned dead tools, repeat steps 2–6 for each (one tool per commit for clean history).

## Success Criteria

- `benchmark_model` no longer appears in MCP tool list.
- Tool count reduced by at least 1.
- All tests pass; coverage ≥ 90%.
- Documentation and mapping updated.
- No prompt/rules reference removed tools without a migration path.

## Testing Strategy

- **Unit tests**: Verify `benchmark_model` is not in `TOOL_CATEGORIES` (or in a helper that returns registered tools).
- **Integration**: Run `list tools` or equivalent; confirm `benchmark_model` is absent.
- **Regression**: Full pre-commit checks pass (format, type_check, quality, tests).
- **Coverage**: Maintain ≥ 90%; no new uncovered paths.

## Risks and Mitigation

- **Risk**: Some workflow secretly depends on `benchmark_model`.  
  **Mitigation**: Unpublish first (do not delete handler); rollback is trivial (re-add to TOOL_CATEGORIES).
- **Risk**: External clients hardcode `benchmark_model`.  
  **Mitigation**: Doc migration path; deprecation notice in tools.md before unpublishing if desired.

## References

- [Tool optimization mapping](../../docs/architecture/tool-optimization-mapping.md)
- [Tool optimization baseline](../../docs/architecture/tool-optimization-baseline.md)
- [Tools-to-resources conversion analysis](../../docs/architecture/tools-to-resources-conversion-analysis.md)
- Session reports: `.cortex/reviews/session-optimization-*.md`
