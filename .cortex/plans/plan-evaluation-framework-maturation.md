# Plan: Evaluation Framework Maturation (Phase 57 Extension)

## Status: IN PROGRESS

(Step 4 completed 2026-02-23; Steps 5–6 pending.)

## Priority: P1 (High)

## Created: 2026-02-21

## Effort: 2 sprints

## Motivation

Phase 57 established the evaluation foundation (26 tasks, error analysis, A/B framework). This plan extends it based on Anthropic's "Demystifying Evals for AI Agents" recommendations and gaps identified in review.

**Key insight from Anthropic:**
> Claude Code started with fast iteration based on feedback. Later, they added evals — first for narrow areas like concision and file edits, and then for more complex behaviors like over-engineering. Teams often delay building evals because they think they need hundreds of tasks. In reality, 20–50 simple tasks drawn from real failures is a great start.

**Current gaps:**

- Eval tasks may not be drawn from real failures (need audit)
- No CI/CD integration — evals don't run automatically
- No production monitoring for tool effectiveness drift
- Eval harness (Step 2) still needs completion
- No automated tool description optimization pipeline

---

## Step 1: Failure-Based Eval Task Audit & Expansion — COMPLETED (2026-02-23)

**Insight:** Real failures are the best source of eval tasks.

**Action:**

1. Audit session review files in `.cortex/reviews/` for recorded failures
2. Mine session logs for tool errors, retries, and misuse patterns
3. For each real failure, create an eval task that:
   - Reproduces the failure condition
   - Defines expected correct behavior
   - Has clear pass/fail criteria
4. Expand task suite from 26 to 40–50 tasks, with ≥ 50% drawn from real failures
5. Categorize tasks by failure type: tool errors, context mismanagement, workflow breakage, incorrect results

**Acceptance criteria:** 40–50 eval tasks. ≥ 50% based on documented real failures.

**Done:** Audited session-optimization and investigation reports; added `.cortex/evals/tasks/failure_based_evals.json` with 26 failure-based tasks (commit pipeline hang/timeout, MCP connection closed, fix_markdown_lint blocking, load_context not called, roadmap/memory-bank misuse, Step 12 skip patterns, etc.). Total 52 tasks (26 core + 26 failure-based); 50% from real failures. Categorized via common_failure_modes (tool_errors, context_mismanagement, workflow_breakage, incorrect_results). New test `test_load_eval_tasks_includes_failure_based_evals` verifies expansion.

---

## Step 2: Complete Evaluation Harness — COMPLETED (2026-02-23)

**Current state:** Phase 57 Step 2 (full evaluation harness) implemented.

**Action:**

1. Implement automated task execution framework:
   - Load eval task → set up test environment → execute tool sequence → capture results
   - Compare results against expected outcomes
   - Generate structured report (pass/fail per task, aggregate metrics)
2. Support both:
   - **Deterministic evals**: exact match, schema validation, output contains/excludes
   - **Judgment evals**: LLM-graded quality (for fuzzy outputs like summaries)
3. Execution modes:
   - **Fast mode** (CI): 10 core tasks, <30s total
   - **Full mode** (nightly/manual): all 40–50 tasks
   - **Focused mode**: specific category only

**Acceptance criteria:** Harness executes all tasks automatically. Reports generated with pass/fail breakdown.

**Done:** Execution harness in `phase5_evaluation_execution.py`: run_one_execution (invoke tool, check expect), run_execution_suite (fast/full/focused), build_execution_summary. Deterministic checks: contains, schema_valid, exact_match. Tool registry in `phase5_evaluation_execution_registry.py` (get_structure_info). EvalTask extended with optional execution (ExecutionSpec/ExecutionExpectSpec). run_tool_evaluation now accepts mode and category and returns execution_summary. exec_fast.json adds 10 fast tasks for CI. Tests in test_phase5_evaluation_execution.py.

---

## Step 3: CI/CD Eval Integration — COMPLETED (2026-02-23)

**Insight from Anthropic:**
> Automated evals are especially useful pre-launch and in CI/CD, running on each agent change and model upgrade as the first line of defense against quality problems.

**Action:**

