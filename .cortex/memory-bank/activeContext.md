# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-28)

- ✅ **Structured final-report types (Pipeline/Diagnostic/Artifact) + Synapse gitlink** - COMPLETE (2026-03-28) - Synapse submodule commits six primary prompts to typed final-report sections per `docs/guides/synapse-final-report-templates.md`; MD032 markdown fixes; superproject updates the guide, `test_synapse_final_report_prompt_alignment`, `.claude/agents/implement-code.md`, memory bank index/history, and bumps the submodule pointer.

- ✅ **Migration: language rule templates and scaffolded_languages reporting** - COMPLETE (2026-03-28) - Synapse submodule adds minimal rules/_templates for Go, Java, JavaScript, Rust, and TypeScript. Structure migration now derives scaffolded_languages from scaffolded rule/script paths (_collect_scaffolded_languages, _to_json_list) with expanded unit tests; plan doc and AGENTS touched. Submodule pointer updated to the new Synapse commit.

- ✅ **Migration: Language-Agnostic Rules and Scripts Scaffolding** - COMPLETE (2026-03-28) - Documented migrate Step 2b (language detection, rules/scripts scaffolding, quality gate routing) and extended expected migration JSON. Clarified zero-arg run_quality_gate and LanguageQualityRouter docs; added unit tests proving resolve_adapter_worker selects SwiftAdapter vs PythonAdapter. Optional TradeWing template reconciliation remains a manual follow-up outside this repo.

- ✅ **Synapse final-report standardization (PARTIAL)** - COMPLETE (2026-03-28) - Step 1 delivered REFACTORING_GUIDE appendix inventory (pipeline/single-shot/meta); .cursor/commands not in repo. Next: canonical templates and prompt updates per plan.

- ✅ **Structured Final Reports — Step 2 (canonical templates)** - COMPLETE (2026-03-28) - Added docs/guides/synapse-final-report-templates.md: base final-report skeleton, per-prompt deltas (commit, implement, fix, analyze, create-plan, review), anti-patterns, and distinction from MCP JSON. REFACTORING_GUIDE appendix links to the guide. Plan synapse-prompt-final-report-standardization Step 2 marked done; Steps 3–5 remain on roadmap.

- ✅ **Structured Final Reports (PARTIAL)** - COMPLETE (2026-03-28) - Synapse primary prompts now require canonical final-report markdown per docs/guides/synapse-final-report-templates.md; integration test guards section markers.

- ✅ **Structured Final Reports — commit (Step 3 + test)** - COMPLETE (2026-03-28) - Synapse submodule commit documents final-report format in primary prompts; integration test guards required headings; plan Step 3 done, Steps 4-5 still open on roadmap.

- ✅ **Structured Final Reports — implement-code handoff + superproject commit** - COMPLETE (2026-03-28) - Synapse submodule chore commit documents orchestrator final-report vs `pipeline_handoff` in `cursor-agents/implement-code.md`; superproject adds alignment integration test, REFACTORING_GUIDE appendix note, plan Step 4/5 partial updates, regenerated `.claude/agents`, and bumped gitlink. Optional `.cursor/commands` wrappers still absent.

- ✅ **Structured Final Reports for Cortex Synapse Prompts** - COMPLETE (2026-03-28) - Extended `test_synapse_final_report_prompt_alignment` for Cursor command markdown when a `.cursor/commands` tree exists; REFACTORING_GUIDE links the archived plan; Phase B pre-commit tests isolate roadmap/progress consistency from workspace drift. Optional workflow command files under `.cursor/commands/` are gitignored (`/.cursor/`); use them locally or mirror content into tracked paths if sharing is required. Plan Steps 4–5 complete; plan archived.

- ✅ **Session Scope Lock — remaining prompt alignment** - COMPLETE (2026-03-28) - Added explicit ## Session Discipline sections to Synapse commit.md and analyze.md (CLAUDE.md parity with pointers to Step 13 split-commit hint and Step 5 scope risk check); integration tests assert headings.

- ✅ **MCP startup: Synapse submodule sync (stash + structured outcomes)** - COMPLETE (2026-03-28) - `synapse_submodule_startup` runs bounded `git submodule update --init --recursive` before MCP listen; when `.cortex/synapse` has local changes, stashes before update and pops after; skips when `CORTEX_SKIP_SYNAPSE_UPDATE` is set or root is not a git checkout; `SynapseStartupSyncResult` / `SynapseStartupSyncOutcome` for logging and tests; non-fatal on git error, timeout, stash, or stash-pop failure. Wired into server startup; unit tests; AGENTS/troubleshooting connectivity preflight; memory bank index.

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

No queued pending plans under `.cortex/plans` in [roadmap.md](roadmap.md); next slice is chosen from Future Enhancements or the implement command.

## Recent Changes

MCP startup Synapse sync (2026-03-28): dirty submodule worktrees are stashed around `git submodule update --init --recursive`; structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
