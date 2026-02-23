# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- Tools set optimization (deprecate/merge/remove poor performers) - PENDING - Execute deprecate/merge/remove for low-usage tools per mapping. Plan: .cortex/plans/plan-tools-set-optimization-deprecate-merge-remove.md
- **E2E Plan Test** - PENDING - Plan: .cortex/plans/e2e-plan-test.md

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Session Optimization Plans (2026-02-03)

### Session Optimization Plans (2026-02-02)

### Session Optimization Plans (2026-02-01)

### Features & Enhancements

- **Pending: Evaluation framework maturation (P1)** - Plan: .cortex/plans/plan-evaluation-framework-maturation.md
- **Pending: Anthropic context engineering alignment (P1)** - Plan: .cortex/plans/plan-anthropic-context-engineering-alignment.md
- **Pending: Agent skills and composability (P2)** - Plan: .cortex/plans/plan-agent-skills-and-composability.md
- **Pending: Security and resilience (P2)** - Plan: .cortex/plans/plan-security-and-resilience.md
- **Pending: Compound engineering alignment** - Plan: .cortex/plans/compound-engineering-alignment-cortex.md
- **Pending: Phase 58 multi-agent specialization** - Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md
- **Pending: Phase 9 excellence** - Plan: .cortex/plans/phase-9-excellence-98.md
- **Optimize MCP tools based on usage data** - PENDING - Reduce tool set using query_usage data; deprecate or consolidate tools below usage threshold. Plan: .cortex/plans/plan-optimize-tools-from-usage.md
