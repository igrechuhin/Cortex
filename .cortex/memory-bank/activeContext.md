# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-02-21)

- ✅ **Phase 56 Step 4: Progressive summarization** - COMPLETE (2026-02-21) - Auto-trigger for progress summarization when progress.md exceeds 10K tokens; Tier 1/2/3 and threshold tests added.

- ✅ **Phase 56 Session Compaction Workflow** - COMPLETE (2026-02-21) - Completed Step 6 Testing and Validation: new tests for managers-not-initialized and invalid handoff schema; fixed session lifecycle integration test (patch in compaction_operations). Phase 56 complete.

- ✅ **Pydantic rules encourage enums for all fixed sets** - COMPLETE (2026-02-21) - Updated python-pydantic-standards.mdc to encourage enums for all fixed-set fields (status, priority, state, type, kind), added explicit guidance and python-coding-standards reference, generalized violations list.

- ✅ **Phase 49 Step 6: Tool Search Tool - Testing** - COMPLETE (2026-02-21) - Token savings and tool discovery tests; get_tool_search_config tests; configuration options documented in advanced-tool-use.md.

- ✅ **Phase 49 Step 7: Programmatic Tool Calling - Analysis** - COMPLETE (2026-02-21) - Tool chains and allowed_callers analysis documented in advanced-tool-use.md; plan Step 7 marked complete.

- ✅ **Phase 49 Step 8: Programmatic Tool Calling - Implementation** - COMPLETE (2026-02-21) - Added allowed_callers to tool meta for validate, suggest_refactoring, apply_refactoring, manage_file. Constant and tool list in tool_categories.py; advanced-tool-use.md and tests updated. Quality gate passed.

- ✅ **Phase 49 Step 9: Documentation and Testing** - COMPLETE (2026-02-21) - Updated tool documentation (docs/api/tools.md), added Usage guide and Measuring improvements to docs/guides/advanced-tool-use.md, added comprehensive tests for input_examples and tool search.

- ✅ **Phase 49: Introduce Anthropic advanced tool use** - COMPLETE (2026-02-21) - Tool use examples, tool search (deferred loading), programmatic tool calling meta; docs and tests updated. All implementable steps done.

- ✅ **Phase 57 evaluation dashboard extension** - COMPLETE (2026-02-21) - Added ToolTaskMetrics and per-tool aggregation in harness; dashboard now includes Overall Tool Effectiveness Score, Top 5 Tools by Usage, and Top 5 Tools by Improvement Needed. Quality gate and tests pass.

- ✅ **Phase 57 Step 1: Evaluation task suite** - COMPLETE (2026-02-21) - Extended core_workflows.json to 26 tasks with 5+ per category (context 8, pre_commit 5, plan 5, memory_bank 8). Added plan-add-roadmap-entry-for-new-plan and plan-archive-or-list-plans. Plan file updated; quality gate and tests passed.

- ✅ **Phase 57 Steps 4 & 6: Optimization workflow and A/B** - COMPLETE (2026-02-21) - Implemented run_tool_optimization_workflow, compare_ab_analyses, optimization history persistence, and dashboard helpers module; added tests; plan and memory bank updated.

- ✅ **Phase 57 Step 2 & Step 6 (partial)** - COMPLETE (2026-02-21) - Completed evaluation harness (token fields, tool usage patterns, output to .cortex/.cache/evals/). Added EvalTaskResult total_input_tokens/total_output_tokens, EvalAnalysis average_tokens_per_task, token_consumption_by_category, top_tool_combinations (ToolCombination). Reproducibility test and phase5_evaluation_helpers extraction; quality gate passed.

- ✅ **Phase 57 Step 3: Extend usage tracking for error patterns** - COMPLETE (2026-02-21) - Extended usage tracking to capture error patterns: ToolUsageEvent now has retry_count, param_validation_failure, result_used; record_tool_usage and record_usage_finish accept and persist them; retry_count is threaded from_execute_with_retry; param_validation_failure is set from exception message when error_type looks like Validation; run_execute_and_finalize/finalize_on_exception/attach_attempt_to_exception moved to mcp_stability_config. Plan Step 3 checkbox marked done.

## Completed Work (2026-02-20)

- **Summary (2026-02-20)** - 1 entries archived.

## Completed Work (2026-02-19)

- **Summary (2026-02-19)** - 1 entries archived.

## Completed Work (2026-02-18)

- **Summary (2026-02-18)** - 1 entries archived.

## Completed Work (2026-02-17)

- **Summary (2026-02-17)** - 1 entries archived.

## Completed Work (2026-02-16)

- **Summary (2026-02-16)** - 1 entries archived.

## Completed Work (2026-02-13)

- **Summary (2026-02-13)** - 1 entries archived.

## Completed Work (2026-01-14)

- **Summary (2026-01-14)** - 1 entries archived.

## Completed Work (2026-02-12)

- **Summary (2026-02-12)** - 1 entries archived.

## Completed Work (2026-02-11)

- **Summary (2026-02-11)** - 1 entries archived.

## Completed Work (2026-02-10)

- **Summary (2026-02-10)** - 1 entries archived.

## Completed Work (2026-02-09)

- **Summary (2026-02-09)** - 1 entries archived.

## Completed Work (2026-02-07)

- **Summary (2026-02-07)** - 1 entries archived.

## Current Focus

Commit pipeline; no active feature focus.

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
