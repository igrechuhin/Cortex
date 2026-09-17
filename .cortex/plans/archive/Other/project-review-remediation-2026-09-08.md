---
title: "Remediate Project Review Findings: Safety, Rules, Planning, Context, and Verification"
component: "cross-cutting"
work_type: fix
status: DONE
priority: Critical
created: 2026-09-08
depends_on: []
execution: agent
---

## Remediate Project Review Findings: Safety, Rules, Planning, Context, and Verification

## Goal

Resolve all seven findings from the September 8 project review and the existing quality-gate failures, using the existing Cortex entrypoints. Make filesystem boundaries enforceable, rule delivery complete, plan completion recoverable, context output bounded, and public workflow outcomes verifiable.

This is an implementation plan. Creating and registering it does not implement the fixes or authorize a commit or push.

## Context and Evidence

Source: [Cortex Project Review and Improvement Recommendations](../../../memory-bank/reviews/review-cortex-project-review-and-improvement-recommendations-2026-09-08-2026-09-08.md). The report contains precise source references and confidence limits.

- F1, P1: Snapshot labels reach path joining and recursive deletion without containment validation.
- F2, P1: Historical reads accept paths outside the documented memory-bank scope. A safe live probe returned the project manifest; no private external file was read.
- F3, P1: Selected shared GENERIC and GENERAL rules are lost during categorization. The live response contained zero rules despite 702 selected tokens and 56 indexed files.
- F4, P1: Completion does not persist DONE. A completed analytics plan remains PENDING; the context resource reports 551 READY plans, including historical and scaffolding artifacts.
- F5, P2: Completion writes multiple files before later validation or I/O can fail, and retries can encounter a missing roadmap entry.
- F6, P2: Appended graph and layered context bypass the base token budget. The observed payload contained 35,347 characters while reporting 1,522 base tokens; its compact READY list occupied 24,229 characters. Character measurements are not token estimates.
- F7, P2: Commit-workflow E2E tests are excluded by the only checked-in CI workflow, and a key test accepts the existence of a status field instead of a successful outcome.
- Quality baseline: 7,737 tests passed, four skipped, and coverage was 91.42%; types, formatting, lint, and spelling passed. The overall gate failed on seven function-length violations and Markdown diagnostics in pre-existing, untracked installed skill packages. The docs gate passed.

Planning inspection also found a related F4 defect: setting an already-equal frontmatter status can insert a duplicate status key in the registration helper. Include idempotent metadata updates in the lifecycle fix.

The skill lock manifest identifies the failing Caveman packages as externally installed. Treat their upstream payload as vendor content rather than refactoring it merely to satisfy Cortex's project-owned function limits.

## Scope

In scope:

- Every review finding F1–F7, including regression coverage and documented behavior changes.
- Explicit, consistent quality-check scope for externally installed skills and project-owned files.
- Idempotent plan metadata updates and evidence-based repair of historical completion records.
- Recovery from partial completion, including failures and interruption between writes.
- CI execution and meaningful assertions for public workflow smoke tests and the remaining slow suite.
- Updated memory-bank status, documentation, and relevant existing Synapse policy where behavior or check ownership changes.

Out of scope:

- Additional MCP tools, new top-level directories, broad unrelated refactors, dependency upgrades, and offline bootstrap support.
- Running destructive probes against the real checkout or reading private files to demonstrate path escapes.
- Reclassifying every archived plan as completed, deleting historical plans, or overwriting unrelated user changes.
- Committing, pushing, deploying, or creating unrelated feature work.

## Approach and Decisions

Use one sequential plan because completion, graph reporting, and context serialization share state and verification. Each step includes a small, independently reviewable implementation step; keep incomplete steps PENDING or IN_PROGRESS and record partial progress accurately.

Restore the quality gate before starting further product work. Retain strict checks for project-owned code and local skills; introduce only a narrow, documented vendor-scope policy for installed packages. Do not globally ignore the agent configuration tree or trust an unvalidated lock entry to exempt arbitrary source paths.

Reuse the shared path resolver, existing memory-file validators, lock/conflict helpers, atomic-file facilities, and snapshot models. Validate containment at filesystem use, not only at the MCP boundary. Use Pydantic models and internal enums, and keep policy prompts language agnostic.

For multi-file completion, use a bounded persisted operation record and rollback snapshots within the canonical session area. Per-file atomic replacement alone cannot guarantee a multi-file transaction; recovery must restore or finish an interrupted operation without losing concurrent edits. Reuse existing recovery primitives after checking their suitability rather than building a general transaction framework.

For context, reserve space for mandatory governance and essential context before optional graph/history sections. If required content itself exceeds the requested budget, return an explicit insufficient-budget result rather than silently dropping mandatory instructions.

