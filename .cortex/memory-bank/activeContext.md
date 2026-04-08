# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-04-08)

- ✅ **Ingest prompt workflow registered (PARTIAL)** - COMPLETE (2026-04-08) - Implemented plan Step 3 by adding `.cortex/synapse/prompts/ingest.md` and registering it in `prompts-manifest.json`; quality gate still failing due to unrelated `/cortex/plan` integration tests, so roadmap entry remains pending.

- ✅ **Ingest Tool for Cortex Memory Bank (/cortex/ingest) (PARTIAL)** - COMPLETE (2026-04-08) - Completed plan Step 4 slice: `cortex://context` now includes `## Recently Ingested Sources` (top 5 from `.cortex/memory-bank/sources/`) with heading-based title extraction and filename fallback; added focused unit/resource tests.

- ✅ **Ingest source-summary lint consistency (PARTIAL)** - COMPLETE (2026-04-08) - Extended `OrphanedWikiPagesCheck` to validate ingest source/summary consistency under `.cortex/memory-bank/sources/` and `.cortex/memory-bank/queries/`, adding tests for orphaned sources and summaries referencing missing source files.

- ✅ **Ingest Tool for Cortex Memory Bank (/cortex/ingest)** - COMPLETE (2026-04-08) - Completed ingest pipeline end-to-end: ingest tool, ingest prompt workflow, recent-ingested-sources context exposure, and memory-bank lint source/summary consistency checks are implemented and validated.

- ✅ **Compress Cortex Synapse Prompts and Memory Bank Files (PARTIAL)** - COMPLETE (2026-04-08) - Implemented Step 2 file-type classifier (`detect_file_type` with extension map + fallback heuristic), exported symbols via compress package init, and added unit coverage with a passing quality gate.

- ✅ **Compress Cortex Synapse Prompts and Memory Bank Files (PARTIAL)** - COMPLETE (2026-04-08) - Added `compress_cortex_internal_files` safe Step 6 entrypoint for Cortex internal targets (prompts, cursor-agents, activeContext/progress), defaulting to dry-run; exported symbol and added focused unit tests.

- ✅ **Compress tools and tests prepared** - COMPLETE (2026-04-08) - Added compress tool modules and unit tests, then executed commit pipeline preflight and Phase A checks successfully.

- ✅ **Compress pipeline verification criteria (PARTIAL)** - COMPLETE (2026-04-08) - Implemented and tested batch-level success-criteria verification for compression outcomes to enforce plan Step 6 acceptance checks programmatically.

- ✅ **Compress pipeline robustness updates** - COMPLETE (2026-04-08) - Added extension-based detection support and batch compression success criteria coverage; validated full quality/docs gates and prepared commit pipeline artifacts.

- ✅ **Compression semantics repair** - COMPLETE (2026-04-08) - Safe fallback compressor and stricter Step 6 verification; memory bank restored to committed canonical text.

- ✅ **Agent-Internal Brevity Rule for Sub-Agent Communication** - COMPLETE (2026-04-08) - Added agent-internal-communication.mdc rule, merged into cortex://rules resource, updated implement-code and shared-defaults prompts, extended pipeline_handoff data docstring, added tests and brevity word-count fixtures (no top-level scripts/).

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

Next implementation slice: **[QG-S1] Add EXTENSION_SCRIPT_MAP** per [roadmap.md](roadmap.md) Blockers and `.cortex/plans/swift-qg-s1-add-extension-script-map.plan.md`.

## Recent Changes

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
