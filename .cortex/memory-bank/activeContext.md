<!-- memory_type: preference -->
# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-08-06)

- ✅ **Agentic Tool-Selection Evaluation Harness** - COMPLETE (2026-08-06) - Added an agent-in-the-loop tool-selection eval mode to run_tool_evaluation. New EvalRunMode.AGENTIC dispatches to run_agentic_suite, reusing the existing EvalSuiteResult shape, persistence, and dashboard writer. EvalTask gained a permanent id, a kind taxonomy (positive/control/near-miss) and covered_by, enforced by a Pydantic validator. Paired reporting is enforced structurally: AgenticScorecard cannot carry a selection-accuracy figure unless the run contains both a control and a near-miss task, returning a typed unpaired reason instead. Negative fixture set adds 7 control and 6 near-miss cases over real Cortex tool overlaps. The anthropic SDK is an optional agentic-evals extra, lazily imported with typed skips for a missing dependency or API key; requirements.txt is unchanged. 61 new tests, fully mocked, no network.

- ✅ **Prompt-Prefix Byte Stability Audit for Tool Schemas and Resources** - COMPLETE (2026-08-06) - Removed last_indexed from the cortex://rules byte-stable body and relocated it to an explicit rules diagnostics operation; added canonical prompt-prefix rendering, sorted tool/script name accessors, sort_keys on all agent-visible json.dumps, an AST sort_keys pre-commit audit, and two byte-stability regression suites (cross-process PYTHONHASHSEED tool schemas; every cortex:// resource read twice) with mutation guards. Added docs/guides/prompt-prefix-byte-stability.md.

- ✅ **Skill Pack Trigger Accuracy Benchmark and Description Tuning** - COMPLETE (2026-08-06) - Built a 24-fixture labeled trigger benchmark (12 positive, 5 control, 7 near-miss) for skill_pack(operation="discover") with a deterministic runner that structurally refuses to emit any accuracy figure unless both negative kinds are present. Removed the zero-signal fallback in _do_discover that returned an arbitrary pack on no match; discovery now returns an empty list with an explicit reason, and every recommendation carries its numeric score and a signal-specific reason string. Scorer extracted to scoring.py with token-level matching: name +3, description +2, keywords +1 each capped at 3 (removing verbosity wins), when_to_use contributing only on a non-stopword bigram, and a MIN_RECOMMEND_SCORE floor of 2. Tuned the refactoring manifest (which had no when_to_use or keywords) and the quality manifest. Top-1 accuracy 0.9167 to 1.0, control false-positive rate 1.0 to 0.0, near-miss false-positive rate 0.2857 to 0.1429. Added "Skill pack" to the glossary. 28 new tests.

- ✅ **Agent Skills Specification Interoperability Assessment** - COMPLETE (2026-08-06) - Assessed Cortex SkillPackManifest against the Agent Skills SKILL.md specification (agentskills.io/specification, retrieved 2026-08-06). Field-by-field mapping of all 21 manifest/workflow/phase fields in both directions; recommendation is NO-GO, recorded with revisit conditions in .cortex/wiki/decisions/agent-skills-spec-interoperability-assessment.md. Documentation only; no code or schema changes.

- ✅ **Ponytail Simplification Cuts for Agentic Eval and Skill Pack Trigger Harnesses** - COMPLETE (2026-08-06) - All 14 over-engineering findings applied, none rejected: removed five empty-list factories, collapsed three Anthropic Protocols to one with a union return from resolve_model_client, deleted RegisteredToolProtocol and single-caller wrappers (render_registered_tool_schema_payload, load_fixture_set, load_shipped_manifests alias), narrowed the agentic scorers to tuple[bool, str], deduplicated skill pack benchmark metrics, reverted quality.json/refactoring.json formatting noise while keeping the new keywords and when_to_use metadata, and removed the hand-rolled stopword/bigram phrase path from skill_pack scoring after confirming all five trigger benchmark figures are unchanged (top1 1.0, recall 1.0, precision 0.6667, control FPR 0.0, near-miss FPR 0.1429). Net -180 lines, no behavior change; when_to_use is now documentation-only metadata. 9 test files updated to the surviving symbols; touched-module coverage 96.8-100%.