## Implementation Steps

### Step 1: Restore the quality gate and define owned-file scope

Status: COMPLETE (2026-09-08). Dependency: none. Covers the existing gate failures.

Targets: quality candidate collection and filtering in `src/cortex/tools/execution/pre_commit_pipeline_quality.py`, Markdown collection in `pre_commit_worker.py`, existing check configuration, the CI workflow, and the corresponding governance tests and Synapse check entrypoints where necessary.

- Preserve the initial working-tree inventory and distinguish tracked project code, local authored skills, and externally installed skill payloads using the existing lock manifest and installation layout.
- Apply one narrow ownership policy to changed-file checks, full checks, Markdown checks, and CI. Validate any manifest-derived paths against the exact installation roots; a forged or malformed entry must not hide project code.
- Keep project-owned local skills checked. Fix actual owned-code or owned-document violations normally. Preserve external package contents and their install metadata; do not rewrite vendor files to satisfy Cortex-specific style limits.
- Handle externally distributed documentation links consistently with that scope, retaining validation of Cortex's own links and integration references.
- Add fixtures proving vendor payload is excluded only from owned-code style gates, while local authored skills and a deliberately invalid source file are still rejected.
- Restart the server if its loaded check implementation changes, run a fresh Cortex quality gate, and resolve all remaining failures before Step 2.

Acceptance: the same checkout passes the full quality gate without reducing source/test coverage thresholds, broad directory exemptions, silently skipped checks, or vendor edits.

### [P:after=1] Step 2: Constrain WAL snapshot and restore destinations

Status: COMPLETE (2026-09-08). Dependency: Step 1. Covers F1.

Targets: `src/cortex/tools/memory/wal_tool.py`, `src/cortex/memory/wal.py`, shared path/input-validation helpers, `tests/tools/memory/test_wal_tool.py`, and `tests/memory/test_wal.py`.

- Add a shared validator for snapshot labels: reject empty or whitespace-only labels, absolute paths, parent/dot segments, both separator styles, and invalid labels before any filesystem mutation.
- Resolve snapshot and restore destinations beneath the canonical snapshot root. Reject escaping symlinks, symlink destinations, and unsafe ancestor resolution; recheck before deletion/copy operations.
- Preserve valid label behavior and make replacement of an existing valid snapshot bounded and recoverable. Reject unsupported inputs with a structured error rather than invoking recursive deletion first.
- Cover valid round trips, replacing an existing valid snapshot, invalid labels, synthetic external sentinel directories, symlink escapes, and missing snapshots.

Acceptance: malicious labels cannot delete, replace, or copy outside the allowed snapshot store; every invalid-input test leaves unrelated sentinels unchanged.

### [P:after=2] Step 3: Enforce historical-read file scope

Status: COMPLETE (2026-09-08). Dependency: Step 2. Covers F2.

Targets: `src/cortex/memory/wal_content.py`, `src/cortex/tools/memory/wal_tool.py`, `tests/memory/test_wal_content.py`, and the WAL tool tests.

- Resolve the requested file through the shared path resolver and require it to remain within the canonical memory-bank root.
- Reuse memory-bank filename/extension rules and apply symlink containment before reading current content or querying historical state.
- Retain valid historical reconstruction and its verification/provenance fields; document that arbitrary project files were never the intended contract.
- Use synthetic fixtures to reject project source files, absolute external paths, parent traversal, directory targets, and escaping symlinks. Cover missing allowed files and corrupted/pruned history.

Acceptance: the former manifest probe is rejected; valid memory history remains reconstructable without external-file disclosure.

### [P:after=3] Step 4: Preserve all selected shared rules

Status: COMPLETE (2026-09-08). Dependency: Step 3. Covers F3.

Targets: `src/cortex/optimization/rules_hybrid.py`, its existing category/result models, the rules response helpers, and rules-manager/resource integration tests.

- Route GENERIC and GENERAL shared rules into the generic bucket explicitly.
- Ensure each selected rule is delivered exactly once across generic, language, and local categories. Preserve local override precedence and the intended handling of unknown categories.
- Compute rule counts and token totals from the delivered selection; retain separately injected governance text with clearly defined accounting.
- Add a real Synapse-backed fixture with shared generic/general rules, a detected language rule, local overrides, and a constrained selection budget.
- Verify both the manager result and the public zero-argument rules resource; assert actual returned rule identities/content, not only key presence.

Acceptance: selected generic/general rules survive serialization, category totals agree with delivered content, and unchanged state remains byte-stable.

### [P:after=4] Step 5: Make completion consistent, idempotent, and recoverable

Status: COMPLETE (2026-09-08). Dependency: Step 4. Covers F5 and the completion transition in F4.

