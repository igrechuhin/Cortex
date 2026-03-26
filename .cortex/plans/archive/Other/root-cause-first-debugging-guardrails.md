# Plan: Root-Cause-First Debugging Guardrails

**Slug**: root-cause-first-debugging-guardrails
**Component**: pipelines
**Work type**: improvement
**Priority**: high
**Status**: PENDING
**Created**: 2026-03-26

---

## Goal

Eliminate "wrong approach" friction (18 incidents in analysis period) by enforcing root-cause analysis before any fix attempt in `fix.md` prompt and fix pipeline.

## Context

Usage analytics show 18/33 sessions had wrong-approach friction. Claude repeatedly jumped to quick fixes before understanding root causes — in MCP disconnections, pipeline failures, import issues. The `fix.md` prompt lacks a mandatory diagnostic gate.

## Implementation Steps

1. Read current `fix.md` prompt at `.cortex/synapse/prompts/fix.md`
2. Add a mandatory PHASE 0 "Diagnose First" gate before any code changes:
   - List top 3 root-cause hypotheses with codebase evidence
   - Select one hypothesis with reasoning
   - Gate: no file edits until hypothesis is documented
3. Add "HARD GATE" block at top of fix.md matching the pattern in create-plan.md
4. Add diagnostic checklist: identify affected files, trace call stack, check for related issues
5. Run `run_quality_gate()` after changes

## Verification

- fix.md has explicit Phase 0 with STOP gate
- Hypothesis template is present
- Hard gate text matches create-plan.md pattern

## Testing

- Verify prompt structure renders correctly
- Test that fix workflow guides diagnostic-first approach
