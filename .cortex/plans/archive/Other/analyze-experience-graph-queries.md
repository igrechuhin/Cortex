---
title: "Rewire /cortex/analyze from Transcript Scraping to Experience Queries"
component: "analyze"
work_type: "refactor"
status: DONE
priority: "Medium"
created: "2026-07-19"
depends_on: ["unified-experience-store"]
---

## Goal

Replace the transcript-scraping mistake-pattern detection in the `/cortex/analyze` pipeline with structured queries over the experience store: sibling nodes under the same parent where one passed the quality gate and one failed become before/after evidence pairs feeding `failure_based_evals.json` and Synapse rule recommendations.

## Context

The Experience Graphs paper (arXiv:2606.29823) argues that learning data should be database queries, not post-hoc log scraping: preference pairs are sibling nodes under the same parent where one scored higher — "a graph pattern match, not a post-hoc log scrape." Cortex's `/cortex/analyze` pipeline currently mines session transcripts for mistake patterns — exactly the fragile approach the paper argues against. With attempts stored as sibling nodes with fitness (plan `unified-experience-store`), failure→fix pairs can be extracted deterministically with evidence attached, strengthening the Compound step of the Plan→Work→Review→Compound loop.

## Scope

**in_scope**

- Query layer: `preference_pairs(session|time-range)` returning sibling node pairs (same parent, divergent gate outcomes) with artifact references.
- Integration into the analyze pipeline (analyze-session step): consume pairs as primary evidence for mistake patterns; keep transcript scraping as fallback when the store has no coverage for a session.
- Emission of evidence-linked entries into `failure_based_evals.json` with node ids and artifact refs.
- Synapse rule recommendations that cite the node pairs justifying them.

**out_of_scope**

- Experience-store schema and instrumentation (plan: unified-experience-store).
- Rule pruning/provenance lifecycle (plan: synapse-rule-provenance).
- Any RL training export (SFT/DPO datasets) — dev-tool analysis only.
- Removing transcript analysis entirely; it remains a fallback.

## Approach

Add a typed analytics module over the experience store exposing graph pattern queries (preference pairs, repeated-failure clusters, fitness trends per task type). Modify the analyze-session step of the analyze pipeline to query this module first, mapping pairs into the existing mistake-pattern model with `evidence` fields (node ids, artifact refs). Transcript scraping runs only for sessions predating the store or with recording gaps, and its findings are marked lower-confidence.

## Implementation Steps

1. Implement `ExperienceAnalytics` queries: `preference_pairs`, `repeated_failures`, `fitness_by_task_type` (Pydantic result models).
2. Extend the mistake-pattern model with an `evidence` field (node ids + artifact refs + confidence source: graph|transcript).
3. Integrate graph queries into the analyze-session step; gate transcript scraping behind a coverage check.
4. Write evidence-linked entries to `failure_based_evals.json` (schema-versioned addition, backward compatible).
5. Attach citing evidence to Synapse rule recommendations emitted by the analyze pipeline.
6. Tests over fixture graphs (constructed sibling pairs) and legacy-fallback paths.
7. Update analyze prompt docs and memory bank.

## Verification Checklist

- Step 2: search `rg "mistake" src/` for the pattern model and all constructors; confirm evidence field threaded through; re-read model file after changes.
- Step 3: confirm the coverage check logic (`rg "analyze-session" .claude/ src/`) and that fallback still passes existing tests.
- Step 4: validate `failure_based_evals.json` consumers still parse the extended schema (`rg "failure_based_evals" src/ tests/`).
- Step 6: `run_quality_gate()` green.

## Dependencies

- Plan: `unified-experience-store` (`.cortex/plans/unified-experience-store.md`) — provides sibling nodes and fitness.

## Success Criteria

- Given a fixture graph with a failed and a passed sibling under one parent, analyze emits exactly one preference pair with correct node ids and artifact refs.
- `failure_based_evals.json` entries produced from graph queries carry evidence links; legacy entries remain valid.
- Sessions without store coverage still produce analyze output via transcript fallback, marked lower-confidence.
- Rule recommendations cite node-pair evidence.
- Quality gate green; ≥95% coverage on new analytics module.

## Testing Strategy

- Unit tests (AAA): each analytics query on constructed graphs, including multi-sibling and no-pair cases.
- Integration tests: analyze-session step end-to-end on fixture store; fallback path on empty store; evals-file schema compatibility.
- Negative cases: orphan nodes, missing artifacts, tied fitness siblings.
- Target: ≥95% coverage on new modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Sparse early data makes graph analysis look worse than scraping | Coverage check chooses source per session; confidence labeling keeps both usable |
| Evals-file schema change breaks consumers | Additive versioned schema; compatibility tests for existing readers |
| Tied or noisy fitness yields false preference pairs | Require strict gate pass/fail divergence; exclude ties |
| Analyze pipeline runtime grows | Indexed queries; bound time-range; measure in tests |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._

## Review Follow-Up Gaps

