<!-- memory_type: milestone -->
# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

- **Project Access bootstrap and owned quality runs** - BLOCKED - BLOCKED: 121/124 selected tests passed; three synthetic lifetime cases denied with errno1; later uncertainty fixes and14 mocked cases await behavioral verification. Plan: .cortex/plans/project-access-bootstrap-owned-quality-runs.md

## Future Enhancements

- **TradeWing scoped data root and reader adapters** - PENDING - Design explicit approved data-root and existing-reader adapters; verify chat binding and synthetic smoke tests before owner-authorized activation. Plan: .cortex/plans/tradewing-scoped-data-root-adapters.md

## Pending plans (from .cortex/plans)

- **Report timings from quality logs** - PENDING - Read-only report from Cortex event logs and Swift test output. Plan: .cortex/plans/report-timings-from-quality-logs.md
- **Recover completed quality receipts after MCP reconnect** - PENDING - Recover a verified full quality result for the same adopted commit pipeline after MCP reconnect. Plan: .cortex/plans/recover-completed-quality-receipts-after-mcp-reconnect.md

### Pipeline Infrastructure

### Tools Infrastructure

### FastMCP v3 Migration

### Fixes

### Quality & Reliability Improvements

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

#### Annotation Quality (Medium Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