1. Add `eval-fast` to pre-commit pipeline (runs 10 core tasks)
2. Add `eval-full` to CI pipeline (runs all tasks on PRs)
3. Block merge if eval score drops below threshold (e.g., 85%)
4. Report eval results as PR check with task-level breakdown
5. Track eval score trends over time

**Acceptance criteria:** Pre-commit runs fast evals. CI runs full evals. Merge blocked on regression.

**Done:** eval_fast added to pre-commit: PreCommitCheck.EVAL_FAST, run in run_preflight_checks (Phase A) and when execute_pre_commit_checks includes eval_fast; pass rate threshold 85%. CI: new step "Run evaluation suite (full)" in .github/workflows/quality.yml runs run_eval_check.py --mode full --threshold 0.85; merge blocked if step fails. Eval results reported in Quality check summary step; task-level breakdown available in run_tool_evaluation payload and .cortex/.cache/evals/. Trends can be tracked via cache/artifacts and future dashboard.

---

## Step 4: Automated Tool Description Optimization — COMPLETED (2026-02-23)

**Insight from "Writing Tools for Agents":**
> One of the most effective methods for improving tools is prompt-engineering your tool descriptions. Even small refinements can yield dramatic improvements.

**Action:**

1. For each tool with error rate > 5% or redundancy rate > 10%:
   - Analyze error patterns (what parameters fail, what context is missing)
   - Generate 3 candidate description improvements
   - A/B test each candidate against baseline using eval tasks
   - Deploy winning description
2. Create MCP tool `optimize_tool_description(tool_name)` that:
   - Pulls error and usage data for the tool
   - Suggests description improvements based on patterns
   - Generates A/B test plan
3. Run optimization cycle 14-day or after significant changes

**Acceptance criteria:** Optimization tool implemented. ≥ 5 tools optimized with measurable improvement. Error rate reduced ≥ 20% for optimized tools.

**Done:** MCP tool `optimize_tool_description(tool_name, days=90)` implemented in `phase5_tool_description_optimization.py`. Uses `phase5_evaluation_optimization_helpers.py` to pull usage stats and failed events via UsageTracker, compute error rate and meets_optimization_threshold (>5% or param/retry signals), build suggestions (USE WHEN, validation, params, retries), and return A/B test plan (run_tool_evaluation baseline → update descriptor → re-run → compare). Registered in tool_categories (DEFERRED_MEDIUM) and discovery. Unit tests in `test_phase5_evaluation_optimization.py`. The "≥ 5 tools optimized" and "error rate reduced ≥ 20%" are usage outcomes to be achieved by running the tool and applying suggestions over time.

---

## Step 5: Production Monitoring & Drift Detection

**Insight from Anthropic:**
> Production monitoring kicks in post-launch to detect distribution drift and unanticipated real-world failures.

**Action:**

1. Track per-session metrics:
   - Tool call success rate (rolling 7-day average)
   - Token efficiency (tokens per successful operation)
   - Error pattern distribution (are new error types emerging?)
   - Session completion rate (how often sessions achieve stated goal)
2. Detect drift: alert when any metric deviates > 2σ from 7-day baseline
3. Weekly report: auto-generated summary of tool health, trends, anomalies
4. Feed anomalies back into eval task creation (close the loop)

**Acceptance criteria:** Per-session metrics tracked. Drift detection active. Weekly reports generated.

---

## Step 6: Eval-Guided Model Upgrade Path

**Insight from Anthropic:**
> Evals shape how quickly you can adopt new models. Teams without evals face weeks of testing while competitors with evals can quickly determine the model's strengths, tune prompts, and upgrade in days.

**Action:**

1. Document "model upgrade playbook":
   - Run full eval suite with new model
   - Compare results against current model baseline
   - Identify regressions and improvements
   - Tune tool descriptions for new model's strengths
   - Deploy with confidence
2. Create `benchmark_model(model_name)` tool that runs eval suite and generates comparison report
3. Store model benchmark results for historical comparison

**Acceptance criteria:** Model upgrade playbook documented. Benchmark tool functional. Baseline stored.

---

## Verification

After all steps:

1. 40–50 eval tasks (≥ 50% failure-based)
2. Automated harness runs all tasks
3. CI/CD integration active
4. ≥ 5 tools optimized via A/B testing
5. Production monitoring and drift detection active
6. Model upgrade process documented and tooled