- ✅ **Delete Unreferenced Protocol Definitions in core protocols Package** - COMPLETE (2026-08-06) - Deleted all 14 unreferenced Protocol classes from src/cortex/core/protocols/, removing linking.py, loading.py, refactoring_execution.py, rules.py, and versioning.py in full and pruning RefactoringEngine/ConsolidationDetector/ReorganizationPlanner from refactoring.py and RelevanceScorer from optimization.py. Net -1739 lines in src/ with no behavior change. Also removed the drifted DependencyGraphProtocol.build_from_links method, whose LinkParserProtocol annotation no longer resolved and whose signature never matched the concrete DependencyGraph; its only consumer uses to_dict(). Added a namespace-agreement test guarding **init** **all**, and updated docs/api/protocols.md, docs/api/managers.md, and the two wiki source mirrors. Quality gate clean (zero lint/type/format/markdown, no new suppressions); 7579 tests pass at 91.38% coverage.

## Completed Work (2026-08-02)

- ✅ **Shaping Interview Prompt (shape.md) Before Plan** - COMPLETE (2026-08-02) - Added a shape.md Synapse prompt and shape-interviewer subagent that resolve unknown requirements by interviewing the user one question at a time (codebase-first, with recommended answers) until the decision tree is settled. The shaping record feeds plan(operation="create") via a new shape_log_path parameter, injecting resolved decisions, assumptions, and out-of-scope declarations as a "## Shaping Constraints" section. plan.md Step 4 became a four-route gate (shape / explore / both / neither). A shared resolve_plan_log_path validator now guards both shape_log_path and explore_log_path against absolute paths and project-root escapes, closing a pre-existing unvalidated-path hole. 17 new tests.

- ✅ **Shared Prompt Reference Layer for Synapse Prompts** - COMPLETE (2026-08-02) - Closed as a recorded negative result per the plan's own abort condition. Measurement (scripts/measure_prompt_duplication.py) shows only 76 of 39,894 prompt tokens (0.19%) are extractable at the plan's >=3-lines/>=3-files threshold, far below the 15% floor; even the threshold-violating >=2-files variant caps at 5.96%. Extraction steps 4-9 were not executed. Evidence: docs/design/synapse-prompt-duplication-report.md.

- ✅ **Domain Glossary Consistency Gate in Plan Creation** - COMPLETE (2026-08-02) - Added canonical .cortex/wiki/glossary.md (30 curated project-specific terms with definition, aliases, and not-to-be-confused-with) plus an advisory terminology gate wired into plan(create) and finalize_step. Detection is restricted to exactly three conservative cases (declared alias, near-match undeclared synonym at a pinned 0.86 threshold, and confusable pair sharing one sentence). The gate never blocks: plans are written before the check runs and status stays success regardless of findings. 47 tests added.

- ✅ **Mechanically Enforce the TYPE_CHECKING Import Ban** - COMPLETE (2026-08-02) - Two-layer mechanical enforcement of the TYPE_CHECKING ban. Ruff TID251 banned-api (configured in ruff.toml, which takes full precedence over pyproject.toml) rejects the `from typing import TYPE_CHECKING` and `typing.TYPE_CHECKING` forms with an editor-visible message citing python-coding-standards.mdc. A new token-based audit (pre_commit_type_checking_audit.py) wired into execute_quality covers what ruff cannot: bare `if TYPE_CHECKING:` blocks with no import, and an allowlist requiring an inline `# type-checking-allowed: <reason>` justification so a bare noqa cannot bypass. Both mechanisms demonstrated firing on a real scratch violation and passing after removal. 16 tests, 100% coverage on new code; full suite 7478 passed.

## Completed Work (2026-07-23)

- **Summary (2026-07-23)** - 9 entries archived.

## Completed Work (2026-07-22)

- **Summary (2026-07-22)** - 3 entries archived.

## Completed Work (2026-07-21)

