---
title: "Ponytail Simplification Cuts for Agentic Eval and Skill Pack Trigger Harnesses"
component: "tools/evaluation"
work_type: "refactor"
status: PENDING
priority: "Medium"
created: "2026-08-06"
depends_on: []
---

## Goal

Remove the 14 over-engineering findings identified by the ponytail review of the uncommitted agentic tool-selection evaluation harness, the prompt-prefix byte-stability module, and the skill pack trigger benchmark, reducing the change by roughly 215 lines with no behavioral regression.

## Context

A ponytail (over-engineering only) review of the current working tree found speculative abstractions, hand-rolled helpers that duplicate stdlib or Pydantic behavior, dead parameters, recomputed values, and pure formatting noise across the newly added evaluation and skill pack modules. Each finding is a concrete, located cut with a named replacement.

The findings cluster into four groups:

1. **Typed empty factories** — `_agentic_models.py` defines five `_empty_*()` functions that return `[]`, while `benchmark.py` in the same change set already uses `default_factory=list[FixtureOutcome]`, proving the helpers are unnecessary.
2. **Protocol and model ceremony** — the Anthropic adapter declares three Protocols and a Pydantic resolution wrapper to describe a single `messages.create` call that is reached through a `cast` regardless.
3. **Dead or duplicated logic** — unused function parameters, an always-`None` tuple slot, recomputed benchmark metrics, single-caller wrappers exported only for tests, and an unused re-export.
4. **Diff noise** — `quality.json` and `refactoring.json` were reformatted (arrays exploded one element per line, `→` and `—` rewritten as `→` and `—`) alongside their genuine `keywords` and `when_to_use` additions.

The scoring path in `skill_pack/scoring.py` carries a hand-rolled 24-word stopword list plus bigram extraction whose entire output is one capped point; that path must be simplified only with a benchmark re-run confirming unchanged trigger accuracy.

## Scope

**in_scope**

- `src/cortex/tools/evaluation/_agentic_models.py` — remove the five empty-list factory functions.
- `src/cortex/tools/evaluation/_agentic_scoring.py` — inline `_response_satisfies`, drop unused `task` parameters, narrow the scorer return tuple.
- `src/cortex/tools/evaluation/_anthropic_client.py` — collapse the Protocol stack, replace `ModelClientResolution` with a union return.
- `src/cortex/tools/evaluation/_agentic_suite.py` — drop the unused `UnpairedReason` import and re-export.
- `src/cortex/tools/evaluation/_local_session.py` — remove `RegisteredToolProtocol` in favor of the FastMCP tool type.
- `src/cortex/discovery/prompt_prefix.py` — remove the `render_registered_tool_schema_payload` wrapper and the redundant `separators` argument.
- `src/cortex/tools/skill_pack/scoring.py` — simplify or remove the stopword and bigram phrase path, gated on a benchmark re-run.
- `src/cortex/tools/skill_pack/benchmark.py` — deduplicate metric computation, inline `load_fixture_set`.
- `src/cortex/tools/skill_pack/operations.py` — remove the `load_shipped_manifests` alias.
- `src/cortex/resources/skills/quality.json` and `refactoring.json` — revert formatting noise, keep the new metadata fields.
- Call-site and test updates required by the above.

**out_of_scope**

- Any change to what the agentic eval measures, the pairing invariant, or the scorecard contract.
- Any change to the byte-stability guarantees of `cortex://rules` or tool schema rendering.
- Adding new features, new eval modes, or new fixtures.
- Correctness, security, or performance fixes not listed above.
- Re-tuning skill pack scoring weights beyond preserving current benchmark figures.

## Approach

Work in four independent passes ordered by risk, running the quality gate after each so a regression is attributable to one pass.

