# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-04-07)

- ✅ **File Review Reports into Memory Bank (PARTIAL)** - COMPLETE (2026-04-07) - Implemented Step 1 foundation by adding `ArtifactType` enum + typed metadata mapping for fileable artifact storage/naming conventions and added focused unit tests.

- ✅ **MCP Tool for Writing Skills and Rules from Analysis Agents (PARTIAL)** - COMPLETE (2026-04-07) - Added `write_artifact` tool and supporting tests so analysis agents can write skills/rules through MCP; next slice should update routing prompts and extend test matrix to full plan scope.

- ✅ **MCP Tool for Writing Skills and Rules from Analysis Agents (PARTIAL)** - COMPLETE (2026-04-07) - Updated Synapse analyze and post-prompt routing guidance to use `write_artifact` for skills/rules, aligning prompt instructions with the implemented MCP write path.

- ✅ **MCP Tool for Writing Skills and Rules from Analysis Agents** - COMPLETE (2026-04-07) - Completed write_artifact integration by aligning analyze prompt skill routing with registered tool behavior and updating structural tests; quality gate passes.

- ✅ **Memory Bank Operations Log (log.md) (PARTIAL)** - COMPLETE (2026-04-07) - Completed Step 1 foundation by adding `MemoryBankFile.LOG` (`log.md`), new operations-log formatter/types module, and tests validating parseable entry format.

- ✅ **Memory Bank Operations Log (operations log) (PARTIAL)** - COMPLETE (2026-04-07) - Implemented Step 2 partial slice by wiring `update_memory_bank(operation="log_append")` with append-only log writes and validation, plus expanded operations-log tests.

- ✅ **Memory Bank Operations Log (operations log) (PARTIAL)** - COMPLETE (2026-04-07) - Implemented Step 4 partial slice by surfacing `## Recent Operations` in `cortex://context` from `.cortex/memory-bank/log.md` and adding resource tests for log-present and log-missing behavior.

- ✅ **Memory Bank Operations Log (operations log)** - COMPLETE (2026-04-07) - Finalized Step 5 with explicit `manage_file(file_name="log.md", operation="read")` test coverage and completed the roadmap plan.

- ✅ **Cleanup Function-Length Exclusions in Constants** - COMPLETE (2026-04-07) - Removed ad-hoc test path exclusions from FUNCTION_LENGTH_EXCLUDED_PATHS and moved test-file handling into deterministic checker policy for FILES mode, with regression tests covering the behavior.

- ✅ **Memory Bank Lint taxonomy slice (PARTIAL)** - COMPLETE (2026-04-07) - Implemented foundational lint check types and first two checks (orphaned plans and missing plan files) with tests under `src/cortex/tools/lint/` and `tests/unit/tools/lint/`.

- ✅ **Memory Bank Lint stale-context check (PARTIAL)** - COMPLETE (2026-04-07) - Added `StaleActiveContextCheck` to flag unresolved stale `activeContext.md` dates against `progress.md`, plus unit coverage for stale/resolved/recent cases.

- ✅ **Memory Bank Lint cross-reference check (PARTIAL)** - COMPLETE (2026-04-07) - Added wiki-only `CrossRefCheck` to flag missing `.cortex/wiki` page targets referenced via wiki/markdown links, with unit coverage for missing refs and absent wiki directories.

- ✅ **Memory Bank Lint orphaned-wiki check (PARTIAL)** - COMPLETE (2026-04-07) - Added wiki-only `OrphanedWikiPagesCheck` to detect `.cortex/wiki` pages without inbound links from wiki or memory-bank markdown files, with focused unit tests.

- ✅ **Memory Bank Lint code-claim check (PARTIAL)** - COMPLETE (2026-04-07) - Added `CodeClaimCheck` with optional `.cortex/config/lint-config.json` support and malformed-config fallback behavior, with unit coverage for mismatch, missing-config, and malformed-config flows.

- ✅ **Memory Bank Lint (/cortex/lint-wiki) (PARTIAL)** - COMPLETE (2026-04-07) - Added `lint_memory_bank` tool (Step 2 slice) to execute lint checks and return structured report metrics; wired tool registration and tests.

- ✅ **Memory Bank Lint stale-threshold config wiring (PARTIAL)** - COMPLETE (2026-04-07) - Wired `stale_threshold_days` from `.cortex/config/lint-config.json` into `lint_memory_bank` execution, documented config usage, and added tests for configured threshold behavior.

- ✅ **Memory Bank Lint (/cortex/lint-wiki)** - COMPLETE (2026-04-07) - Completed memory-bank lint workflow and closed remaining parsing gap for roadmap markdown-linked plan references with regression coverage.

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