- **Summary (2026-07-21)** - 1 entries archived.

## Completed Work (2026-07-20)

- **Summary (2026-07-20)** - 1 entries archived.

## Completed Work (2026-07-19)

- **Summary (2026-07-19)** - 1 entries archived.

## Completed Work (2026-06-30)

- **Summary (2026-06-30)** - 1 entries archived.

## Completed Work (2026-06-25)

- **Summary (2026-06-25)** - 1 entries archived.

## Completed Work (2026-06-24)

- **Summary (2026-06-24)** - 1 entries archived.

## Completed Work (2026-06-23)

- **Summary (2026-06-23)** - 1 entries archived.

## Completed Work (2026-05-08)

- **Summary (2026-05-08)** - 1 entries archived.

## Completed Work (2026-05-04)

- **Summary (2026-05-04)** - 1 entries archived.

## Completed Work (2026-05-03)

- **Summary (2026-05-03)** - 1 entries archived.

## Completed Work (2026-04-29)

- **Summary (2026-04-29)** - 1 entries archived.

## Completed Work (2026-04-27)

- **Summary (2026-04-27)** - 1 entries archived.

## Completed Work (2026-04-26)

- **Summary (2026-04-26)** - 1 entries archived.

## Completed Work (2026-04-25)

- **Summary (2026-04-25)** - 1 entries archived.

## Completed Work (2026-04-24)

- **Summary (2026-04-24)** - 1 entries archived.

## Completed Work (2026-04-23)

- **Summary (2026-04-23)** - 1 entries archived.

## Completed Work (2026-04-22)

- **Summary (2026-04-22)** - 1 entries archived.

## Completed Work (2026-04-20)

- **Summary (2026-04-20)** - 1 entries archived.

## Completed Work (2026-04-21)

- **Summary (2026-04-21)** - 1 entries archived.

## Completed Work (2026-04-19)

- **Summary (2026-04-19)** - 1 entries archived.

## Completed Work (2026-04-18)

- **Summary (2026-04-18)** - 1 entries archived.

## Completed Work (2026-04-17)

- **Summary (2026-04-17)** - 1 entries archived.

## Completed Work (2026-04-16)

- **Summary (2026-04-16)** - 1 entries archived.

## Completed Work (2026-04-15)

- **Summary (2026-04-15)** - 1 entries archived.

## Completed Work (2026-04-14)

- **Summary (2026-04-14)** - 1 entries archived.

## Completed Work (2026-04-12)

- **Summary (2026-04-12)** - 1 entries archived.

## Completed Work (2026-04-13)

- **Summary (2026-04-13)** - 1 entries archived.

## Completed Work (2026-04-11)

- **Summary (2026-04-11)** - 1 entries archived.

## Completed Work (2026-04-10)

- **Summary (2026-04-10)** - 1 entries archived.

## Completed Work (2026-04-09)

- **Summary (2026-04-09)** - 1 entries archived.

## Completed Work (2026-04-08)

- **Summary (2026-04-08)** - 1 entries archived.

## Completed Work (2026-04-07)

- **Summary (2026-04-07)** - 1 entries archived.

## Completed Work (2026-04-06)

- **Summary (2026-04-06)** - 1 entries archived.

## Completed Work (2026-04-04)

- **Summary (2026-04-04)** - 1 entries archived.

## Completed Work (2026-04-03)

- **Summary (2026-04-03)** - 1 entries archived.

## Completed Work (2026-04-02)

- **Summary (2026-04-02)** - 1 entries archived.

## Completed Work (2026-04-01)

- **Summary (2026-04-01)** - 1 entries archived.

## Completed Work (2026-03-31)

- **Summary (2026-03-31)** - 1 entries archived.

## Completed Work (2026-03-30)

- **Summary (2026-03-30)** - 1 entries archived.

## Completed Work (2026-03-29)

- **Summary (2026-03-29)** - 1 entries archived.

## Completed Work (2026-03-28)

- **Summary (2026-03-28)** - 1 entries archived.

## Completed Work (2026-03-27)

