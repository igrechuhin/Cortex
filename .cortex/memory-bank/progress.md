<!-- memory_type: milestone -->
# Progress Log

## 2026-08-15

- <!-- memory_type: status -->
- **RulesIndexer Recursive .mdc Discovery and Rules Reindex Synapse Wiring** - COMPLETE. `find_rule_files` now uses `rglob` instead of a one-level `iterdir`+`glob` scan, and the rule-file pattern set gained `*.mdc`, so nested Synapse rules under `rules/<lang>/<name>.mdc` are discovered. Extracted a sync `build_synapse_manager(project_root, optimization_config)` helper in `factory_optimization.py` (the async `_create_synapse_manager` now delegates to it) and wired a `synapse_manager` into the rules manager construction in both `factory_optimization.py` and `container_optimization.py`. New `test_find_rule_files_nested_mdc` regression test. Coverage 91.36%.

## 2026-08-08

- **PHP Framework/Language Adapter Support** - COMPLETE. Added a PHP framework adapter (`php_adapter.py`, `php_parsing.py`) under `services/framework_adapters/`, and wired PHP detection/routing into `language_detector.py`, `language_quality_router.py`, `framework_adapters/detection.py`, `hook_templates.py`, and `core/constants.py`. New tests in `test_php_adapter.py`; existing detection/router/hook-template/pre-commit-registry tests updated. Quality gate green, coverage 91.26%.
- <!-- memory_type: status -->
- **Persistent Content-Hash Phase A Fingerprinting** - COMPLETE. Added `pre_commit_fingerprint_store.py` for cross-process, git-HEAD-keyed fingerprint persistence, and switched `compute_git_file_hash` to hash changed-file contents (not just names) via `_hash_source_contents`, closing a gap where an autofix pass rewriting content without changing the file set was silently skipped. `PipelineDirtyTracker.reset()` now takes `project_root` to also clear the persisted fingerprint. Wired through `pre_commit_tools_execute_checks.py`, `pre_commit_worker.py`, `pre_commit_zero_arg_tools.py`, and `session_goal_store.py`. New `test_pre_commit_fingerprint_store.py`; `test_commit_wf.py` updated.

## 2026-08-06

- **Agentic Tool-Selection Evaluation Harness** - COMPLETE. Agent-in-the-loop tool-selection eval mode with structurally enforced paired reporting (no accuracy figure without both negative kinds), kind/covered_by fixture taxonomy, 13 negative fixtures, optional lazily-imported anthropic extra, and live FastMCP schema exposure with explicit visibility gating. 61 new tests; quality gate clean, coverage 91.34%.
- **Prompt-Prefix Byte Stability Audit for Tool Schemas and Resources** - COMPLETE. Tool-schema payload and cortex:// resource bodies are now byte-stable across renders; last_indexed relocated from the cortex://rules body to an explicit rules diagnostics operation; determinism enforced by sorted name accessors, sort_keys on agent-visible json.dumps, and an AST sort_keys pre-commit audit; locked by cross-process PYTHONHASHSEED tool-schema tests and per-resource byte-equality tests with mutation guards. 30 tests added; quality and docs gates green.
- **Skill Pack Trigger Accuracy Benchmark and Description Tuning** - COMPLETE. Labeled 24-fixture trigger benchmark with pairing enforced in the runner (no accuracy figure without both a control and a near-miss); zero-signal fallback removed from _do_discover so a no-match query yields an empty recommendation with an explicit reason; token-level scorer with capped keyword contribution, non-stopword bigram when_to_use matching, and a recommendation floor; refactoring and quality manifests tuned. Top-1 0.9167 to 1.0, control FP 1.0 to 0.0, near-miss FP 0.2857 to 0.1429. Glossary gained "Skill pack". 28 tests added; quality and docs gates green.
- **Agent Skills Specification Interoperability Assessment** - COMPLETE. Field-by-field comparison of SkillPackManifest against the Agent Skills SKILL.md spec in both export and import directions; explicit NO-GO recorded with revisit conditions in the wiki. Documentation only, no code or schema changes.
- **Ponytail Simplification Cuts for Agentic Eval and Skill Pack Trigger Harnesses** - COMPLETE. All 14 reviewed over-engineering findings removed across the agentic eval, prompt-prefix, and skill pack trigger modules; net -180 lines with zero behavior change and identical trigger benchmark figures.
- **Delete Unreferenced Protocol Definitions in core protocols Package** - COMPLETE. Removed 14 dead Protocol classes and 5 wholly-dead protocol modules (-1739 lines in src/), pruned **init** re-exports to the 8 live protocols, dropped the drifted DependencyGraphProtocol.build_from_links, added an **all**/namespace agreement test, and synced docs/api and wiki source mirrors. Quality gate clean, 7579 tests pass at 91.38%.

## 2026-08-02

