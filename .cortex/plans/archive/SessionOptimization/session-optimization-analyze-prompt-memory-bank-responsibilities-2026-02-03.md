# Session Optimization: Analyze Prompt and Memory Bank Responsibilities (2026-02-03)

## Status

Status: COMPLETE

## Source

Created from end-of-session analysis: `.cortex/reviews/session-optimization-2026-02-03T20-27.md`.

## Goal

Align the Analyze prompt Pre-Analysis Checklist with memory bank file responsibilities (activeContext = completed work only; roadmap = current status and upcoming work). Optionally migrate in-progress/Next Focus content from activeContext to roadmap.

## Context

- Memory bank responsibilities are now documented: activeContext.md = completed work only; roadmap.md = future/upcoming work only; when work is done, move from roadmap to activeContext (AGENTS.md, CLAUDE.md, maintainability.mdc, memory-bank-workflow.mdc, memory-bank-updater, docs).
- The Analyze prompt (`.cortex/synapse/prompts/analyze.md`) Pre-Analysis Checklist still says "`activeContext.md` – current work focus", which does not match the new contract.

## Implementation Steps

1. **Update Analyze prompt Pre-Analysis Checklist**
   - In `.cortex/synapse/prompts/analyze.md`, under "Read relevant memory bank files", update the bullet for activeContext.md to: "`activeContext.md` – completed work only (for current status and upcoming work see roadmap.md)".
   - Add an explicit bullet for roadmap.md: "`roadmap.md` – current status and upcoming work".
   - Ensure the checklist instructs analysts to read both so end-of-session analysis reflects completed work (activeContext) and current/upcoming (roadmap) without implying "current work focus" lives only in activeContext.

2. **Optional: Content migration**
   - In activeContext.md, move any "Active Work (in progress)" and "Next Focus" items into roadmap.md so that activeContext contains only completed-work summaries.
   - This is optional and can be done in a separate pass; the new headers and rules already state the contract.

## Success Criteria

- Analyze prompt Pre-Analysis Checklist describes activeContext as completed work and roadmap as current/upcoming work.
- No duplicate entries between activeContext and roadmap when optional migration is performed.

## Dependencies

- Session analysis: .cortex/reviews/session-optimization-2026-02-03T20-27.md.
- Memory bank responsibilities (AGENTS.md, CLAUDE.md, maintainability.mdc, memory-bank-workflow.mdc) – already updated.