Targets: `src/cortex/tools/plans/completion.py`, completion operations/I/O/archive modules, `register_artifact_graph.py`, the existing file snapshot/lock helpers, and completion tests.

- Prevalidate date, progress text, plan filename, matching plan/roadmap identity, archive destination, and all required reads before writing.
- Fix frontmatter status replacement so setting an existing value is idempotent and produces exactly one canonical status key.
- Within a consistent lock boundary, prepare snapshots and a persisted completion record, then update plan metadata to DONE, roadmap, active context, optional progress, and archive state.
- Use atomic per-file writes with conflict detection. On failure restore earlier content and file locations, or leave a precise recoverable operation record if rollback cannot finish; never report success with unapplied work.
- Make identical retries succeed without duplicate completion/progress entries. Reject conflicting retries and archive collisions without overwriting unrelated data.
- Recover interrupted operations before treating the plan as completed or resynchronizing dependents. Bound and clean completed recovery records through the existing session lifecycle.
- Add fault injection at every write/archive boundary, lock denial, missing prerequisites, malformed filename, retry after success/failure, interruption/restart recovery, and concurrent-update cases.

Acceptance: each operation ends with all records consistent or explicit recoverable failure; a successful retry completes exactly once, and unrelated edits remain intact.

### [P:after=5] Step 6: Correct actionable plan graphs and repair historical metadata

Status: COMPLETE (2026-09-08). Dependency: Step 5. Covers the graph/history portion of F4.

Targets: `src/cortex/core/artifact_graph.py`, frontmatter normalization, plan graph surfaces, registration/resync helpers, session/context consumers, and their existing tests.

- Keep archived plans available for dependency resolution while limiting the actionable queue to real active plans with eligible statuses.
- Exclude scaffolding such as README, templates, indexes, and dependency-graph documents from plan vertices. Resolve identity consistently and detect ambiguous duplicate slugs rather than silently choosing one.
- Preserve blocked, in-progress, declined, and custom legacy intent. Canonicalize metadata using the existing normalizer without treating absent metadata as proof of completion.
- Produce a reviewable repair inventory by matching archived plans to recorded completion evidence. Back up affected files and apply only unambiguous status repairs through existing MCP plan operations; leave ambiguous items explicitly reported.
- Verify the completed analytics plan no longer appears READY and genuine dependents unblock. Correct stale next-work references when their underlying plan is already completed.
- Cover PENDING → completion → DONE/archive → dependency-unblock end to end, plus legacy headings, duplicate status keys, repeated registration, scaffold files, archived declined work, and ambiguous identities.

Acceptance: session/context/plan graph agree on actionable work; completed plans are excluded from READY while their dependencies are satisfied, and historical repair is reversible and idempotent.

### [P:after=6] Step 7: Enforce a budget for the complete context resource

Status: COMPLETE (2026-09-16). Dependency: Step 6. Covers F6.

Targets: `src/cortex/tools/optimization/handlers.py`, formatting/append helpers, the plan graph surface bundle, existing context layer builders, and context resource/performance tests.

- Allocate the configured budget across required governance, essential context, optional layers, graph summaries, recent artifacts, and other appended content.
- Count the final serialized response with the existing tokenizer, including its metadata, and expose component accounting that sums consistently.
- Bound READY/BLOCKED details in the concise resource and direct callers to existing detailed graph operations for additional information; do not add a tool.
- Preserve cache scoping, invalidation, deterministic ordering, and byte stability for unchanged relevant state.
- Cover hundreds of plans, long history/governance, small and invalid budgets, empty optional sections, cached reads, and insufficient budget for mandatory content.
- Keep existing latency expectations and add a bounded regression case for graph-heavy context assembly.

Acceptance: successful context responses remain within the configured token budget, report truthful accounting, and retain mandatory governance; insufficient-budget responses explain the unmet requirement.

### [P:after=7] Step 8: Verify public workflow outcomes in CI

Status: COMPLETE (2026-09-16). Dependency: Step 7. Covers F7.

Targets: `tests/e2e/test_commit_pipeline.py`, session lifecycle tests, shared-rules integration fixtures, plan completion fixtures, and `.github/workflows/quality.yml`.

- Add a bounded smoke suite through the supported public MCP surface using an isolated temporary project and real shared rules. Keep setup independent of live workspace state.
- Assert nonempty expected rules, PENDING → DONE/archive, correct dependency unblocking, bounded context output, and successful quality results.
- Include a deliberate failed-quality case and verify failure semantics; a response containing status keys must not satisfy a success assertion.
- Ensure critical smoke tests run on every pull request. Add a scheduled/manual job for the remaining slow suite with explicit selection, bounded timeouts, and published results.
- Strengthen CI outcome handling so missing, skipped, or infrastructure-error results cannot be reported as a successful required smoke check.
- Confirm fixture-created plans and logs remain in temporary roots and do not pollute the real roadmap or session telemetry.