- **Shaping Interview Prompt (shape.md) Before Plan** - COMPLETE. Added shape.md prompt + shape-interviewer subagent for one-question-at-a-time requirements shaping; threaded shape_log_path through plan(create) to inject "## Shaping Constraints"; extended plan.md Step 4 into a four-route gate; added shared plan-log path validation guarding both shape and explore log paths. 17 new tests.
- **Shared Prompt Reference Layer for Synapse Prompts** - COMPLETE (negative result). Duplication measurement gated the plan: 0.19% extractable vs a 15% abort floor, so no _shared/ layer or include resolver was built. Delivered scripts/measure_prompt_duplication.py (standing measurement tool), tests/unit/test_measure_prompt_duplication.py (15 tests), and docs/design/synapse-prompt-duplication-report.md. Confirmed the REFACTORING_GUIDE/SUMMARY relocation to docs/guides/ was already done with no stale references.
- **Domain Glossary Consistency Gate in Plan Creation** - COMPLETE. Added canonical .cortex/wiki/glossary.md (30 curated terms) and an advisory-only terminology gate in plan creation covering exactly three detection cases; wired into both fast-forward and step-by-step planning modes, with a Terminology row in the /cortex/plan final report. 47 tests added; full suite 7464 passed.
- **Mechanically Enforce the TYPE_CHECKING Import Ban** - COMPLETE. Ruff TID251 banned-api in ruff.toml plus a complementary token-based source audit wired into the quality gate covering the bare `if TYPE_CHECKING:` block form and a justification-comment allowlist. Both layers verified to fire on a real violation. 16 tests, 100% coverage on new code, full suite green.

## 2026-07-23

- **Week containing 2026-07-23** - 9 entries summarized.

## 2026-07-22

- **Week containing 2026-07-22** - 3 entries summarized.

## 2026-07-21

- **Week containing 2026-07-21** - 4 entries summarized.

## 2026-07-20

- **Week containing 2026-07-20** - 12 entries summarized.

## 2026-07-19

- **Week containing 2026-07-19** - 1 entries summarized.

## 2026-06-30

- **Month containing 2026-06-30** - 2 entries summarized.

## 2026-06-25

- **Month containing 2026-06-25** - 10 entries summarized.

## 2026-06-24

- **Month containing 2026-06-24** - 5 entries summarized.

## 2026-06-23

- **Month containing 2026-06-23** - 5 entries summarized.

## 2026-05-08

- **Month containing 2026-05-08** - 4 entries summarized.

## 2026-05-04

- **Month containing 2026-05-04** - 2 entries summarized.

## 2026-05-03

- **Month containing 2026-05-03** - 5 entries summarized.

## 2026-04-29

- **Month containing 2026-04-29** - 1 entries summarized.

## 2026-04-27

- **Month containing 2026-04-27** - 2 entries summarized.

## 2026-04-26

- **Month containing 2026-04-26** - 2 entries summarized.

## 2026-04-25

- **Month containing 2026-04-25** - 2 entries summarized.

## 2026-04-24

- **Month containing 2026-04-24** - 2 entries summarized.

## 2026-04-23

- **Month containing 2026-04-23** - 3 entries summarized.

## 2026-04-22

- **Month containing 2026-04-22** - 2 entries summarized.

## 2026-04-20

- **Month containing 2026-04-20** - 5 entries summarized.

## 2026-04-21

- **Month containing 2026-04-21** - 6 entries summarized.

## 2026-04-19

- **Month containing 2026-04-19** - 3 entries summarized.

## 2026-04-18

- **Month containing 2026-04-18** - 4 entries summarized.

## 2026-04-17

- **Month containing 2026-04-17** - 6 entries summarized.

## 2026-04-16

- **Month containing 2026-04-16** - 14 entries summarized.

## 2026-04-15

- **Month containing 2026-04-15** - 11 entries summarized.

## 2026-04-14

- **Month containing 2026-04-14** - 18 entries summarized.

## 2026-04-13

- **Month containing 2026-04-13** - 6 entries summarized.

## 2026-04-12

- **Month containing 2026-04-12** - 21 entries summarized.

## 2026-04-11

- **Month containing 2026-04-11** - 1 entries summarized.

## 2026-04-10

- **Month containing 2026-04-10** - 1 entries summarized.

## 2026-04-09

- **Month containing 2026-04-09** - 1 entries summarized.

## 2026-04-08

- **Month containing 2026-04-08** - 1 entries summarized.

## 2026-04-07

- **Month containing 2026-04-07** - 1 entries summarized.

## 2026-04-06

- **Month containing 2026-04-06** - 1 entries summarized.

## 2026-04-04

- **Month containing 2026-04-04** - 1 entries summarized.

## 2026-04-03

- **Month containing 2026-04-03** - 1 entries summarized.

## 2026-04-02

- **Month containing 2026-04-02** - 1 entries summarized.

## 2026-04-01

- **Month containing 2026-04-01** - 1 entries summarized.

## 2026-03-31

- **Month containing 2026-03-31** - 1 entries summarized.

## 2026-03-30

- **Month containing 2026-03-30** - 1 entries summarized.

## 2026-03-29

- **Month containing 2026-03-29** - 1 entries summarized.

## 2026-03-28

- **Month containing 2026-03-28** - 1 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 6495 tests, 91.14% coverage (as of 2026-04-14); integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Plan prompt and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
