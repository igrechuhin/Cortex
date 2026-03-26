# Plan: Pipeline Code Integrity Guard — Prevent Fix-Loop Corruption

**Slug**: pipeline-code-integrity-guard
**Component**: pipelines
**Work type**: improvement
**Priority**: high
**Status**: PENDING
**Created**: 2026-03-26

---

## Goal

Prevent fix pipelines from introducing duplicate definitions, circular imports, and TYPE_CHECKING violations — the root cause of multi-session cascading repair loops.

## Context

Multiple sessions had fix pipeline corruption: duplicate definitions, circular import workarounds with TYPE_CHECKING (banned in project standards), and syntax errors. The `fix.md` and automated fix flow need explicit anti-corruption checks.

## Implementation Steps

1. Read `fix.md` at `.cortex/synapse/prompts/fix.md`
2. Add explicit "NO-GO" list to fix.md:
   - NEVER add duplicate function/class definitions
   - NEVER use `TYPE_CHECKING` imports (project standard violation)
   - NEVER introduce circular imports (extract to new module instead)
   - NEVER add syntax that isn't valid Python
3. Add a post-fix validation step in fix.md: run `python -c "import {module}"` for changed modules before calling success
4. Add rollback instruction: if fix introduces new test failures, revert and try different approach (max 3 attempts)
5. Update `fix_quality_issues` documentation to warn about corruption risks

## Verification

- fix.md has NO-GO list
- Post-fix module import check is present
- Rollback on new failures is documented

## Testing

- Verify NO-GO items are prominent and early in the prompt
- Check rollback logic is actionable
