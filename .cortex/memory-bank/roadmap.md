# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### FastMCP v3 Migration

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

- Plan: [Fix: Add Missing Makefile Offline Targets](../plans/archive/Other/fix-makefile-offline-targets.md)
- **Harden Fix Workflow for Coverage-Only Failures** - PENDING - Production-hardening plan to enforce coverage-only failure handling in /cortex/fix with regression evals, coverage-attempt evidence contracts, and bounded blocker classification. Plan: .cortex/plans/harden-fix-workflow-for-coverage-only-failures.md
- **Enforce Post-Implementation Review Loop in /do Pipeline** - PENDING - Add mandatory post-completion review in /cortex/do; if review finds gaps, record them in the plan and return status to PENDING. Plan: .cortex/plans/enforce-post-implementation-review-loop-in-do-pipeline.md

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
