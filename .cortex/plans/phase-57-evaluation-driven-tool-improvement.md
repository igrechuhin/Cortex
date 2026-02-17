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

- [ ] Create 20+ evaluation tasks covering core Cortex workflows:
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

- [ ] For each task, define:
  - Expected tool calls (which tools, in what order)
  - Expected outcome (success criteria)
  - Token budget baseline (expected token consumption)
  - Common failure modes
- [x] Store tasks in `.cortex/evals/tasks/` as JSON (initial `core_workflows.json` seeded; extend with additional tasks in follow-up work)

### Step 2: Build Evaluation Harness

- [ ] Create `ToolEvaluationHarness` class:

  ```python
  class ToolEvaluationHarness:
      async def run_task(self, task: EvalTask) -> EvalResult:
          """Run a single evaluation task and measure results."""
      async def run_suite(self, suite: list[EvalTask]) -> EvalSuiteResult:
          """Run all tasks and aggregate metrics."""
      def analyze_results(self, results: EvalSuiteResult) -> EvalAnalysis:
          """Analyze results for patterns and improvement opportunities."""
  ```

- [ ] Track metrics per task:
  - **Success/failure** — did the workflow complete correctly?
  - **Tool calls** — count, sequence, any redundant calls
  - **Token consumption** — total input + output tokens
  - **Errors** — count, types, retries needed
  - **Latency** — time to complete each tool call and overall task
- [ ] Track aggregate metrics:
  - Overall success rate by task category
  - Average token consumption by task category
  - Most common error types across all tasks
  - Tool usage patterns (which tools called together)
- [ ] Output results to `.cortex/.cache/evals/` as JSON

### Step 3: Error Pattern Analysis

- [ ] Extend usage tracking to capture error patterns:
  - Tool name + error type + frequency
  - Parameter validation failures (which params, what values)
  - Retry patterns (how many retries before success, what changed)
  - "Wasted" tool calls (calls whose results were ignored by agent)
- [ ] Create `analyze_error_patterns()` tool:
  - Surfaces top 10 recurring errors
  - Identifies tools with highest retry rates
  - Suggests specific improvements for each pattern
- [ ] Store error patterns in `.cortex/.cache/evals/error_patterns.json`

### Step 4: Automated Tool Description Optimization

- [ ] Create `optimize_tool_descriptions` workflow:
  1. Run evaluation suite to get baseline metrics
  2. Collect all tool transcripts (calls + responses + agent reasoning)
  3. Feed transcripts to Claude with prompt: "Analyze these tool usage transcripts and suggest improvements to tool descriptions, parameter names, and examples"
  4. Apply suggested improvements to tool descriptions
  5. Re-run evaluation suite to measure improvement
  6. Accept changes that improve metrics, reject those that don't
- [ ] Implement A/B testing for tool descriptions:
  - Run same tasks with original vs. optimized descriptions
  - Compare success rates, token usage, error rates
  - Keep whichever performs better
- [ ] Store optimization history in `.cortex/.cache/evals/optimization_history.json`

### Step 5: Continuous Improvement Pipeline

- [ ] Create `run_tool_evaluation` MCP tool:
  - Runs full evaluation suite
  - Reports results summary
  - Suggests improvements
- [ ] Integrate with end-of-session analysis:
  - Track which tools were used in the session
  - Compare against expected patterns
  - Flag anomalies (unusual tool sequences, high retry counts)
- [ ] Create evaluation dashboard (Markdown report):
  - Overall tool effectiveness score
  - Top 5 tools by usage and by improvement needed
  - Trending error patterns
  - Token efficiency trends

### Step 6: Testing and Validation

- [ ] Unit tests for evaluation harness (95%+ coverage)
- [ ] Unit tests for error pattern analysis
- [ ] Integration test: run evaluation suite and verify metrics collection
- [ ] Verify evaluation results are reproducible
- [ ] Test A/B comparison logic

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
