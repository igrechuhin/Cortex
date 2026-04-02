# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Feedback Loop: Pipe Quality Gate Errors Back into Agent Context** - PENDING - Auto-write GateFeedback to pipeline_handoff on failure; /cortex/do reads it at next step start. Plan: .cortex/plans/feedback-loop-error-context.md
- **Structured Agent-Oriented Logging for Cortex MCP Tools** - PENDING - Add structured LogEvent logging to MCP tools so agents trace requirement→code→runtime behavior. Plan: .cortex/plans/structured-agent-logging.md
- **Reflection Quality Pass — Self-Evaluation Step in Cortex Pipelines** - PENDING - Optional reflection/critic pass after quality gate to catch semantic issues the gate misses. Plan: .cortex/plans/reflection-quality-pass.md
- **AI Code Comments and BELIEF Annotations Support in Cortex Rules** - PENDING - Surface # AI: comment and BELIEF declaration conventions as a Cortex rule with gate warnings. Plan: .cortex/plans/ai-code-comments-belief-annotations.md

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
