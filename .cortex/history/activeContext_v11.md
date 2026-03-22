# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-22)

- ✅ **Clean up legacy Node package manifest and clarify Node dependency** - COMPLETE (2026-03-22) - Removed root `package.json`; contributor docs and AGENTS describe a Python-first workflow and CI/global `cspell` as the remaining Node surface; plan archived to `.cortex/plans/archive/`.

- ✅ **Decompose oversized tool modules (PARTIAL)** - COMPLETE (2026-03-22) - Contributor docs now include Architecture guardrails under Code Constraints (size limits, how to request exemptions, quarterly review). Roadmap item kept pending until audit and any remaining splits land.

- ✅ **Decompose oversized tool modules by responsibility boundaries** - COMPLETE (2026-03-22) - Tool-module decomposition batches 1–4 finished: split models re-exports, pre-commit tools, similarity engine; contributing guardrails; file/function size checks clean. Guard test verifies stable facades and line caps.

- ✅ **Gate MCP list_roots to advertised roots capability** - COMPLETE (2026-03-22) - `project_root_resolver` checks client roots capability before `list_roots()` so bridges without roots do not close the transport; unit tests in `test_project_root_resolver.py`.

- ✅ **Decomposed tool module boundary governance test** - COMPLETE (2026-03-22) - `tests/unit/test_decomposed_tool_module_boundaries.py` asserts stable facades, import paths, and logical line caps aligned with decomposition policy.

- ✅ **Fix broad exception handling and subprocess log fd comment** - COMPLETE (2026-03-22) - Documented intentional broad except in project_root_resolver (_fetch_roots_path) and mcp_stability (usage metrics + tool wrapper), plus diagnostic catches in pre_commit_connection and health_check; added Unix fd inheritance comment in _spawn_detached_process; added RuntimeError fallback unit test; marked REV-2026-03-22-1/2 RESOLVED in code review report. Inventory: the `cortex.tools` package initializer uses intentional side-effect imports to register tool modules at import time—lazy/deferred registration remains a future refactor. Fixed MD036/heading style in sibling .cortex/plans drafts so markdown gate passes.

- ✅ **Reconstruct roadmap backlog and enforce docs-gate consistency invariant** - COMPLETE (2026-03-22) - Docs-gate invariant check_roadmap_progress_consistency integrated into Phase B; tests added; progress reconciled (superseded PARTIALs); roadmap Refactoring backlog for remaining decomposition; Steps 1–5 satisfied.

- ✅ **Add offline mode and preflight network/test failure differentiation for bootstrap** - COMPLETE (2026-03-22) - Preflight CLI and `make preflight` (exit 2 on unreachable registry); `make bootstrap-offline` with `WHEELHOUSE`; contributing.md **Offline / Restricted-Network Setup**; path-gated `.github/workflows/bootstrap-offline.yml` (Docker `--network none`, assert `make preflight` exits 2); regression tests; plan archived to `.cortex/plans/archive/Other/fix-bootstrap-offline-preflight-reliability.md`.

- ✅ **Resolve contributor documentation drift and conflicting quality workflow instructions** - COMPLETE (2026-03-22) - Updated docs/development/contributing.md with .cortex-centric project layout and a human vs MCP quality matrix aligned with AGENTS.md; removed the forbidden legacy Memory Bank path substring from all Markdown; adjusted prompts, ADRs, and tools docs; added unit tests for contributing content and repo-wide Markdown scan.

- ✅ **Decompose oversized tool modules (remainder)** - COMPLETE (2026-03-22) - Verified governance: all src files ≤400 logical lines and functions ≤30 lines; quality gate clean with no file/function length violations. Archived decomposition plan batches 1–4 complete; remainder closed.

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

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