Acceptance: CI records executed semantic smoke tests, catches deliberately broken workflow outcomes, and provides an actual execution path for the slow suite.

### [P:after=8] Step 9: Verify all findings, document contracts, and compound results

Status: COMPLETE (2026-09-16). Dependency: Step 8. Covers final proof for F1–F7 and quality scope.

- Re-read context and rules on every fix path. After changing server-loaded Python modules, restart Cortex before trusting in-process checks.
- Run the public lifecycle scenario and the focused negative cases from Steps 2–8; capture one concise evidence record per finding.
- Run a fresh zero-argument quality gate after configuring force_fresh and an adequate timeout through pipeline handoff, then run the docs gate.
- Review the complete diff for unintended scope changes, missing tests, path handling gaps, privacy-sensitive logs, and changes to user-authored work.
- Update API/configuration docs, quality-scope guidance, relevant existing Synapse rules, and the review's resolution notes. Keep terminology and policy consistent across local and CI paths.
- Update active context and progress through MCP after each completed slice, keeping a real PENDING roadmap entry while work remains. Complete/archive this plan only when all acceptance criteria pass.
- Run session analysis and record actionable lessons without claiming completion from token coverage or unit-test count alone.

Acceptance: all findings have passing regression evidence, quality and docs gates pass, review records show the final behavior, and no unimplemented step is marked complete.

## Testing Strategy

- Reproduce each defect with a narrow behavior-level regression before fixing it. All filesystem attack and recovery tests use temporary projects and synthetic data.
- Keep public-resource assertions in addition to internal unit tests; selected rule content, plan transitions, recovery outcomes, and final token budgets are the contracts.
- Check execution-frontier behavior for this plan's explicit predecessor chain. Automatic file-disjointness hints must not let a step bypass a declared predecessor.
- Use fresh Cortex quality gates after meaningful implementation steps and after server restarts; do not run standalone language checks in place of the MCP gate.
- Run the docs gate after plan/history changes and capture separate evidence for CI smoke tests and the remaining slow suite.

## Verification Checklist

- [x] Baseline: owned-file quality policy is narrow, tested, and green.
- [x] F1: snapshot/restore path escape cases are rejected before mutation.
- [x] F2: historical reads enforce the memory-bank boundary.
- [x] F3: all selected shared rules survive public serialization.
- [x] F4: DONE is persisted; graph readiness and history repair are correct.
- [x] F5: completion handles failure, retries, interruption, and conflicts safely.
- [x] F6: final context tokens obey the configured budget.
- [x] F7: CI selects semantic lifecycle smoke tests and the scheduled/manual slow suite; both selections pass locally with JUnit proof.
- [x] Final: fresh quality gate and docs gate pass after restarting changed server code.
- [x] Compound: report, plan status, roadmap, and progress agree.

## Dependencies and Related Work

There are no unresolved external plan dependencies. Active-plan discovery returned no existing pending remediation plan; archived work is context and implementation to reuse, not a reason to mark this work already completed.

Related archived slugs: `content-preserving-wal-as-of`, `fix-archive-blind-plan-graph-summaries-session-brief`, and `improve-layered-context-budget`. Preserve their valid behavior while closing the gaps demonstrated in the review.

Execution order is Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8 → Step 9. Explicit predecessor dependencies enforce a single execution frontier. Dependency markers permit only the next step after its predecessor finishes; they do not authorize overlapping work.

## Risks and Rollback

- Path restrictions intentionally reject formerly accepted out-of-scope requests. Preserve documented valid calls and explain the tightened contract.
- A vendor exclusion can hide owned defects if too broad. Validate scope and keep negative fixtures for source files, local skills, and forged manifest paths.
- Recovery can overwrite concurrent edits if locks or fingerprints are wrong. Test conflicts and restore only state owned by the operation.
- Historical metadata is inconsistent. Apply only evidence-backed repairs with recorded original content, and report unresolved ambiguity.
- A hard response budget can collide with large required governance. Return an explicit budget error; do not quietly omit policy.
- Slow CI can delay feedback. Keep pull-request smoke checks bounded and separate full slow-suite execution from the fast gate.
- Restore code by a scoped revert of the relevant implementation step; restore data from verified snapshots under the correct lock boundary. Do not use destructive git operations.

## Success Criteria

All seven findings are closed by behavior-level regression evidence. Valid existing MCP workflows continue to work, the actionable queue excludes completed/scaffolding artifacts, completion is recoverable, delivered rules and token accounting are truthful, and quality/docs gates are green. Tool count does not increase, vendor payloads remain intact, and no commit or push occurs without a separate explicit request.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._

