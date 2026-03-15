# Phase 57: Evaluation-Driven Tool Improvement

**Status:** IN PROGRESS
**Created:** 2026-02-11
**Priority:** HIGH
**Estimated Effort:** 3 sprints
**Related:** Phase 49 (Advanced Tool Use), Phase 50 (Tool Consolidation)

## Goal

Build a systematic evaluation framework for measuring Cortex MCP tool effectiveness — tracking not just usage counts but success rates, token efficiency, error patterns, and agent workflow accuracy — then use Claude to iteratively optimize tool descriptions and schemas based on evaluation data, following Anthropic's evaluation-driven tool development methodology.

## Context

Anthropic's "Writing Effective Tools for Agents" article describes an iterative process:

1. Build prototype tools
2. Create comprehensive evaluations grounded in real-world use cases
3. Run evaluations, analyze results (including agent reasoning/CoT)
4. Let Claude analyze transcripts and optimize tools
5. Repeat until performance plateaus

Key insight: "Claude-optimized tool descriptions outperformed human-written ones" and "most of the advice in this post came from repeatedly optimizing our internal tool implementations with Claude Code."

Cortex currently tracks basic usage stats (call counts, success rates) via `get_tool_usage_stats` but lacks:

- Task-level success measurement (did the overall workflow succeed?)
- Token efficiency tracking (how many tokens did the tool consume vs. a concise baseline?)
- Error pattern analysis (which errors recur, what causes tool retries?)
- Systematic evaluation of tool descriptions against real agent workflows
- Automated tool description optimization

**Reference:** <https://www.anthropic.com/engineering/writing-tools-for-agents>

## Approach

1. Define evaluation tasks grounded in real Cortex workflows
2. Build an evaluation harness that measures tool effectiveness
3. Implement automated tool description optimization
4. Create a continuous improvement pipeline

## Implementation Steps

### Step 1: Define Evaluation Task Suite

- [x] Create 20+ evaluation tasks covering core Cortex workflows:
  **Context loading tasks (5+):**
  - "Load context for a bug fix in the validation module"
  - "Load context for adding a new MCP tool"
  - "Load context for architectural review of the tool registration system"

  **Pre-commit tasks (5+):**
  - "Run pre-commit checks after adding a new Python module with tests"
  - "Run quality fixes after modifying 3 files across different packages"
  - "Execute full commit pipeline for a feature addition"

  **Plan management tasks (5+):**
  - "Create a plan for adding dark mode support to a web app"
  - "Register a completed plan and update roadmap"
  - "Find and implement the next pending roadmap item"

  **Memory bank tasks (5+):**
  - "Read activeContext, update completed work, add next steps"
  - "Validate all memory bank files and fix any issues"
  - "Search usage history for recent load_context calls"

- [x] For each task, define:
  - Expected tool calls (which tools, in what order)
  - Expected outcome (success criteria)
  - Token budget baseline (expected token consumption)
  - Common failure modes

- [x] Store tasks in `.cortex/evals/tasks/` as JSON (initial `core_workflows.json` seeded; extend with additional tasks in follow-up work). Extended to 26 tasks with 5+ in each category (context 8, pre_commit 5, plan 5, memory_bank 8).

### Step 2: Build Evaluation Harness

- [x] Create `ToolEvaluationHarness` class:

  ```python
  class ToolEvaluationHarness:
      async def run_task(self, task: EvalTask) -> EvalResult:
          """Run a single evaluation task and measure results."""
      async def run_suite(self, suite: list[EvalTask]) -> EvalSuiteResult:
          """Run all tasks and aggregate metrics."""
      def analyze_results(self, results: EvalSuiteResult) -> EvalAnalysis:
          """Analyze results for patterns and improvement opportunities."""
  ```

- [x] Track metrics per task:
  - **Success/failure** — did the workflow complete correctly?
  - **Tool calls** — count, sequence, any redundant calls
  - **Token consumption** — total input + output tokens (schema in EvalTaskResult/EvalAnalysis; 0 when usage events lack token data)
  - **Errors** — count, types, retries needed
  - **Latency** — time to complete each tool call and overall task
- [x] Track aggregate metrics:
  - Overall success rate by task category
  - Average token consumption by task category
  - Most common error types across all tasks
  - Tool usage patterns (which tools called together) — `top_tool_combinations` in EvalAnalysis
- [x] Output results to `.cortex/.cache/evals/` as JSON

### Step 3: Error Pattern Analysis

