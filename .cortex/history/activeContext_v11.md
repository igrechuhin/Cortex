# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-02-17)

- ✅ **Phase: Investigate fix_markdown_lint MCP Tool Failure** - COMPLETE (2026-02-17) - Root cause: second long-running tool (e.g. fix_markdown_lint) was failing immediately when invoked while execute_pre_commit_checks was still running. Fix: added LONG_RUNNING_SEMAPHORE_WAIT_SECONDS (90s) so the second call waits for the first to finish instead of raising immediately; commit pipeline can now proceed when sequential calls arrive. Tests and troubleshooting docs updated.

- ✅ **Session Optimization: Analysis-Only Context and Rules Indexing** - COMPLETE (2026-02-17) - Documented analysis-only no_data in Analyze prompt and troubleshooting; added rules indexing fallback (Synapse/AGENTS) in troubleshooting; verified manage_file full-file read (no bug). Fixed pre-existing type-check errors in test_mcp_stability_timeouts.py so quality gate passes.

- ✅ **Phase: Investigate execute_pre_commit_checks MCP Tool Failure** - COMPLETE (2026-02-17) - Root cause: long-running semaphore wait (90s) was shorter than execute_pre_commit_checks default test_timeout (300s), so a second call failed with RuntimeError before the first finished. Fix: increased LONG_RUNNING_SEMAPHORE_WAIT_SECONDS to 330s so sequential commit-pipeline calls succeed. Updated error message and troubleshooting docs; added invariant test.

- ✅ **Phase 56 Step 1: Design Compaction Strategy** - COMPLETE (2026-02-17) - Defined compaction rules for activeContext.md and progress.md, designed SessionHandoff JSON format, implemented Pydantic model, and added comprehensive unit tests (92.3% coverage). Design decision: summarize older entries in-place rather than archiving to progress.md.

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

Commit pipeline; no active feature focus.

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
