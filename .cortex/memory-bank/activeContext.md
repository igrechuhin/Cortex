<!-- memory_type: preference -->
# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-09-17)

- ✅ **Investigate usage-pattern analysis JSON serialization failure** - COMPLETE (2026-09-17) - Fixed the public usage-pattern response boundary with Pydantic JSON-mode dumps for co-access, task, and unused-file models; corrected rule totals to count rules rather than categories. Real FastMCP nonempty resource smoke and workspace-isolation regressions passed. Historical zero inventory totals were not attributed to an unproven routing defect. Eight quality checks passed: 8,082 tests, four skips, 91.61% coverage; docs gate passed. Original 398-byte routing configuration remained unchanged.

- ✅ **Resolve quality-gate MCP transport timeout** - COMPLETE (2026-09-17) - Bounded public Phase A waits to 20 seconds with resumable existing job handles, worker-owned pending metadata, preserved terminal failures, and live-worker mutation guards. Fresh MCP requests met the 30-second deadline; 66 focused tests and 8,089 full-suite tests passed, with 91.60% overall coverage. Synchronous preflight semantics preserved; consumer guidance updated.

- ✅ **Package Cortex commands and thin lifecycle hooks as a plugin** - COMPLETE (2026-09-17) - Completed Claude/Codex plugin packaging after explicit user approval of cheap best-effort deduplication instead of strict exactly-once semantics. Existing handoff receipts and fingerprints retained: same-turn Codex compactions may collapse, changed Claude transcript metadata may repeat writes, and startup suppression is process-local. No product code or state store added for this acceptance change. Native workflows, startup, pre-compaction persistence, fresh-process resume, visible nonblocking failure, coexistence, update and uninstall passed in actual hosts. Focused verification rerun: 48 passed; prior unchanged-code quality proof: 8,100 passed, four skipped, 91.71% coverage. Guide: docs/guides/plugins.md; native evidence: .cortex/.session/claude-plugin-native-evidence.json. Codex local distribution must remain at its generated path.

- ✅ **Repair existing plan registration updates** - COMPLETE (2026-09-17) - Existing canonical plan registrations update in place and unchanged replay succeeds instead of returning a false missing-section error. Pathless replay preserves section headers. Atomic same-directory roadmap replacement preserves original registration on partial-write or replacement failure and retains permissions. Unfinished-plan removal guards remain unchanged. Added six behavior regressions; removed two obsolete expectations. 123 focused tests and 8,104 full-suite tests passed, four skips; all eight quality checks passed, 91.73% overall and 100% changed-statement coverage. Autofix/quality transport deadlines required detached-result recovery; separate ASAP autofix timeout investigation registered. Evidence: .cortex/.session/plan-registration-repair-evidence.json.

- ✅ **Investigate autofix MCP transport timeout** - COMPLETE (2026-09-17) - Autofix now returns within a 20-second bounded wait, resumes durable jobs and delivers retained terminal outcomes. All final mutations run in the detached worker; live fix and quality jobs prevent conflicting launches. Recovered original timeout evidence and documented MCP reload requirements. Verification: 42 focused tests; real stdio MCP smoke with a 30-second deadline, 64.871-second worker, same PID across server reconnect and quality-gate contention.

## Completed Work (2026-09-16)

- ✅ **Investigate Cortex quality gate MCP transport timeout** - COMPLETE (2026-09-16) - Recovered the original detached worker: it completed in 109.14 seconds after the client timed out at 30 seconds. A fresh FastMCP client with a 900-second request timeout and unchanged 600-second worker timeout returned the full quality failure and successful docs result in 95.10 seconds, with no duplicate worker. The request deadline is independent of worker timeout; no server heartbeat change was needed. Remediation continues against actual gate diagnostics.

- ✅ **Remediate Project Review Findings: Safety, Rules, Planning, Context, and Verification** - COMPLETE (2026-09-16) - Completed Steps 7–9 after the existing safety/rules/lifecycle remediation: complete serialized context budgets with mandatory-content preservation and bounded graph previews; real public MCP lifecycle, identity, and gate pass/failure tests; explicit PR smoke and scheduled/manual slow CI with fail-closed JUnit checks. Fixed negotiated client identity extraction and forced-run fingerprint invalidation. Inline review: no_gaps. Fresh quality gate: 8,042 passed, four skipped, 91.56% coverage, zero reported errors/warnings. Nine public workflows and all 21 slow tests passed; docs gate passed. Remote CI not run; no commit or push.