Pass 1 is behavior-free mechanical cleanup: the empty factories, the unused import and re-export, unused parameters, and the JSON formatting revert. Pass 2 removes single-caller wrappers and updates the tests that import them, since those tests are the only consumers. Pass 3 collapses the Anthropic adapter typing surface, which touches one call site in `_run_impl.py` and its adapter tests. Pass 4 is the only pass with measurable risk: simplifying the phrase-scoring path in `scoring.py` must be validated by running the trigger benchmark before and after and asserting identical top-1 accuracy, recall, precision, and both false-positive rates; if any figure moves, revert that cut and record why.

Where a cut removes a symbol currently imported by a test, prefer updating the test to the surviving symbol over keeping the wrapper alive for test convenience.

## Implementation Steps

1. Delete `_empty_tool_calls`, `_empty_tool_results`, `_empty_str_list`, `_empty_agentic_results`, and `_empty_feedback` from `_agentic_models.py`; replace each `default_factory` reference with `list` and confirm the annotated field types still validate.
2. Remove the unused `UnpairedReason` import and its `__all__` entry from `_agentic_suite.py`.
3. Revert the array-explosion and Unicode-escape reformatting in `quality.json` and `refactoring.json`, preserving only the added `keywords` and `when_to_use` entries and the original `→`/`—` characters.
4. Inline `_response_satisfies` into `_score_positive` in `_agentic_scoring.py` as a single expression, and delete the unused `task` parameter from `_score_control`.
5. Narrow `_score_positive` and `_score_control` to return `tuple[bool, str]`, setting the `covered` value in `score_task` instead of threading an always-`None` third slot.
6. Delete `render_registered_tool_schema_payload` from `prompt_prefix.py`, move the composition into its caller and its test, and drop the redundant `separators` argument from `canonical_json`.
7. Delete `load_fixture_set` from `benchmark.py`, replacing its two call sites with `FixtureSet.model_validate_json(path.read_text(encoding="utf-8"))`.
8. Delete the `load_shipped_manifests` alias from `skill_pack/operations.py`, rename `_load_all_manifests` to a public name, and update the benchmark test import.
9. Delete `RegisteredToolProtocol` from `_local_session.py` and annotate `to_tool_schema` with the FastMCP tool type returned by `mcp.list_tools()`.
10. Collapse `MessagesApiProtocol`, `AnthropicSdkProtocol`, and `AsyncAnthropicFactory` in `_anthropic_client.py` to the single Protocol the adapter actually reads, relying on the existing `cast` for the factory.
11. Replace `ModelClientResolution` with a `ModelClientProtocol | AgenticSkipReason` return from `resolve_model_client`, and update the branch in `_run_impl._run_agentic_mode`.
12. Change `_positive_metrics` in `benchmark.py` to also return the positive hit count, and pass the already-computed `controls` and `near_misses` lists into `_paired_result` rather than re-deriving them.
13. Record the current trigger benchmark figures, then simplify the phrase path in `scoring.py` by scoring `when_to_use` through the existing keyword-matching helper over its non-stopword tokens; delete `_STOPWORDS`, `_when_to_use_bigrams`, and `_matched_phrases` if the figures are unchanged.
14. Run the full quality gate and the docs gate, and update the two guide documents if any renamed public symbol is referenced there.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read after change |
|------|--------------------|--------------|-------------------------------|
| 1 | `_empty_tool_calls`, `_empty_tool_results`, `_empty_str_list`, `_empty_agentic_results`, `_empty_feedback` | `src/`, `tests/` | `_agentic_models.py` |
| 2 | `UnpairedReason` | `src/cortex/tools/evaluation/` | `_agentic_suite.py`, `evaluation/__init__.py` |
| 3 | `→`, `—` | `src/cortex/resources/skills/` | `quality.json`, `refactoring.json` |
| 4-5 | `_response_satisfies`, `_score_control`, `_score_positive` | `src/`, `tests/` | `_agentic_scoring.py` |
| 6 | `render_registered_tool_schema_payload`, `separators` | `src/`, `tests/`, `docs/` | `prompt_prefix.py`, `test_prompt_prefix_stability.py` |
| 7-8 | `load_fixture_set`, `load_shipped_manifests`, `_load_all_manifests` | `src/`, `tests/` | `benchmark.py`, `operations.py` |
| 9 | `RegisteredToolProtocol` | `src/`, `tests/` | `_local_session.py` |
| 10-11 | `MessagesApiProtocol`, `AsyncAnthropicFactory`, `ModelClientResolution` | `src/`, `tests/` | `_anthropic_client.py`, `_run_impl.py` |
| 12 | `_positive_metrics`, `_paired_result` | `src/cortex/tools/skill_pack/` | `benchmark.py` |
| 13 | `_STOPWORDS`, `_when_to_use_bigrams`, `_matched_phrases`, `PHRASE_MATCH_SCORE` | `src/`, `tests/` | `scoring.py`, `test_skill_pack_trigger_benchmark.py` |
| 14 | Renamed public symbols | `docs/guides/` | `agentic-tool-selection-eval.md`, `prompt-prefix-byte-stability.md` |

