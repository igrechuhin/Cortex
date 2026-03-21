# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

- **PENDING** — [Targeted exception narrowing in validation and config paths](../plans/exception-narrowing-targeted.md) — Replace `except Exception` with specific types in 5 highest-impact locations (validation_config, completion_io, container). Priority: Medium.
- **PENDING** — [Replace sync file I/O with async in pipeline_handoff](../plans/async-io-pipeline-handoff.md) — Wrap `write_text`/`read_text` in `asyncio.to_thread()` to prevent event-loop blocking. Priority: Medium.

### Documentation Cleanup (DRY)

- **PENDING** — [Align docs/index.md with canonical 10-tool inventory](../plans/docs-surface-alignment.md) — Remove stale "70+ MCP tools" claim and align all top-level docs with the published surface. Priority: High.
- **PENDING** — [Clarify file/function size governance: document logical-line counting](../plans/file-size-governance-clarity.md) — Document that enforcement uses logical lines (excluding blanks, comments, docstrings) to eliminate confusion. Priority: High.

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements

- **PENDING** — [Add CI markdown link validation for non-archive docs](../plans/ci-markdown-link-validation.md) — Automated validation that internal markdown links resolve to existing files. Priority: Medium.
- **PENDING** — [Tighten tool-count guardrail from MAX=16 to MAX=12](../plans/tool-budget-tightening.md) — Reduce headroom from 60% to 20% above target; require explicit ADR to raise. Priority: Medium.
- **PENDING** — [Improve submodule preflight resilience and error messaging](../plans/submodule-resilience.md) — Auto-init in bootstrap, interactive prompt in check_synapse, remediation in quality gate output. Priority: Medium.
