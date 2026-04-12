# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

- **README Tool Inventory Parity Fix** — Align README "Key Tools" table with canonical 12-tool inventory; add CI parity test. Plan: `.cortex/plans/readme-tool-inventory-parity.md`

### Quality & Reliability Improvements

- **Type Policy Hardening: Remove Any from Production Code** — Remove `typing.Any` from `src/cortex/tools/execution/pre_commit_status.py`; add ruff/pyright guard to prevent re-entry. Plan: `.cortex/plans/type-policy-hardening-any-removal.md`

- **Deprecation Completion: Legacy Quality Entrypoints Migration** — PENDING — Migration matrix and sunset schedule for `execute_pre_commit_checks`, `start_quality_job`, `get_quality_job_status`; ≥50% reference reduction in one release. Plan: `.cortex/plans/deprecation-legacy-quality-entrypoints.md` (matrix: `.cortex/plans/deprecation-legacy-quality-entrypoints-migration-matrix.md`).

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
