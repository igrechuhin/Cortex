# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-11)

- **Job-based pre-commit pipeline + commit orchestration migration** - COMPLETE. Fixed two interlocking issues: (1) `commit.md` hybrid mess — rewritten to delegate all phases (Preflight/A/B/C/Step 12) to dedicated cursor-agents; (2) MCP `-32000` disconnects — `start_pre_commit_job(phase=...)` and `get_pre_commit_job_status` now used by `commit-checks.md` and `commit-final-gate.md` instead of blocking `execute_pre_commit_checks`. Added `phase_to_checks()` helper to `pre_commit_phase_dispatch.py`; extended `start_pre_commit_job` with `phase` parameter. Fixed `analyze()` validation error (`target` now defaults to `"context"`). 43/43 targeted tests pass.
- **Plan: make-pre-commit-checks-job-based-for-cursor-mcp** - COMPLETE. Archived.
- **Implement pipeline cursor-agent delegation** - COMPLETE. `implement-next-roadmap-step.md` rewritten as thin orchestrator. Created 4 new cursor-agents: `implement-select.md`, `implement-code.md`, `implement-finalize.md`, `implement-verify.md`. Auto-synced on MCP startup; `TestRequiredAgentFilesPresent` enforces presence of all 10 required agent files.
- **CI fix: npm cache** - COMPLETE. Removed `cache: "npm"` from `actions/setup-node@v4`; was causing all CI steps to be skipped when `package-lock.json` absent.
- **Pyright fixes: pre_commit_status.py** - COMPLETE. 14 errors fixed via `dict[str, object]` + `cast()` + helper extraction.
- **Synapse cursor-agents: project/language agnostic** - COMPLETE. Created `shared-defaults.md` for quality thresholds; removed hardcoded numbers from `implement-code.md`, `commit-checks.md`; made archive categories project-supplied via `get_structure_info()` in `commit-docs.md`, `implement-finalize.md`; removed Python-specific `rumdl` fallback from `commit.md`.
- ✅ **[HI-6] Resolve Type-Checker Strategy (PARTIAL)** - Pyright is primary type checker (configuration + contributor docs); mypy kept as explicitly-optional local check; remaining: run a Phase A quality gate/CI validation slice for the type-checker-strategy docs/config/memory-bank changes.

- ✅ **[HI-6] Resolve Type-Checker Strategy (PARTIAL – docs slice)** - COMPLETE (2026-03-11) - Aligned key public docs and extension development guide so they consistently state that Pyright is the primary type checker (CI + local) and mypy is optional/local-only, and recorded that this was a docs-only session where the quality gate was effectively skipped due to tooling limitations ("Quality gate skipped — doc-only session"); remaining HI-6 work is to run a Phase A quality gate/CI validation slice for the type-checker-strategy docs/config/memory-bank changes and confirm it passes.

- ✅ **[HI-6] Resolve Type-Checker Strategy (2026-03-11)** - COMPLETE (2026-03-11) - Ran the job-based Phase A preflight quality gate via Cortex MCP (phase "A") to validate that Pyright-based type checking, tests, coverage, and other quality checks all pass with the current Pyright-first configuration. This confirms that Pyright is the enforced primary type checker for Phase A and CI while mypy remains an optional/local cross-check, allowing HI-6 to be closed from the implementation side.

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

Roadmap item implementation batch complete; remaining items are documentation cleanup (MED-7, MED-3, MED-10), refactoring (MED-8, HI-1, HI-4, HI-7, MED-9), and features (HI-2).

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