## Completed Work (2026-09-08)

- ✅ **Cortex Project Review and Improvement Recommendations 2026-09-08 [reviews/review-cortex-project-review-and-improvement-recommendations-2026-09-08-2026-09-08.md]** - COMPLETE (2026-09-08) - [Cortex Project Review and Improvement Recommendations 2026-09-08](reviews/review-cortex-project-review-and-improvement-recommendations-2026-09-08-2026-09-08.md) — Review report for Cortex Project Review and Improvement Recommendations 2026-09-08 (2026-09-08); key findings summarized.

- ✅ **Project Review Remediation: Owned-File Quality Scope (PARTIAL)** - COMPLETE (2026-09-08) - <!-- memory_type: preference -->

- ✅ **Owned-File Quality Scope Session Analysis 2026-09-08 [analyses/analysis-owned-file-quality-scope-session-analysis-2026-09-08-2026-09-08.md]** - COMPLETE (2026-09-08) - [Owned-File Quality Scope Session Analysis 2026-09-08](analyses/analysis-owned-file-quality-scope-session-analysis-2026-09-08-2026-09-08.md) — Session analysis for Owned-File Quality Scope Session Analysis 2026-09-08 (2026-09-08); decisions and follow-ups recorded.

- ✅ **Project review remediation Step 2 — snapshot safety** - COMPLETE (2026-09-08) - Snapshot/restore path containment and recovery now have 84 synthetic regression cases; reflection handler matching has eight added cases. Fresh full quality/reflection gates passed with 7,863 tests, four skipped, and 91.48% coverage. Next: Step 3 historical-read containment; plan remains PARTIAL.

- ✅ **Project review remediation Step 3 — historical-read scope** - COMPLETE (2026-09-08) - Canonical memory-bank Markdown paths and fixed WAL log paths are validated before reads, with late content-path revalidation. Missing-file and reverse-delta semantics remain intact. Fresh quality/reflection gates passed with 7,909 tests, four skipped, and 91.49% coverage. Next: Step 4 shared-rule delivery; plan remains PARTIAL.

- ✅ **Project review remediation Step 4 complete; Step 5 next** - COMPLETE (2026-09-08) - PARTIAL plan: Steps 1–4 complete and Steps 5–9 PENDING. Shared generic/general rules now survive exclusive categorization and serialization; merge identity preserves local override precedence and distinct relative paths. Public counts and tokens match delivered rules, with separate governance accounting. Twenty-one integration cases exercise real loading, budgets, overrides, all category/source combinations, and actual resource text. Fresh gate: 7,930 passed, four skipped, 91.49% coverage; reflection approved with reviewed advisories. Live rules proof: one shared rule, 702 delivered tokens, byte-identical consecutive responses. All 49 fingerprinted vendor/lock files unchanged. Next work is Step 5 recoverable/idempotent multi-file plan completion. No commit or push.

- ✅ **Project review remediation Step 5 complete** - COMPLETE (2026-09-08) - Completion is now consistent, idempotent, and recoverable through prevalidation, a bounded typed operation record, one cross-process lock, expected-hash atomic writes, WAL preservation, canonical DONE metadata, exact retry semantics, and conflict-aware rollback/recovery. The fresh Cortex gate passed all checks; 38 focused cases cover success and failure boundaries. The plan remains PARTIAL with Steps 6–9 pending. Next: Step 6, correct actionable plan graphs and repair historical metadata.

