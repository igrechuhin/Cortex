# Roadmap: MCP Memory Bank

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **Merge analyze* prompts into single end-of-session analyze (Blocker)** - COMPLETE (2026-02-02) - Unified end-of-session analyze prompt created; manifest and SYNAPSE_PROMPT_ICONS updated; old prompts archived to .cortex/synapse/prompts/archive/ with deprecation note; integration tests assert on unified analyze prompt; README updated. Plan: .cortex/plans/archive/Blocker/phase-merge-analyze-prompts-blocker.md.

- **Fix commit workflow: re-run Step 12.3 after code fixes in Step 12** - COMPLETE (2026-02-02) - Commit prompt now requires re-run of Step 12.3 (quality) after any code change in 12.2 or 12.3; CRITICAL RULE and 12.1/12.2/12.3 bullets updated; reminder that type/lint fixes can introduce new lint (e.g. E402); Step 13 precondition item 5 added; integration test test_commit_prompt_requires_rerun_step_12_3_after_fix_in_step_12_2_or_12_3. Plan: .cortex/plans/archive/SessionOptimization/fix-commit-workflow-rerun-12.3-after-fix.md.

- **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02) - Implemented all recommendations from .cortex/reviews/session-optimization-2026-02-02T10-04.md. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-rules-and-fallback-2026-02-02.md.

- **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01). Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-connection-closed-handling.md.

- **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02). Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-require-script-analysis.md.

## Current Status (2026-02-02)

### Active Work

(Active Work and Future Enhancements and Pending plans sections truncated for MCP write – see .cortex/memory-bank/roadmap.md for full content.)

- **Wire optimization.json to runtime behavior** - PENDING - Wire or remove unused optimization.json properties per .cortex/reviews/optimization-config-investigation-2026-02-03T19-13.md. Plan: .cortex/plans/wire-optimization-config-to-runtime.md.
