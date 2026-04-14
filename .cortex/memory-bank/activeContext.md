# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-04-14)

- ✅ **Remove offline setup/bootstrap support** - COMPLETE (2026-04-14) - Removed `preflight-offline` and `bootstrap-offline` setup paths from Makefile and docs, and documented offline setup as intentionally out of scope unless explicitly requested.

- ✅ **FastMCP v3 — Phase 2 official lifecycle APIs (PARTIAL)** - COMPLETE (2026-04-14) - Server initialization now owns roots/list_changed handler wiring and server.py no longer patches FastMCP internals directly; startup tests added to lock this behavior while remaining disconnect shim work is deferred to next subtask.

- ✅ **FastMCP v3 — Phase 2 disconnect shim decision (PARTIAL)** - COMPLETE (2026-04-14) - Disconnect suppression patch in main startup is intentionally retained with explicit rationale until middleware replacement in Phase 3, backed by regression tests for patched/unpatched ClosedResourceError behavior.

- ✅ **FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs** - COMPLETE (2026-04-14) - Completed migration away from server-level private FastMCP patches for prompt and roots flows, with explicit defer of disconnect request wrapper removal to Phase 3 middleware work.

- ✅ **FastMCP v3 — Phase 3: Middleware for Disconnect Handling and Request Logging** - COMPLETE (2026-04-14) - Replaced private request monkey-patching with FastMCP middleware chain, added debug-gated request logging and response limiting with optimization-config support, and added middleware-focused unit tests while removing the legacy disconnect patch path from startup.

- ✅ **FastMCP v3 — Phase 4: Transport Configuration Cleanup** - COMPLETE (2026-04-14) - Migrated transport startup to explicit FastMCP v3 run kwargs, removed legacy env forwarding, switched port-default transport to streamable-http, and updated tests/docs for the new behavior.

- ✅ **FastMCP v3 — Phase 5: New Features (Lifespan, Visibility, Auth, Transforms)** - COMPLETE (2026-04-14) - Added server lifespan-managed startup injection, dynamic setup component visibility, server-enforced auth on write tools, optional ResourcesAsTools/PromptsAsTools compatibility transforms, and a `CORTEX_DEV` hot-reload dev workflow with test coverage.

- ✅ **Fix: Stale Test-Count Metric in progress.md What Works Section (PARTIAL)** - COMPLETE (2026-04-14) - Implemented stale numeric claim detection in memory-bank linting and refreshed progress.md What Works metrics; full completion blocked by unrelated repository gate failures.

- ✅ **Fix: Stale Test-Count Metric in progress.md What Works Section** - COMPLETE (2026-04-14) - Updated stale What Works test metrics and added stale numeric claim lint coverage with tests and docs updates.

- ✅ **Refactor: Split Oversized `src/cortex/tools/session/brief.py` and `src/cortex/tools/optimization/handlers.py`** - COMPLETE (2026-04-14) - Completed verification of the module split, confirmed all six target modules are under the 400-line limit, and validated no regressions via a green quality gate.

- ✅ **Improvement: Layered Context Budget (L0–L3 Tiering) for context resource** - COMPLETE (2026-04-14) - Implemented layered context loading (L0-L3), integrated context resource/session config support, and added tests validating layered behavior and token budgets.

- ✅ **Layered context budget modules and routing** - COMPLETE (2026-04-14) - Implemented layered context helpers (L0-L3), updated optimization handlers/context appenders wiring, and added resource tests for layered context loading behavior.

- ✅ **Improvement: Temporal Memory with Validity Windows (PARTIAL)** - COMPLETE (2026-04-14) - Added temporal indexing and contradiction detection, introduced timeline query support wired through `manage_file` operations, and integrated best-effort background temporal indexing into session startup.

- ✅ **Improvement: Temporal Memory with Validity Windows** - COMPLETE (2026-04-14) - Implemented temporal fact storage, indexing, timeline retrieval, and session integration with comprehensive tests and quality gate passing.

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

Refactor in progress (2026-04-14): split `session/brief.py` and `optimization/handlers.py` into `brief_cap.py`, `brief_loaders.py`, `context_appenders.py`, and `context_loaders.py`; compatibility symbols in `handlers.py` were retained for existing tests while finishing structural debt cleanup.

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