- [x] Extend usage tracking to capture error patterns:
  - Tool name + error type + frequency (already in ToolUsageEvent/Stats)
  - Parameter validation failures (`param_validation_failure` on ToolUsageEvent; set from ValidationError message when recording)
  - Retry patterns (`retry_count` on ToolUsageEvent; threaded from _execute_with_retry via record_usage_finish)
  - "Wasted" tool calls (`result_used` field on ToolUsageEvent; optional, for future session-level tracking)
- [x] Create `analyze_error_patterns()` tool:
  - Surfaces top recurring errors based on evaluation suite results
  - Identifies tools associated with each error type via affected_tools
  - Provides a compact JSON payload for follow-up optimization work
- [x] Store error patterns in `.cortex/.cache/evals/error_patterns.json`

### Step 4: Automated Tool Description Optimization

- [x] Create `optimize_tool_descriptions` workflow (initial):
  1. Run evaluation suite to get baseline metrics
  2. (Collect transcripts / Claude step deferred to later iteration)
  3. (Apply improvements deferred)
  4. Re-run or pass optimized analysis for comparison
  5. Compare via `compare_ab_analyses` and accept/reject
  6. Record run in optimization history
- [x] Implement A/B testing for tool descriptions:
  - `run_tool_optimization_workflow` runs baseline, optionally accepts `optimized_analysis_json` for A/B
  - `compare_ab_analyses(baseline, optimized)` compares success rates and error counts; winner chosen by success rate then error count
  - Keep whichever performs better (recorded in history)
- [x] Store optimization history in `.cortex/.cache/evals/optimization_history.json`

### Step 5: Continuous Improvement Pipeline

- [x] Create `run_tool_evaluation` MCP tool:
  - Runs full evaluation suite
  - Reports results summary
  - Suggests improvements
- [x] Integrate with end-of-session analysis:
  - Track which tools were used in the session
  - Compare against expected patterns
  - Flag anomalies (unusual tool sequences, high retry counts)
  - Implemented: `get_session_tool_anomalies(hours=24)` MCP tool; optional step in analyze.md to call it and add Tool use anomalies subsection.
- [x] Create evaluation dashboard (Markdown report):
  - Overall tool effectiveness score
  - Top 5 tools by usage and by improvement needed
  - Trending error patterns (as "Top Error Patterns" section)
  - Token efficiency trends (implemented: format_token_efficiency in dashboard_helpers; section shown when average_tokens_per_task or token_consumption_by_category present)

### Step 6: Testing and Validation

- [x] Unit tests for evaluation harness (95%+ coverage)
- [x] Unit tests for error pattern analysis (payload shape, empty suite, task_ids filter)
- [x] Integration test: run evaluation suite and verify metrics collection (dashboard with per-tool sections)
- [x] Verify evaluation results are reproducible
- [x] Test A/B comparison logic (compare_ab_analyses, optimization workflow baseline + A/B, history load/append)

## Dependencies

- Usage tracking (existing) — provides raw data
- Phase 49 (Tool Use Examples) — evaluation validates example effectiveness
- Phase 50 (Tool Consolidation) — evaluation measures consolidation impact
- Phase 52 (Error Responses) — evaluation measures error response helpfulness

## Success Criteria

1. 20+ evaluation tasks covering all major Cortex workflows
2. Evaluation harness measures success rate, tokens, errors, latency per task
3. Error pattern analysis identifies top 10 recurring issues
4. At least one round of automated tool description optimization completed
5. Measurable improvement in tool selection accuracy after optimization
6. 95%+ test coverage for evaluation framework

## Testing Strategy

- **Coverage Target:** 95%+ for evaluation framework code
- **Unit Tests:** EvalTask parsing, metric calculation, error pattern analysis, A/B comparison
- **Integration Tests:** Full evaluation suite run with mock tools
- **Edge Cases:** Tasks with no expected tool calls, tasks that should fail, concurrent evaluation runs
- **Regression Tests:** Evaluation framework doesn't interfere with production tool usage
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** EvalTask, EvalResult, EvalAnalysis models

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Evaluation tasks don't reflect real usage | High | Ground tasks in actual agent session transcripts |
| Automated optimization degrades some tools | Medium | A/B testing, only accept improvements, rollback capability |
| Evaluation overhead impacts performance | Low | Run evaluations asynchronously, cache results |
| Metric collection adds token overhead | Low | Minimal tracking in production, full tracking in eval mode |

## Notes

- Anthropic: "We relied on held-out test sets to ensure we did not overfit to our 'training' evaluations"
- Split evaluation tasks into train (80%) and test (20%) sets to prevent overfitting
- Consider using Claude's interleaved thinking to understand why agents make tool selection errors
- Future: integrate with CI to run evaluations on tool description changes