## Partial Progress Log

- 2026-09-08: Step 1 complete. Added validated installed-skill ownership shared by structural checks, Markdown lint/autofix, link validation, CI, and local parity checks; preserved lexical ownership through symlinks and removed the full-gate Markdown cap. Added 34 regression cases. A newly initialized Cortex MCP server passed the forced-fresh full quality gate with zero errors and warnings; all 49 fingerprinted installed-package/lock files remained unchanged. Steps 2–9 remain PENDING. Files: `.github/workflows/quality.yml`, `Makefile`, `docs/api/tools.md`, `docs/guides/markdown-formatting.md`, `src/cortex/core/quality_scope.py`, `src/cortex/tools/execution/file_language_router.py`, `src/cortex/tools/execution/pre_commit_pipeline_quality.py`, `src/cortex/tools/execution/pre_commit_worker.py`, `src/cortex/tools/files/markdown_link_validation.py`, `src/cortex/tools/files/markdown_lint.py`, `src/cortex/tools/files/markdown_lint_core.py`, `tests/unit/test_quality_scope.py`.

- 2026-09-08: Step 2 complete. Added shared snapshot label and containment validation, staged bounded replacement with retained recovery data on rollback failure, per-file atomic restore, structured public errors, and 84 synthetic regression cases. Added 8 reflection regressions while correcting the indented-handler false positive that blocked the quality gate. Fresh Cortex quality and reflection gates passed: 7,863 tests passed, four skipped, 91.48% overall coverage; snapshot helper line coverage 97.08%. Reflection's 11 advisory findings were reviewed: typed path/model access, documented heuristic marker text, and already annotated JSON assertions; no error-level findings remain. Steps 3–9 remain PENDING. Files: `src/cortex/memory/wal.py`, `src/cortex/memory/wal_snapshots.py`, `src/cortex/tools/memory/wal_tool.py`, `tests/memory/test_wal_snapshots.py`, `tests/tools/memory/test_wal_tool.py`, `src/cortex/tools/evaluation/reflection.py`, `src/cortex/tools/reflection_constants.py`, `tests/unit/tools/evaluation/test_reflection.py`, `docs/api/tools.md`, `docs/guides/reflection-pass.md`.

- 2026-09-08: Step 3 complete. Historical reads now require canonical project-relative memory-bank Markdown paths, including nested artifacts. Shared filename/path validators reject out-of-scope requests before content or WAL access; content and fixed log paths reject symlinks and unsupported file types, with a second content-path check after the WAL read. Preserved missing-file semantics, canonical identity, reverse-delta provenance, hash verification, and corrupted/pruned-history errors. Added 46 regression cases. Fresh Cortex quality/reflection gates passed: 7,909 tests passed, four skipped, 91.49% overall coverage. Steps 4–9 remain PENDING. Files: `src/cortex/memory/wal.py`, `src/cortex/memory/wal_content.py`, `src/cortex/tools/memory/wal_tool.py`, `tests/memory/test_wal_history_scope.py`, `tests/tools/memory/test_wal_tool.py`, `docs/api/tools.md`.

- 2026-09-08: Step 4 complete. Shared generic/general aliases load together; exclusive categorization preserves every selected rule, relative-path merge keys preserve local overrides and distinct nested identities, and delivered-rule counts/token totals are recomputed from serialized selections. Governance accounting is documented separately. Added 21 integration cases using real shared-rule loading and decoded public resource content; corrected the existing resource byte-stability helper to assert actual text. Two consecutive fresh public reads returned the same shared general coding-standard rule, with rules_count 1 and total_tokens 702 matching delivered rule tokens. Fresh Cortex quality/reflection gates passed: 7,930 tests passed, four skipped, 91.49% overall coverage, zero quality errors or warnings. Reflection approved with 14 reviewed advisory findings and no error findings. All 49 fingerprinted installed-package/lock files remain unchanged. Steps 5–9 remain PENDING. Files: `src/cortex/optimization/rules_hybrid.py`, `src/cortex/tools/synapse/rules_operation_helpers.py`, `src/cortex/tools/synapse/rules_operations_handlers.py`, `tests/tools/test_rules_operations.py`, `tests/integration/test_hybrid_rules_delivery.py`, `tests/integration/test_resource_byte_stability.py`, `tests/integration/resource_test_helpers.py`, `docs/api/tools.md`.

