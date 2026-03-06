# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-06)

- ✅ **Phase 92: Improve MCP Tool Descriptions and Usage Guidance** - COMPLETE (2026-03-06) - Updated high-impact MCP tool descriptions with a consistent USE WHEN / DO NOT / EXAMPLES template, and added governance coverage so tools steer agents toward canonical entrypoints (memory bank, pre-commit, structure, usage). Verified quality gate, type checks, and full tests (4910/4910) with ~92.41% coverage.
- ✅ **README selling doc refresh** - COMPLETE (2026-03-06) - Rewrote the README to lead with value and a clear plan → implement → commit workflow, trimmed long reference sections, and kept links to the authoritative docs.

- ✅ **Phase 84: Remaining Type-Checker Suppression Cleanup** - COMPLETE (2026-03-06) - Eliminated remaining type-checker suppressions in core MCP usage-context wrapper and session/usage Pydantic models by introducing safer typing and typed default factories; pyright now passes in src without ignores.

- ✅ **Phase 90: Agent Session Verbosity and "ok, proceed" Pattern** - COMPLETE (2026-03-06) - Tightened execution-continuity guidance so agents auto-continue instead of waiting for "ok, proceed", and updated Synapse prompts plus AGENTS/CLAUDE to distinguish valid vs invalid stops.

- ✅ **Commit pipeline (2026-03-06)** - COMPLETE (2026-03-06) - Ran /cortex/commit: Phase A preflight (fix_errors, format, synapse_format, synapse_lint, type_check, tests, eval_fast, markdown_lint) all passed with 4910 tests and ~92.41% coverage; proceeding to memory bank/roadmap + docs phases.

- ✅ **Phase 85: Unify Developer Command Surface** - COMPLETE (2026-03-06) - Unified the developer command surface by documenting canonical Make targets, adding a commit-check alias, and introducing a docs consistency test for README and AGENTS uv sync usage.

- ✅ **Phase 81: Oversized Module Reduction — Wave 1 (Top 10) — Step 1 core/security split** - COMPLETE (2026-03-06) - Split legacy `cortex.core.security` (732 LOC) into focused `git_security.py`, `html_security.py`, and `input_validation.py` modules with a slim `security.py` aggregator re-exporting public helpers; verified format, type_check, quality, and full tests (4913 tests, 92.42% coverage).

- ✅ **Phase 81 Step 2: validation/models.py split** - COMPLETE (2026-03-06) - Split cortex.validation.models into domain modules (schema_models, quality_models, roadmap_models, infrastructure_models, timestamp_models) with slim models.py re-exports; fixed pre_commit_tools function-length violations; quality gate and tests passed.

- ✅ **Phase 93: Usage Events Collection Pipeline Investigation** - COMPLETE (2026-03-06) - Default usage_writable to True when .cortex/synapse exists and config.json is missing so usage events are written to .cortex/synapse/.cache/usage/events without requiring a config file. Added regression test.

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

Commit pipeline; no active feature focus.

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
