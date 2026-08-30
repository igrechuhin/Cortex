---
title: "Decompose oversized tool modules — remainder"
component: tools
work_type: refactor
status: IN_PROGRESS
priority: High
created: 2026-03-22
depends_on: []
---

## Goal

Split every `src/cortex/tools/**/*.py` file that exceeds 400 lines into focused
sub-modules, and bring every function within those files to ≤30 logical lines.
This completes the long-running PARTIAL roadmap item and is the primary lever for
advancing Architecture and Maintainability scores from 8 → 9.

## Context

Progress log shows four PARTIAL batches (2026-03-21) with remaining violations.
Current over-limit files (by `wc -l`):

| File | Lines | Excess |
|------|-------|--------|
| `tools/session/pipeline_handoff.py` | 522 | +122 |
| `tools/usage/usage_analytics.py` | 496 | +96 |
| `tools/synapse/prompts.py` | 465 | +65 |
| `tools/files/markdown_lint_core.py` | 457 | +57 |
| `tools/execution/pre_commit_detached.py` | 453 | +53 |
| `tools/context/effectiveness_operations.py` | 405 | +5 |

Function-length violations may exist within any of these files. The quality gate
reports them via `function_length_violations` in `run_quality_gate()` output.

## Implementation Steps

Work one file per sub-task. Validate with `run_quality_gate()` after each file.

### Step 1: Scope all violations

Run `run_quality_gate()` and extract `file_size_violations` and
`function_length_violations`. Cross-check against the table above. Confirm the full
list before starting any splits.

**Verification checklist:**

- `file_size_violations` list captured.
- `function_length_violations` list captured.
- No file or function in the list is already at/under limit (stale entry).

### Step 2: Split `pipeline_handoff.py` (522 lines)

**Done (2026-03-22):** Split into `pipeline_handoff_io.py`, `pipeline_handoff_validation.py`, and thin `pipeline_handoff.py` facade; quality gate passed.

Read the file. Identify cohesive responsibility groups:

- State read/write operations → `pipeline_handoff_io.py`
- Phase validation logic → `pipeline_handoff_validation.py`
- Thin dispatcher stays in `pipeline_handoff.py` (public API unchanged)

Update all import sites. Run `run_quality_gate()`.

**Verification checklist:**

- `pipeline_handoff.py` ≤400 lines after split.
- All new files ≤400 lines.
- No function in any new file exceeds 30 lines.
- All existing tests pass; no patch-target changes that break mocks.

### Step 3: Split `usage_analytics.py` (496 lines)

**Done (2026-03-22):** Collection helpers → `analytics_collection.py`; resource handlers → `usage_analytics_resources.py`; thin `usage_analytics.py` tools facade (~300 lines). Patch target `_get_tracker` / `get_usage_tracker` preserved for tests.

Read the file. Identify groups:

- Data collection helpers → `analytics_collection.py` (already partially split per
  `analytics_models.py`, `analytics_formatters.py`, `analytics_impl.py`; check what
  remains in the main file).
- Aggregation logic → move to nearest existing helper or new `analytics_aggregation.py`.

**Verification checklist:**

- `usage_analytics.py` ≤400 lines.
- `run_quality_gate()` passes.

### Step 4: Split `synapse/prompts.py` (465 lines)

**Done (2026-03-22):** Split into `prompts_content.py` (icons + Claude tool rewrite constants), `prompts_paths.py` (discovery + manifest/content load + testable `_paths_anchor()`), `prompts_registration.py` (MCP registration + manifest walk), `prompts_agents.py` (cursor/claude agent sync + frontmatter inject), and thin `prompts.py` facade (~107 lines). Tests patch `prompts_paths` / `prompts_agents` where implementation moved; `process_prompt_info` calls facade `create_prompt_function` for patchability.

**Verification checklist:**

- `prompts.py` ≤400 lines.
- `run_quality_gate()` passes.
- Synapse format/lint checks still pass (synapse_format, synapse_lint in gate output).

### Step 5: Split `markdown_lint_core.py` (457 lines)

**Done (2026-03-22):** Cache persistence and per-file progress → `markdown_lint_cache_updates.py` (`after_one_file`, `_update_markdown_lint_cache_from_results`, `update_markdown_lint_cache_safe`); `markdown_lint_core.py` re-exports stable symbols (~376 lines). Tests patch `markdown_lint_cache_updates` for moved helpers.

Read the file alongside `markdown_lint_run.py` (353 lines) and
`markdown_lint_helpers.py` (327 lines). Identify what remains in `_core.py`:

- Cache management → already in `markdown_lint_cache.py`?
- Core lint execution → `markdown_lint_executor.py`
- Result parsing → `markdown_lint_parser.py`

**Verification checklist:**

- `markdown_lint_core.py` ≤400 lines.
- All markdown lint tests pass.
- `run_quality_gate()` passes.

### Step 6: Split `pre_commit_detached.py` (453 lines)

**Done (2026-03-22):** Subprocess spawn (`Popen`, worker argv, log redirection) and async polling (`poll_for_result`, result-file reads, timeout/dead-worker envelopes) → `pre_commit_process.py`. `pre_commit_detached.py` keeps hashing, cache discovery, job interpretation, and `run_checks_detached` / `start_pre_commit_job_impl` (~313 lines). `poll_for_result` and `spawn_detached_worker` re-exported from facade for test patch targets.

Read alongside `pre_commit_worker.py` (352 lines). Identify groups:

- Process lifecycle (spawn/poll/kill) → `pre_commit_process.py`
- Output collection → already in `pre_commit_helpers_*`?
- Detached state machine → stays in `pre_commit_detached.py` (slim)

**Verification checklist:**

- `pre_commit_detached.py` ≤400 lines.
- `run_quality_gate()` passes.
- Phase A pipeline integration tests pass.

### Step 7: Trim `effectiveness_operations.py` (405 lines)

This is 5 lines over. Read the file; likely one function or a block of constants can
move to `effectiveness_operations_insights.py` (373 lines, has room).

**Verification checklist:**

- `effectiveness_operations.py` ≤400 lines.
- `run_quality_gate()` passes.

### Step 8: Function-length pass

For every function flagged in Step 1's `function_length_violations`: extract a
`_helper` at file scope. Keep the public function as a thin caller.

**Verification checklist:**

- `function_length_violations` is empty in `run_quality_gate()` output.

### Step 9: Final gate and memory bank update

Run `run_quality_gate()` one final time. All checks must pass. Then update
`activeContext.md` and `progress.md` via `plan(operation="complete", ...)`.

**Verification checklist:**

- `file_size_violations: []`
- `function_length_violations: []`
- `tests_passed` ≥ 5401, `coverage` ≥ 0.90
- `preflight_passed: true`

## Dependencies

- Steps 2–7 are independent of each other and can be batched if context allows.
- Step 8 depends on Steps 2–7 completing (file splits may resolve some function
  violations automatically).

## Success Criteria

1. Zero files over 400 lines in `src/cortex/tools/`.
2. Zero functions over 30 lines in any split file.
3. Quality gate passes with no test regressions.
4. Architecture and Maintainability metrics eligible to advance from 8 → 9.
5. PARTIAL roadmap entry removed; progress entry added for 2026-03-22.

## Testing Strategy (95% coverage target)

- No new test files needed for pure splits (existing tests cover public APIs).
- Update mock patch targets in any test that patches a symbol being moved.
- Add boundary tests in `tests/unit/test_decomposed_tool_module_boundaries.py`
  (already exists per progress log) for each new module's public surface.
- Coverage must not drop below 90% after each step.