- 2026-09-08: Step 5 complete. Plan completion now prevalidates all inputs and reads, persists a typed bounded recovery record, serializes the operation under one cross-process lock, uses expected-hash atomic writes with WAL preservation, and validates project-relative archive and payload metadata before recovery. DONE frontmatter is canonical and idempotent; identical retries complete once, while conflicting retries, collisions, interruptions, rollback conflicts, malformed records, and tampered or symlinked payloads fail without overwriting unrelated data. Added 38 focused cases. The fresh Cortex gate passed all quality, formatting, lint, type, test, and reflection checks; the final integrity batch brings the suite to 7,967 passing cases with four skipped, and last explicit coverage was 91.39%. Reflection approved with 17 advisory findings and no errors. Steps 6–9 remain PENDING. Files: `src/cortex/tools/plans/completion.py`, `src/cortex/tools/plans/completion_models.py`, `src/cortex/tools/plans/register_artifact_graph.py`, `src/cortex/tools/plans/completion_transaction.py`, `src/cortex/tools/plans/completion_transaction_io.py`, `src/cortex/tools/plans/completion_transaction_models.py`, `src/cortex/tools/plans/completion_transaction_prepare.py`, `src/cortex/tools/plans/completion_transaction_recovery.py`, `tests/tools/test_plan_completion.py`, `tests/tools/test_plan_completion_archive.py`, `tests/tools/test_plan_completion_transaction.py`, `tests/tools/test_plan_completion_recovery.py`, `docs/api/tools.md`.

- 2026-09-08: Step 6 complete. Shared archive-aware plan identity now excludes scaffolding, drafts, and symlinks; duplicate slugs are explicit diagnostics. Only active recognized plans are actionable; archived dependencies remain resolvable, manual BLOCKED and IN_PROGRESS intent is preserved, and unknown/conflicting metadata is not silently promoted. Scoped scalar and legacy metadata parsing preserves body examples and custom states. CRUD title/path metadata and scoped context share discovery. The existing plan tool gained guarded, locked, expected-hash status repair without adding a tool; missing expected-hash targets now conflict instead of being recreated. Fresh final quality gate passed with zero errors and warnings; last detailed suite result was 8,020 passing tests, four skipped, 91.41% coverage, followed by one test split and another green full gate. Root's 21 discovery boundary cases passed. Live graph, context, and session agree on one READY plan (previously 552), zero BLOCKED, and no archived IN_PROGRESS leakage. Thirteen evidence-backed historical repairs succeeded; all thirteen repeated calls were no-ops, and exact comparison confirmed only status metadata changed. Steps 7–9 remain PENDING.

### Step 6 Historical Repair Evidence

Completion evidence came from exact-title COMPLETE entries in progress.md, independently of archive placement. Of 615 real documents, 14 matched this conservative evidence rule: 13 required repair and the prompt-prefix byte-stability audit was already DONE. The other 601 documents were left unchanged by this repair batch; the archived fast-forward planning plan retains its PARTIAL notes and status. The shared prompt-reference investigation is complete with a negative result; its explanation remains intact.

Rollback snapshot: `20260908T161953361545`, session `08267f8ad3c6`, created through the implement pipeline snapshot operation before mutation. All targets are under the canonical archive/Other directory. Each target now has one DONE status field; duplicate equivalent PENDING fields were consolidated where present. Plan bodies and other metadata are byte-preserved.

