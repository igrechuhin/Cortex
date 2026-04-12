# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-04-12)

- ✅ **Wiki ingest routing (PARTIAL)** - COMPLETE (2026-04-12) - When `.cortex/wiki/` exists, MCP `ingest` stores raw markdown under `wiki/sources/`, emits a frontmatter summary page (category from tags), appends `wiki/index.md`, and cortex://context recent-ingest prefers wiki `sources/` over memory-bank.

- ✅ **Project Wiki for Attached Projects (PARTIAL)** - COMPLETE (2026-04-12) - Registered `/cortex/query` Synapse workflow: `query.md`, manifest, `query` prompt icon, `TestQuerySynapsePrompt`. Plan Step 5 done; Steps 6–8 remain.

- ✅ **Wiki staged ingest helper (PARTIAL)** - COMPLETE (2026-04-12) - Added `cortex.tools.wiki` with `wiki_ingest_staged_docs` for commit-pipeline wiki updates; patterns configurable via schema frontmatter; `ingest_source_at_project_root` exposes sync ingest for tooling.

- ✅ **Project Wiki (PARTIAL): commit wiki ingest bridge** - COMPLETE (2026-04-12) - Synapse commit.md documents Phase A→B call to wiki_ingest_staged_docs and staging wiki outputs before Phase B docs gate.

- ✅ **Project Wiki (PARTIAL): idempotent staged wiki ingest** - COMPLETE (2026-04-12) - Commit-time `wiki_ingest_staged_docs` now keys on `stable_ingest_rel` (repo path slug): identical content returns skipped/unchanged; updates archive prior raw under `sources/{slug}-v{n}.md` and refreshes the deterministic wiki summary with a cumulative `## Revision` section.

- ✅ **Project Wiki (PARTIAL): init_wiki lazy registration** - COMPLETE (2026-04-12) - `init_wiki` MCP prompt is no longer always registered from the Synapse manifest; it appears only when `.cortex/wiki/schema.md` exists and no summary pages exist under concepts/entities/decisions/workflows/analyses (sources-only does not suppress). Registration runs on first `list_prompts` after startup repair, independent of `should_mount_setup`.

- ✅ **Project Wiki for Attached Projects (.cortex/wiki/)** - COMPLETE (2026-04-12) - Shipped .cortex/wiki layout, session wiki_status, conditional init-wiki registration, wiki-aware ingest and index updates, ask prompt, file_artifact mirror to wiki/analyses, wiki lint checks including index staleness, idempotent wiki_ingest_staged_docs for commits, self-hosted wiki seed; Synapse analyze/review prompts now record memory-bank and wiki mirror paths for filed analyses.

- ✅ **Auto-Ingest from Git Hooks (Wiki Auto-Update)** - COMPLETE (2026-04-12) - Wiki staged ingest wired into commit prompt; idempotent slug ingest, revision notes, and 100% unit coverage on staged_ingest.

- ✅ **Planning modes (PARTIAL)** - COMPLETE (2026-04-12) - Plan tool supports planning_mode step with draft files, section state footer, continue/approve/finalize_step; fast-forward unchanged.

- ✅ **Fast-Forward vs. Step-by-Step Planning Modes** - COMPLETE (2026-04-12) - Planning modes: fast-forward and step-by-step MCP flows, draft hygiene, session stale-draft hints, tests, and quality fixes (operations log timestamps, test helpers).

- ✅ **Type Policy Hardening: Remove Any from Production Code** - COMPLETE (2026-04-12) - Replaced pre-commit status summaries with Pydantic BaseModel and StrEnum; return ModelDict; added Ruff ANN401 for src with tests ignored; narrowed numeric assertions in unit tests.

- ✅ **Deprecation Completion: Legacy Quality Entrypoints Migration (PARTIAL)** - COMPLETE (2026-04-12) - Preflight Phase A now delegates to run_detached_phase_a_checks; e2e uses run_quality_gate with session checks-task.json; sunset 2026-07-01 documented; migration matrix + compat marker module.

- ✅ **README Tool Inventory Parity Fix** - COMPLETE (2026-04-12) - README Key Tools and AGENTS.md list all 12 MCP tools; added tests/docs parity tests; dev group includes uv-build for offline preflight; Phase B test helpers for function-length limits.

- ✅ **Network-Resilience Onboarding** - COMPLETE (2026-04-12) - Added --offline preflight, make preflight-offline, README restricted-network steps, bootstrap-offline preflight contract, CORTEX_REPO_ROOT test hook, integration smoke test.

- ✅ **Commit: legacy quality + preflight + tests** - COMPLETE (2026-04-12) - Shipped deprecation compat, offline bootstrap contract, wiki ingest for README/tools.md, and modular phase-tool unit tests.

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

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