## Dependencies

None. All target modules are present in the working tree; no other plan blocks this work.

## Success Criteria

- All 14 reviewed findings are either applied or explicitly recorded as rejected with a one-line reason in the plan's completion entry.
- Net line count across the targeted source files decreases by at least 180 lines.
- `run_quality_gate()` reports zero type, lint, format, and markdown errors.
- `run_docs_gate()` passes.
- The skill pack trigger benchmark reports identical `top1_accuracy`, `recall`, `precision`, `control_false_positive_rate`, and `near_miss_false_positive_rate` before and after step 13.
- No public behavior of `run_tool_evaluation(mode="agentic")`, `skill_pack(operation="discover")`, or the `cortex://rules` byte-stability contract changes.
- Test coverage for the touched modules stays at or above 95%.

## Testing Strategy

Target 95% coverage on every touched module, using the AAA pattern throughout.

Existing suites are the primary regression net and must pass unchanged in intent: `tests/tools/test_agentic_eval_scoring.py`, `tests/tools/test_agentic_eval_adapters.py`, `tests/tools/test_agentic_eval_harness.py`, `tests/tools/test_skill_pack_trigger_benchmark.py`, `tests/discovery/test_prompt_prefix_stability.py`, `tests/integration/test_resource_byte_stability.py`, and `tests/unit/test_cache_payload_stability_audit.py`. Where a test imports a symbol being deleted, update the import to the surviving symbol rather than reinstating the wrapper.

Negative cases to keep or add: an unpaired scorecard still refuses to carry `selection_accuracy`; a control fixture with any recommendation still fails; `resolve_model_client` still yields a typed skip when the `anthropic` extra is absent and when the API key is missing; `canonical_json` output stays byte-identical across processes after the `separators` removal.

Step 13 additionally requires a before/after comparison of the benchmark result object, asserted as an equality check on the five reported figures.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Simplifying the phrase-scoring path shifts trigger accuracy | Skill pack discovery regresses silently | Record benchmark figures before the change and assert equality on all five metrics; revert the cut if any figure moves |
| Removing Protocols weakens type coverage of the Anthropic adapter | Type checker loses a guard on SDK usage | Keep the one Protocol the adapter reads; rely on the existing `cast` boundary and confirm the type checker still passes with zero suppressions |
| Deleting test-only wrappers breaks imports | Test suite fails to collect | Update each importing test in the same commit as the deletion |
| The JSON formatting revert also drops the intended metadata additions | Skill pack discovery loses new keywords | Diff the reverted files against `HEAD` and confirm only `keywords` and `when_to_use` differ |
| `default_factory=list` changes validation behavior for typed list fields | Model construction errors at runtime | Rely on existing model construction tests; run the full evaluation test suite after step 1 |
| Concurrent commit pipeline touches the same files | Merge conflicts or lost edits | Wait for the running `/cortex/commit` workflow to finish before starting implementation |