- [Agent Skills Specification Interoperability Assessment](agent-skills-specification-interoperability-assessment.md). Evidence in progress.md: **Agent Skills Specification Interoperability Assessment** - COMPLETE. Field-by-field comparison of SkillPackManifest against the Agent Skills SKILL.md spec in both export and import directions; explicit NO-GO recorded with revisit conditions in the wiki. Documentation only, no code or schema changes.
- [Agentic Tool-Selection Evaluation Harness](agentic-tool-selection-evaluation-harness.md). Evidence in progress.md: **Agentic Tool-Selection Evaluation Harness** - COMPLETE. Agent-in-the-loop tool-selection eval mode with structurally enforced paired reporting (no accuracy figure without both negative kinds), kind/covered_by fixture taxonomy, 13 negative fixtures, optional lazily-imported anthropic extra, and live FastMCP schema exposure with explicit visibility gating. 61 new tests; quality gate clean, coverage 91.34%.
- [Content-Preserving WAL for AS-OF Reconstruction](content-preserving-wal-as-of.md). Evidence in progress.md: **Content-Preserving WAL for AS-OF Reconstruction** - COMPLETE. WAL entries now store zlib+base64 reverse deltas, delta_codec, and experience-store step numbers; new wal_content.py provides hash-verified as_of reconstruction plus size-bounded compaction; memory_wal gained an as_of operation for analyze-pipeline evidence. 20 new tests, quality gate green.
- [Delete Unreferenced Protocol Definitions in core protocols Package](delete-unreferenced-protocol-definitions-in-core-protocols-package.md). Evidence in progress.md: **Delete Unreferenced Protocol Definitions in core protocols Package** - COMPLETE. Removed 14 dead Protocol classes and 5 wholly-dead protocol modules (-1739 lines in src/), pruned **init** re-exports to the 8 live protocols, dropped the drifted DependencyGraphProtocol.build_from_links, added an **all**/namespace agreement test, and synced docs/api and wiki source mirrors. Quality gate clean, 7579 tests pass at 91.38%.
- [Domain Glossary Consistency Gate in Plan Creation](domain-glossary-consistency-gate-in-plan-creation.md). Evidence in progress.md: **Domain Glossary Consistency Gate in Plan Creation** - COMPLETE. Added canonical .cortex/wiki/glossary.md (30 curated terms) and an advisory-only terminology gate in plan creation covering exactly three detection cases; wired into both fast-forward and step-by-step planning modes, with a Terminology row in the /cortex/plan final report. 47 tests added; full suite 7464 passed.
- [Fix archive-blind plan-graph summaries in session brief and optimization handlers](fix-archive-blind-plan-graph-summaries-session-brief.md). Evidence in progress.md: **Fix archive-blind plan-graph summaries in session brief and optimization handlers** - COMPLETE. compute_artifact_graph defaults to include_archive=True; build_plan_graph_surface_bundle dropped the per-caller flag. 2 regression tests added.
- [Falsifiable Prediction Gate and Graded Miss Ledger](graded-prediction-ledger.md). Evidence in progress.md: **Falsifiable Prediction Gate and Graded Miss Ledger** - COMPLETE. Seven-form claim vocabulary, automatic grading against the next quality gate inside the existing record_gate_result hook, HIT/MISS/UNGRADED verdicts persisted as experience nodes, session(operation="predict") plus a brief predictions line, and the predict-before-you-edit doctrine rule. 66 tests added; 7727 pass at 91.42% coverage; quality and docs gates green. Review caught and fixed two grader defects: a false HIT in error-gone when the gate reports failures per check rather than per file, and a node id containing "error" reading as a test failure.
- [Mechanically Enforce the TYPE_CHECKING Import Ban](mechanically-enforce-the-type-checking-import-ban.md). Evidence in progress.md: **Mechanically Enforce the TYPE_CHECKING Import Ban** - COMPLETE. Ruff TID251 banned-api in ruff.toml plus a complementary token-based source audit wired into the quality gate covering the bare `if TYPE_CHECKING:` block form and a justification-comment allowlist. Both layers verified to fire on a real violation. 16 tests, 100% coverage on new code, full suite green.
- [Ponytail Simplification Cuts for Agentic Eval and Skill Pack Trigger Harnesses](ponytail-simplification-cuts-for-agentic-eval-and-skill-pack-trigger-harnesses.md). Evidence in progress.md: **Ponytail Simplification Cuts for Agentic Eval and Skill Pack Trigger Harnesses** - COMPLETE. All 14 reviewed over-engineering findings removed across the agentic eval, prompt-prefix, and skill pack trigger modules; net -180 lines with zero behavior change and identical trigger benchmark figures.
- [Shaping Interview Prompt (shape.md) Before Plan](shaping-interview-prompt-shape-md-before-plan.md). Evidence in progress.md: **Shaping Interview Prompt (shape.md) Before Plan** - COMPLETE. Added shape.md prompt + shape-interviewer subagent for one-question-at-a-time requirements shaping; threaded shape_log_path through plan(create) to inject "## Shaping Constraints"; extended plan.md Step 4 into a four-route gate; added shared plan-log path validation guarding both shape and explore log paths. 17 new tests.
- [Shared Prompt Reference Layer for Synapse Prompts](shared-prompt-reference-layer-for-synapse-prompts.md). Evidence in progress.md: **Shared Prompt Reference Layer for Synapse Prompts** - COMPLETE (negative result). Duplication measurement gated the plan: 0.19% extractable vs a 15% abort floor, so no _shared/ layer or include resolver was built. Delivered scripts/measure_prompt_duplication.py (standing measurement tool), tests/unit/test_measure_prompt_duplication.py (15 tests), and docs/design/synapse-prompt-duplication-report.md. Confirmed the REFACTORING_GUIDE/SUMMARY relocation to docs/guides/ was already done with no stale references.
- [Skill Pack Trigger Accuracy Benchmark and Description Tuning](skill-pack-trigger-accuracy-benchmark-and-description-tuning.md). Evidence in progress.md: **Skill Pack Trigger Accuracy Benchmark and Description Tuning** - COMPLETE. Labeled 24-fixture trigger benchmark with pairing enforced in the runner (no accuracy figure without both a control and a near-miss); zero-signal fallback removed from _do_discover so a no-match query yields an empty recommendation with an explicit reason; token-level scorer with capped keyword contribution, non-stopword bigram when_to_use matching, and a recommendation floor; refactoring and quality manifests tuned. Top-1 0.9167 to 1.0, control FP 1.0 to 0.0, near-miss FP 0.2857 to 0.1429. Glossary gained "Skill pack". 28 tests added; quality and docs gates green.
- [Wire Usage-Pattern Analytics to Session Logs and Package-Relative Tool Analysis](wire-usage-pattern-analytics-to-session-logs-and-package-relative-tool-analysis.md). Evidence in progress.md: **Wire Usage-Pattern Analytics to Session Logs and Package-Relative Tool Analysis** - COMPLETE. cortex://analysis now returns real usage_patterns (projected from .cortex/.session/ load_context logs) and a non-zero tools count (package-relative tools_dir). Dead access-log.json writer and pattern_normalization module deleted; track_usage_patterns flag now has an effect. 7736 tests pass, coverage 91.4%.