- ✅ **Project review remediation Step 6 complete** - COMPLETE (2026-09-08) - Actionable graphs now share archive-aware unique discovery and preserve manual/custom metadata intent. Thirteen backed-up historical status repairs were evidence-based, status-only, and idempotent. Fresh quality gate passed with zero errors/warnings; graph/context/session agree on one READY plan. Steps 7–9 remain PENDING; next is Step 7. Repair evidence and snapshot reference are retained in the remediation plan.
Step 1 is complete: structural and Markdown checks share a narrow validated installed-skill boundary, preserve source ownership through symlinks, and check all owned Markdown files in full gates. CI/local parity and link validation follow the same policy. Added 34 regression cases; a newly started Cortex MCP server passed the forced-fresh full quality gate. All 49 fingerprinted package/lock files remained unchanged. Plan project-review-remediation-2026-09-08 remains PENDING for Steps 2–9.

## Completed Work (2026-09-05)

- **Summary (2026-09-05)** - 1 entries archived.

## Completed Work (2026-08-31)

- **Summary (2026-08-31)** - 1 entries archived.

## Completed Work (2026-08-30)

- **Summary (2026-08-30)** - 1 entries archived.

## Completed Work (2026-08-28)

- **Summary (2026-08-28)** - 1 entries archived.

## Completed Work (2026-08-21)

- **Summary (2026-08-21)** - 1 entries archived.

## Completed Work (2026-08-18)

- **Summary (2026-08-18)** - 1 entries archived.

## Completed Work (2026-08-15)

- **Summary (2026-08-15)** - 1 entries archived.

## Completed Work (2026-08-08)

- **Summary (2026-08-08)** - 1 entries archived.

## Completed Work (2026-08-06)

- **Summary (2026-08-06)** - 1 entries archived.

## Completed Work (2026-08-02)

- **Summary (2026-08-02)** - 1 entries archived.

## Completed Work (2026-07-23)

- **Summary (2026-07-23)** - 1 entries archived.

## Completed Work (2026-07-22)

- **Summary (2026-07-22)** - 1 entries archived.

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

Current work is tracked in [roadmap.md](roadmap.md): project review remediation, Steps 1–6 complete; Step 7 is next.

## Recent Changes

Plan frontmatter normalization (2026-08-30): `PlanExecutionMode` enum and `normalize_plan_slug`/`resolve_plan_status_token` helpers added to `artifact_graph.py`; new `plan_frontmatter_normalize.py` rewrites plan frontmatter to canonical schema and is wired into `pre_commit_fix_quality.py`'s memory-bank lint autofix; `prompts_registration.py` workflow-redirect branch extracted to `_try_workflow_redirect`.

All-or-nothing complete_plan validation (2026-08-28): `progress_entry` format check now runs before any write, alongside `date_str`, via `_reject_bad_inputs` in `completion.py`; previously a late rejection during archive left the roadmap and activeContext already mutated with no progress row.

Agent spec honesty guard (2026-08-21): new regression test `test_agent_spec_honesty_guards.py` blocks Synapse `claude-agents/*.md` specs from shipping pre-filled `"status":"passed"` handoff templates and requires the no-fabrication rule wherever an agent writes a gate result; `implement-code.md` granted `ReadMcpResourceTool`; Synapse submodule bumped to a77cf2c4.

PHP language keywords and rules category alias (2026-08-18): added a `php` bucket to language-keyword context detection (mirrored in `context_detector.py`, `config_defaults.py`, `_config.py`, and the generated JSON snapshots); `RulesLoader._resolve_category_alias` maps `generic` <-> `general` so Synapse's `general` category and Cortex's `generic` category both resolve.

RulesIndexer recursive .mdc discovery (2026-08-15): `find_rule_files` uses `rglob` (was one-level `iterdir` + `glob`) and the pattern set gained `*.mdc`, so nested Synapse rules are indexed; `build_synapse_manager` extracted as a sync helper in `factory_optimization.py` and wired into the rules manager in both `factory_optimization.py` and `container_optimization.py`.

Persistent Phase A fingerprinting (2026-08-08): `pre_commit_fingerprint_store.py` added for cross-process fingerprint persistence keyed by git HEAD; `compute_git_file_hash` now hashes file contents, not just names, so autofix-only content rewrites are no longer skipped.

PHP language/framework adapter support (2026-08-08): `php_adapter.py` and `php_parsing.py` added under `services/framework_adapters/`; PHP wired into `language_detector.py`, `language_quality_router.py`, `framework_adapters/detection.py`, `hook_templates.py`, and `core/constants.py`.

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