- **Summary (2026-03-27)** - 1 entries archived.

## Completed Work (2026-03-26)

- **Summary (2026-03-26)** - 1 entries archived.

## Completed Work (2026-03-25)

- **Summary (2026-03-25)** - 1 entries archived.

## Completed Work (2026-03-24)

- **Summary (2026-03-24)** - 1 entries archived.

## Completed Work (2026-03-23)

- **Summary (2026-03-23)** - 1 entries archived.

## Completed Work (2026-03-22)

- **Summary (2026-03-22)** - 1 entries archived.

## Completed Work (2026-03-21)

- **Summary (2026-03-21)** - 1 entries archived.

## Completed Work (2026-03-20)

- **Summary (2026-03-20)** - 1 entries archived.

## Completed Work (2026-03-16)

- **Summary (2026-03-16)** - 1 entries archived.

## Completed Work (2026-03-14)

- **Summary (2026-03-14)** - 1 entries archived.

## Completed Work (2026-03-13)

- **Summary (2026-03-13)** - 1 entries archived.

## Completed Work (2026-03-12)

- **Summary (2026-03-12)** - 1 entries archived.

## Completed Work (2026-03-11)

- **Summary (2026-03-11)** - 1 entries archived.

## Completed Work (2026-03-10)

- **Summary (2026-03-10)** - 1 entries archived.

## Completed Work (2026-03-09)

- **Summary (2026-03-09)** - 1 entries archived.

## Completed Work (2026-03-08)

- **Summary (2026-03-08)** - 1 entries archived.

## Completed Work (2026-03-07)

- **Summary (2026-03-07)** - 1 entries archived.

## Completed Work (2026-03-06)

- **Summary (2026-03-06)** - 1 entries archived.

## Completed Work (2026-03-05)

- **Summary (2026-03-05)** - 1 entries archived.

## Completed Work (2026-03-04)

- **Summary (2026-03-04)** - 1 entries archived.

## Completed Work (2026-03-03)

- **Summary (2026-03-03)** - 1 entries archived.

## Completed Work (2026-03-02)

- **Summary (2026-03-02)** - 1 entries archived.

## Completed Work (2026-03-01)

- **Summary (2026-03-01)** - 1 entries archived.

## Completed Work (2026-02-28)

- **Summary (2026-02-28)** - 1 entries archived.

## Completed Work (2026-02-27)

- **Summary (2026-02-27)** - 1 entries archived.

## Completed Work (2026-02-26)

- **Summary (2026-02-26)** - 1 entries archived.

## Completed Work (2026-02-25)

- **Summary (2026-02-25)** - 1 entries archived.

## Completed Work (2026-02-24)

- **Summary (2026-02-24)** - 1 entries archived.

## Completed Work (2026-02-23)

- **Summary (2026-02-23)** - 1 entries archived.

## Completed Work (2026-02-22)

- **Summary (2026-02-22)** - 1 entries archived.

## Completed Work (2026-02-21)

- **Summary (2026-02-21)** - 1 entries archived.

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

Next roadmap item: **[Fast-Forward vs. Step-by-Step Planning Modes](../plans/archive/Other/fast-forward-vs-step-by-step-modes.md)** (see [roadmap.md](roadmap.md) pending plans).

## Recent Changes

CodeGraph integration (2026-06-30): added `setup_codegraph` setup prompt with visibility gated on `memory_bank_initialized and not codegraph_configured`; `ProjectConfigStatus.codegraph_configured` checks `.cursor/mcp.json` and `.mcp.json`; `.codegraph/` added to `.gitignore`.

CI quality gate green (2026-06-23): synapse scripts fully typed (99 pyright errors resolved across 8 files); docs gate test uses concrete types instead of Any; test_phase3 and test_phase4 stale dates fixed.

Refactor in progress (2026-04-14): split `session/brief.py` and `optimization/handlers.py` into `brief_cap.py`, `brief_loaders.py`, `context_appenders.py`, and `context_loaders.py`; compatibility symbols in `handlers.py` were retained for existing tests while finishing structural debt cleanup.

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
