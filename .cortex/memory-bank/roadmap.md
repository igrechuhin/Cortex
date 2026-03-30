# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **[QG-S4] Swift check_file_sizes FILES env** - PENDING - Accept FILES env var; include Tests/ in fallback scan. Plan: `.cortex/plans/swift-qg-s4-swift-check-file-sizes.plan.md`
- **[QG-S5] Swift check_function_lengths FILES env** - PENDING - Accept FILES env var; include Tests/ in fallback scan. Plan: `.cortex/plans/swift-qg-s5-swift-check-function-lengths.plan.md`
- **[QG-S6] python synapse scripts FILES env** - PENDING - Add FILES env var interface to both python scripts for interface parity. Plan: `.cortex/plans/swift-qg-s6-python-scripts-files-env.plan.md`
- **[QG-S7] Unit tests for file_language_router** - PENDING - Full unit test suite: routing, collection, parsers, mocked dispatch, execute_quality regression. Plan: `.cortex/plans/swift-qg-s7-unit-tests.plan.md`
- **[QG-S8] Integration tests + validation** - PENDING - Real synapse script invocations via FILES env; TradeWing scenario; full suite regression check. Plan: `.cortex/plans/swift-qg-s8-integration-tests.plan.md`

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PENDING - Optional TradeWing template reconciliation and further language packs; tracks remaining work reflected in progress PARTIAL entries.

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

### Features & Enhancements