### Steps 7–8 Verification Evidence

- 2026-09-16: Complete serialized context budgets preserve required governance and
  essential layers, include exact component accounting and numeric utilization,
  reject invalid budgets, and explain insufficient required budgets. Optional
  histories/layers and bounded graph previews fit the remaining allocation.
  Existing latency and graph-heavy latency regressions pass at the documented
  100 ms median / 250 ms upper envelope.
- Four isolated public MCP smoke cases pass: actual shared rules and context
  accounting, PENDING → DONE/archive with dependency unblocking, real quality
  pass/fail outcomes, and trusted/untrusted client visibility. The smoke exposed
  and now protects request-context identity extraction and forced-run fingerprint
  invalidation. Temporary fixture managers, requests, logs, and plans are isolated.
- 205 focused safety/rules/completion/context regressions pass. The explicit PR
  smoke selection passes its JUnit acceptance checker; all 21 scheduled/manual
  slow-suite tests pass locally, including the uninstrumented graph-heavy latency
  check. Seven existing collection warnings concern model
  classes named TestResult/TestResultModel and the legacy TestLinkParser class;
  no selected slow test failed or skipped. CI has not been run remotely.
- API/configuration/testing documentation and the original review now describe
  the final contracts. No commit or push is authorized.

### Step 9 Final Verification Evidence

- A fresh MCP process with a 900-second client deadline completed the forced
  quality gate: 8,042 passed, four skipped, 91.56% global coverage, and zero
  reported errors or warnings. The detached result is
  `.cortex/.session/pre_commit_result_5738f00f2f71.json`.
  Docs timestamps, roadmap synchronization, and progress consistency all passed.
- The nine public workflow tests also passed together after replacing
  import-order-dependent module patching with isolated canonical ContextVars.
  Their JUnit report passed the nonempty/no-failure/no-skip acceptance checker.
- Scoped coverage across the changed context allocation/assembly, graph preview,
  client identity, and forced-freshness regions is 138/145 executable lines
  (95.17%). This is not a claim of 95% coverage for every containing file.
- Session analysis found only two current-session context loads: average base
  selection utilization 0.298 and relevance 0.404. This small sample is not
  final-response accounting or completion evidence. Use task-specific context
  requests rather than oversized general-session budgets.
- Lessons: exercise negotiated MCP identities and real pass-to-fail gate
  transitions; distinguish client deadlines from detached worker timeouts;
  isolate request storage, not whichever modules happen to be imported; run
  latency measurements without coverage/parallel-suite instrumentation.
  These reinforce existing testing guidance; no new framework rule is needed.

### Post-Prompt Analysis

- Context effectiveness: the two-load sample and its limitations are recorded
  above; it does not establish precision/recall or a causal performance gain.
- Session optimization: the public usage-pattern resource returned
  `TypeError: Object of type CoAccessPattern is not JSON serializable`.
  This non-blocking hook failure is tracked as an ASAP
  [serialization investigation](../../investigate-usage-pattern-analysis-json-serialization.md).
  The original routing file was restored without flushing unrelated phase state.
- Tools optimization: analysis reported 14 tools, below its target of 40, no
  consolidation candidates, and a long `manage_file` docstring advisory.
  This source analysis is not an independent inventory of every runtime tool.
- Session Scope Risk: multi-goal session. Plugin/hook architecture discussion
  interleaved with remediation verification. Keep any plugin implementation in
  a separate session/change; mixing it here would increase verification and
  state-tracking risk. No plugin implementation was performed.
- Compaction skipped (not required for this prompt).
- Artifacts: one bounded investigation plan; no new skill or rule. Existing
  testing guidance already covers the actionable remediation lessons.
