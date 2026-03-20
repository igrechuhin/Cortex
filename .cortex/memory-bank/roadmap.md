# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Split make quality flows into non-mutating check and fix modes** - PENDING - Plan: `.cortex/plans/split-make-quality-flows-into-non-mutating-check-and-fix-modes.md` - Refactor Makefile targets into clear check/fix modes and add CI-parity local target.
- **Document MCP-unavailable fallback for read-only audits** - PENDING - Plan: `.cortex/plans/document-mcp-unavailable-fallback-for-read-only-audits.md` - Define audited read-only fallback behavior and connectivity remediation when MCP is unavailable.
- **Block dirty submodule references in commit workflow** - PENDING - Plan: `.cortex/plans/block-dirty-submodule-references-in-commit-workflow.md` - Add commit/quality guard that blocks dirty submodule references and gives remediation.
- **Harden session telemetry against synthetic data pollution** - PENDING - Plan: `.cortex/plans/harden-session-telemetry-against-synthetic-data-pollution.md` - Filter synthetic telemetry and validate record quality to preserve accurate optimization signals.

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