- [x] Write evidence-linked entries to `failure_based_evals.json` from `preference_pairs()` output (plan step 4): `EvidenceLink`/`EvalTask.evidence` exist but nothing constructs entries from graph queries yet (evidence: `src/cortex/experience/analytics.py`, `src/cortex/tools/evaluation/_models.py`). **Closed**: `src/cortex/experience/failure_evals.py::preference_pairs_to_eval_tasks()` builds evidence-linked `EvalTask` entries from `PreferencePair` results; `upsert_eval_tasks()` writes/dedups them into `failure_based_evals.json` by id (idempotent, preserves hand-written entries — verified by `tests/experience/test_failure_evals.py::test_upsert_eval_tasks_idempotent_on_repeated_calls` and `::test_upsert_eval_tasks_preserves_unrelated_existing_entries`, 98.08% coverage). Reachable end-to-end via `src/cortex/tools/session/pipeline_handoff_analytics.py::op_write_failure_evals()`.
- [x] Register an MCP tool exposing `preference_pairs`/`repeated_failures`/`fitness_by_task_type` and wire the coverage-check + transcript-fallback flow into the analyze-session step (plan step 3): currently only documented as intent (evidence: `.cortex/synapse/cursor-agents/analyze-session.md`, `.claude/agents/analyze-session.md`). **Closed**: `src/cortex/tools/session/pipeline_handoff.py` registers `PREFERENCE_PAIRS`/`REPEATED_FAILURES`/`FITNESS_BY_TASK_TYPE`/`WRITE_FAILURE_EVALS` `pipeline_handoff` operations, dispatched to `op_preference_pairs`/`op_repeated_failures`/`op_fitness_by_task_type`/`op_write_failure_evals` in `src/cortex/tools/session/pipeline_handoff_analytics.py` (coverage-checked via `_open_core`/`list_nodes`/`list_sessions`, returning `"status":"no_coverage"` when the store/session has no data). `.claude/agents/analyze-session.md` Step 1 calls these operations as the primary evidence source and falls back to transcript scraping on `no_coverage`/`coverage:false` (mirrored in `.cortex/synapse/cursor-agents/analyze-session.md`). Verified: `tests/unit/tools/test_pipeline_handoff_analytics_op.py` (15 tests), `tests/experience/test_experience_store.py`/`test_experience_analytics.py`.
- [x] Attach citing node-pair evidence to Synapse rule recommendations emitted by the analyze pipeline (plan step 5). **Closed**: `.claude/agents/analyze-session.md` Step 3 requires an `Evidence: node <failed_node.id> (parent <parent_id>)` citation on every graph-sourced recommendation and Step 4 carries an `evidence_citations` array through the phase handoff; `.claude/agents/analyze-compact.md` (and Cursor mirror) renders `Evidence: node <node_id> (parent <parent_id>)` next to Synapse rule recommendations derived from `evidence_citations` in the session-phase handoff.

## Partial Progress Log

- 2026-07-20: Implemented experience-graph analytics query layer (`preference_pairs`, `repeated_failures`, `fitness_by_task_type` pure functions + Pydantic result models), wired into `ExperienceStoreCore`/`ExperienceStore`, extended `EvalTask` with `EvidenceLink`/`evidence` field (backward-compatible), added unit+integration tests, and documented the intended graph-first coverage-check flow in the analyze-session prompts (plan steps 1, 2, 6-partial) — files: src/cortex/experience/analytics_models.py, src/cortex/experience/analytics.py, src/cortex/experience/store_core.py, src/cortex/experience/store.py, src/cortex/tools/evaluation/_models.py, tests/experience/test_experience_analytics.py, tests/experience/test_experience_store.py, .claude/agents/analyze-session.md, .cortex/synapse/cursor-agents/analyze-session.md
- 2026-07-20 (verification pass): Verified all 3 Review Follow-Up Gaps are code-complete from a prior uncommitted pass in the working tree; no code changes needed. Verified (no change needed, read + ran tests): `src/cortex/experience/analytics.py` (`preference_pairs`/`repeated_failures`/`fitness_by_task_type` — strict COMPLETED/FAILED status divergence, one pair per failed sibling paired with the highest-fitness passed sibling, ties/None-fitness excluded by construction; 100% coverage via `tests/experience/test_experience_analytics.py`), `src/cortex/experience/failure_evals.py` (`preference_pairs_to_eval_tasks`/`upsert_eval_tasks` — id-keyed upsert, idempotent, preserves unrelated entries; 98.08% coverage via `tests/experience/test_failure_evals.py`), `src/cortex/tools/evaluation/_models.py` (`EvalTask.evidence: list[EvidenceLink] = Field(default_factory=...)`, `model_config = ConfigDict(extra=EXTRA_ALLOW)` — additive/backward-compatible, legacy entries without `evidence` parse fine), `src/cortex/tools/session/pipeline_handoff_analytics.py` + `pipeline_handoff.py` (`PREFERENCE_PAIRS`/`REPEATED_FAILURES`/`FITNESS_BY_TASK_TYPE`/`WRITE_FAILURE_EVALS` operations registered and dispatched; 15 passing tests in `tests/unit/tools/test_pipeline_handoff_analytics_op.py`), `.claude/agents/analyze-session.md` + `.cortex/synapse/cursor-agents/analyze-session.md` (Step 1 coverage-checked graph-first query with transcript fallback on `no_coverage`; Step 3 mandates `Evidence: node <id> (parent <parent_id>)` citation; Step 4 threads `evidence_citations` through the handoff), `.claude/agents/analyze-compact.md` + `.cortex/synapse/cursor-agents/analyze-compact.md` (renders `Evidence: node <node_id> (parent <parent_id>)` next to Synapse rule recommendations from `evidence_citations`). Ran the 4 targeted test files (46 tests, all pass) plus `run_quality_gate()` (`preflight_passed: true`, 0 errors, 0 warnings across fix_errors/quality/format/synapse_format/synapse_lint/spelling/type_check/tests/markdown). All 3 Review Follow-Up Gaps closed; all Success Criteria in this plan are met. Files touched this pass: only this plan file (checkbox + evidence annotations, this log entry) — no source/test changes were needed.
