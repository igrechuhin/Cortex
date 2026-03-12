# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](../memory-bank/activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Documentation Cleanup (DRY)

- **[HI-6] Resolve Type-Checker Strategy** — PARTIAL / IN PROGRESS: Pyright is documented and configured as the primary type checker (CI + local), with mypy retained as an optional/local-only cross-check. `pyproject.toml`, `pyrightconfig.json`, contributor docs, `.cortex` memory-bank entries (including `techContext.md` and this roadmap entry), and the dedicated HI-6 plan are all aligned to say "Pyright primary, optional/local mypy." Only the Phase A quality-gate/CI validation slice remains before HI-6 can be closed. Plan: `plans/resolve-type-checker-strategy.md` | Priority: High | Order: 11
- **[MED-7] Fix README Tool Count** — Update "27 public MCP tools" to actual count. Plan: `plans/fix-readme-tool-count.md` | Priority: Medium | Order: 19
- **[MED-3] Calibrate Review Metric Scores** — Add calibration examples and evidence requirements for 9 review metrics. Plan: `plans/calibrate-review-metric-scores.md` | Priority: Medium | Order: 15
- **[MED-10] Make Prompts Agent-Agnostic** — Replace Cursor-specific tool names with generic mapping. Plan: `plans/make-prompts-agent-agnostic.md` | Priority: Medium | Order: 22

### Refactoring

- **[MED-8] Reduce Prompt-Alignment Test Fragility** — Refactor substring assertions to semantic checks. MUST complete before HI-1. Plan: `plans/reduce-prompt-alignment-test-fragility.md` | Priority: Medium | Order: 20
- **[HI-4] Consolidate Roadmap Sync Models** — Remove legacy duplicates in `src/cortex/validation/roadmap_models.py`. Plan: `plans/consolidate-roadmap-sync-models.md` | Priority: High | Order: 9
- **[HI-7] Reduce Redundant Pipeline Checks** — Dirty-state tracking to skip clean checks in final validation. Depends: CRI-3, HI-1. Plan: `plans/reduce-redundant-pipeline-checks.md` | Priority: High | Order: 12
- **[MED-9] Reduce Oversized Modules** — Split top 5 files (>550 lines) to comply with 400-line limit. Plan: `plans/reduce-oversized-modules.md` | Priority: Medium | Order: 21

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](../memory-bank/activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements

- **[HI-2] Structured Quality Config** — Add structured quality config (JSON under `.cortex/config/`) replacing markdown-parsed thresholds. Plan: `plans/add-structured-quality-config.md` | Priority: High | Order: 7
