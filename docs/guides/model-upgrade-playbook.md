# Model Upgrade Playbook

This playbook describes how to adopt a new model (e.g. a new Claude or other provider model) with confidence using the evaluation framework. It aligns with Anthropic’s guidance: evals shape how quickly you can adopt new models; teams with evals can quickly determine strengths, tune prompts, and upgrade in days.

**Migration note:** The `benchmark_model` MCP tool was unpublished in 2026-03-02. Use `run_tool_evaluation(mode="full")` and manually store/compare results in `.cortex/.cache/evals/model_benchmarks.json`. Programmatic use can call `benchmark_model` via `cortex.tools.evaluation.model_benchmark`.

## Prerequisites

- Evaluation framework in place (Phase 57): task suite, harness, execution-based evals.
- Full eval suite runs successfully with the current model (`run_tool_evaluation(mode="full")` or CI “Run evaluation suite (full)”).
- Optional: a stored baseline for the current model (see “Store baseline” below).

## Steps

### 1. Run full eval suite with new model

- Run the full evaluation suite using the **new** model (e.g. by switching the agent/model in your environment and invoking the eval).
- Use the MCP tool: `run_tool_evaluation(mode="full")`.
- Record the run by saving the JSON output to `.cortex/.cache/evals/model_benchmarks.json` (or use `benchmark_model` from `cortex.tools.evaluation.model_benchmark` programmatically). If you have a baseline, produce a comparison report manually or via the handler.

### 2. Compare results against current model baseline

- If you have a baseline (stored via `benchmark_model(model_name="current")` or a named model), `benchmark_model` returns a comparison report:
  - Overall success rate delta (new vs baseline).
  - Execution pass rate delta (execution-based tasks).
  - **Regressions**: task IDs that passed on baseline but failed on the new model.
  - **Improvements**: task IDs that failed on baseline but passed on the new model.
- Build this comparison from the eval JSON and stored baseline; use `benchmark_model` programmatically if available. Use the report to decide whether the new model is acceptable or needs tuning.

### 3. Identify regressions and improvements

- **Regressions**: Fix by tuning tool descriptions, prompts, or workflows for the new model; re-run the eval and re-compare.
- **Improvements**: Note them for documentation; no change required unless you want to raise the bar for the baseline.

### 4. Tune tool descriptions for the new model

- Use `optimize_tool_description(tool_name)` for tools that regressed or have high error rates.
- Apply the suggested description improvements and re-run the eval to validate (A/B style).
- Re-run the full eval after tuning and update the stored run (or call `benchmark_model` programmatically).

### 5. Deploy with confidence

- When the comparison report shows no unacceptable regressions and (optionally) execution pass rate meets your threshold (e.g. ≥ 85%), you can deploy the new model.
- Update the baseline to the new model when it becomes the default: store the run under the baseline name in `model_benchmarks.json` (or use `benchmark_model` programmatically) so future upgrades compare against this run.

## Storing and using baselines

- **Store a baseline**: Run the full eval with your **current** production model, then save the result to `.cortex/.cache/evals/model_benchmarks.json` under a model name (e.g. `current` or `claude-sonnet-4`). Or call `benchmark_model(model_name="current")` from `cortex.tools.evaluation.model_benchmark` programmatically.
- **Compare on upgrade**: When evaluating a new model, run the full eval with the new model, store the result, and compare to the baseline run in `model_benchmarks.json`. Or use `benchmark_model(model_name="<new-model-id>", baseline_model_name="current")` programmatically.
- **Historical comparison**: Stored benchmarks are kept in the same cache file; compare runs manually or via the `benchmark_model` handler.

## Summary

1. Run full eval with new model.
2. Store the result and compare to baseline (manually or via `benchmark_model` from `cortex.tools.evaluation.model_benchmark`).
3. Address regressions (tune tools/prompts); re-run eval and benchmark as needed.
4. When metrics are acceptable, deploy and optionally update the baseline.
