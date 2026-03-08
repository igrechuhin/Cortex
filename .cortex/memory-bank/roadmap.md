# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

- **[CRI-1] Fix TODO Scanner Exclusion Patterns** — Replace substring matching with path-segment-aware patterns to prevent false negatives on production files. Plan: `plans/fix-todo-scanner-exclusion-patterns.md` | Priority: Critical | Order: 1
- **[CRI-3] Add MCP Circuit-Breaker Pattern** — Standardize circuit-breaker for consecutive MCP failures with clean abort and resume. Plan: `plans/add-mcp-circuit-breaker-pattern.md` | Priority: Critical | Order: 3
- **[CRI-4] Add Commit Pipeline Rollback** — Pre-pipeline state snapshot and rollback offer on failure. Depends: CRI-3. Plan: `plans/add-commit-pipeline-rollback.md` | Priority: Critical | Order: 4
- **[CRI-5] Add Plan YAML Frontmatter Schema** — Deterministic plan similarity scoring via enforced frontmatter. Plan: `plans/add-plan-frontmatter-schema.md` | Priority: Critical | Order: 5
- **[HI-3] Persist Pipeline State Decisions** — Checkpoint similarity_decision, primary_language to survive context compression. Depends: CRI-3. Plan: `plans/persist-pipeline-state-decisions.md` | Priority: High | Order: 8
- **[HI-5] Fix Roadmap Logging Leakage** — Replace content previews with metadata in ghost-section logs. Plan: `plans/fix-roadmap-logging-leakage.md` | Priority: High | Order: 10
- **[MED-2] Fix Loop Convergence Detection** — Abort oscillating fix loops early when violation count not decreasing. Plan: `plans/add-fix-loop-convergence-detection.md` | Priority: Medium | Order: 14
- **[MED-4] Extend Pre-Flight Directory Validation** — Auto-create missing operational directories (plans/, reviews/, .session/). Plan: `plans/extend-preflight-directory-validation.md` | Priority: Medium | Order: 16
- **[MED-5] Atomic Memory Bank Writes** — Temp file + rename pattern for manage_file writes. Plan: `plans/add-atomic-memory-bank-writes.md` | Priority: Medium | Order: 17
- **[MED-6] Schema-Define Roadmap Section Names** — Replace hardcoded strings with constants; auto-create missing sections. Plan: `plans/schema-define-roadmap-sections.md` | Priority: Medium | Order: 18
- **[MED-1] Agent Handoff Output Validation** — Validate agent results against schema before checkpointing. Plan: `plans/add-agent-handoff-validation.md` | Priority: Medium | Order: 13

### Documentation Cleanup (DRY)

- **[CRI-2] Fix Troubleshooting Docs Contradiction** — Resolve contradictory coverage config statements. Plan: `plans/fix-troubleshooting-docs-contradiction.md` | Priority: Critical | Order: 2
- **[HI-6] Resolve Type-Checker Strategy** — Document mypy vs pyright decision; remove stale config. Plan: `plans/resolve-type-checker-strategy.md` | Priority: High | Order: 11
- **[MED-7] Fix README Tool Count** — Update "27 public MCP tools" to actual count. Plan: `plans/fix-readme-tool-count.md` | Priority: Medium | Order: 19
- **[MED-3] Calibrate Review Metric Scores** — Add calibration examples and evidence requirements for 9 review metrics. Plan: `plans/calibrate-review-metric-scores.md` | Priority: Medium | Order: 15
- **[MED-10] Make Prompts Agent-Agnostic** — Replace Cursor-specific tool names with generic mapping. Plan: `plans/make-prompts-agent-agnostic.md` | Priority: Medium | Order: 22

### Refactoring

- **[MED-8] Reduce Prompt-Alignment Test Fragility** — Refactor substring assertions to semantic checks. MUST complete before HI-1. Plan: `plans/reduce-prompt-alignment-test-fragility.md` | Priority: Medium | Order: 20
- **[HI-1] Simplify Commit Pipeline Structure** — Collapse 15+ steps to 3 macro-phases with tabular sub-steps. Depends: MED-8, CRI-3, CRI-4. Plan: `plans/simplify-commit-pipeline-structure.md` | Priority: High | Order: 6
- **[HI-4] Consolidate Roadmap Sync Models** — Remove legacy duplicates in `src/cortex/validation/roadmap_models.py`. Plan: `plans/consolidate-roadmap-sync-models.md` | Priority: High | Order: 9
- **[HI-7] Reduce Redundant Pipeline Checks** — Dirty-state tracking to skip clean checks in final validation. Depends: CRI-3, HI-1. Plan: `plans/reduce-redundant-pipeline-checks.md` | Priority: High | Order: 12
- **[MED-9] Reduce Oversized Modules** — Split top 5 files (>550 lines) to comply with 400-line limit. Plan: `plans/reduce-oversized-modules.md` | Priority: Medium | Order: 21

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements

- **[HI-2] Structured Quality Config** — Add structured quality config (JSON under `.cortex/config/`) replacing markdown-parsed thresholds. Plan: `plans/add-structured-quality-config.md` | Priority: High | Order: 7
