# Session Optimization Follow-Ups: Phase 57 Evaluation Framework and Context Budgets (2026-02-17)

**Status:** PENDING

## Goal

Harden context-budget validation and zero-file safeguards, expand the Phase 57 evaluation task suite, and integrate rules indexing and evaluation dashboards so future sessions can use `run_tool_evaluation` and context analytics more effectively.

## Context

- Context analytics show ~49% average token utilization with 6.22 files selected per `load_context` call and solid relevance (~0.615), but a few calls have `token_budget=0` or zero selected files.
- Phase 57 introduced `run_tool_evaluation` and core evaluation models plus a seeded `.cortex/evals/tasks/core_workflows.json` suite, with new tests added to cover harness behavior.
- Rules manager is enabled but currently has `indexed_files=0`, so prompts lean heavily on AGENTS and the memory bank for standards.

## Tasks

1. **Context Budget Guardrails**
   - [ ] Add validation in `load_context` / callers to reject `token_budget=0` for non-trivial tasks (implement/add, fix/debug, refactor, testing, optimization).
   - [ ] Emit structured warnings when a non-trivial task results in zero selected files.
   - [ ] Ensure prompts (implement, commit, analyze) fall back to learned default budgets per task type when no explicit budget is provided.

2. **Evaluation Suite Expansion (Phase 57)**
   - [ ] Add evaluation tasks for memory-bank operations (compaction, `validate` with `roadmap_sync`, `manage_file` append helpers).
   - [ ] Add evaluation tasks for commit pipeline helpers (`run_preflight_checks`, `run_docs_and_memory_bank_sync`).
   - [ ] Split `.cortex/evals/tasks/core_workflows.json` into logical categories if it grows too large, keeping each file focused.

3. **Dashboards and Reporting**
   - [ ] Implement a small report helper that consumes `EvalAnalysis` and writes Markdown dashboards (category success rates, top error patterns) next to `last_suite.json`.
   - [ ] Wire an optional hook from analyze/commit flows to link to the latest evaluation report when available.

4. **Rules Indexing and Integration**
   - [ ] Run `rules(operation="index")` and confirm `rules_manager_status.indexed_files > 0`.
   - [ ] Update implement/analyze prompts to treat rules as a first-class source of coding standards when indexing is enabled.
   - [ ] Add a troubleshooting note for cases where rules are enabled but `indexed_files=0` so agents know to reindex.

## Success Criteria

- `load_context` is never invoked with `token_budget=0` for non-trivial tasks, and zero-file selections for such tasks are treated as anomalies.
- Evaluation suite covers core memory-bank and commit-pipeline workflows in addition to existing core workflows.
- A Markdown evaluation dashboard is generated alongside `last_suite.json` and referenced from at least one review or analyze report.
- Rules indexing is active (non-zero indexed files) and contributes relevant rules to implement/analyze flows.
