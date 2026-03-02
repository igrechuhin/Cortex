# Plan: Consolidate execute_pre_commit_checks + fix_quality_issues

**Status**: PENDING
**Priority**: P1 (high)
**Estimated Effort**: 4–6 hours

## Goal

Reduce Cortex MCP tool count by folding `fix_quality_issues` into `execute_pre_commit_checks` as a new operation/mode, then deprecating `fix_quality_issues`. One canonical quality/check/fix tool.

## Context

Both tools cover the same quality surface (format, lint, markdown, type checks). `execute_pre_commit_checks` runs checks and can fix (Phase A includes fix_errors, format). `fix_quality_issues` runs format fix, lint fix, markdown fix, and reports type errors—all without running tests. Consolidation adds a fix-only mode to the canonical quality gate.

**Reference**: [docs/guides/tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md) — target ≥ 4.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 6).

### Step 1: Add fix_quality mode to execute_pre_commit_checks

- Add `checks=["fix_quality"]` (or `phase="fix_only"`) to `execute_pre_commit_checks` that runs the same logic as `fix_quality_issues`: format fix, lint fix, markdown fix, type check (report only).
- Do NOT run tests in this mode.
- Parameters: `include_untracked_markdown` (default True) for markdown scope.
- Return format: match `fix_quality_issues` response shape (status, *_fixed counts, files_modified, remaining_issues, type_check_errors).

### Step 2: Update run_composite_workflow quality_check operation

- Change `run_composite_workflow(operation="quality_check")` to call `execute_pre_commit_checks(checks=["fix_quality"])` instead of invoking `fix_quality_issues`.
- Verify composite workflow tests pass.

### Step 3: Update commit and fix-quality prompts

- Update commit pipeline, fix-quality command, and any Synapse agents that call `fix_quality_issues` to use `execute_pre_commit_checks(checks=["fix_quality"])`.
- Update AGENTS.md, CLAUDE.md, and docs that reference fix_quality_issues.

### Step 4: Deprecate fix_quality_issues

- Add deprecation warning to `fix_quality_issues` implementation: suggest `execute_pre_commit_checks(checks=["fix_quality"])`.
- Remove `fix_quality_issues` from tool registration (or keep as thin shim that delegates).
- Remove from `tool_categories.py` and TOOL_CATEGORIES.

### Step 5: Update tool documentation

- Update `execute_pre_commit_checks` docstring per tool-description-altitude-rubric (USE WHEN, EXAMPLES for fix_quality).
- Ensure docs/api/tools.md reflects the new checks option.

### Step 6: Verification

- Run full pre-commit suite; ensure fix-only path works.
- Verify `/cortex/fix-quality` (or equivalent) uses consolidated tool.
- Confirm tool count reduced by 1.

## Testing Strategy

- **Coverage target**: ≥ 95% for new/modified code.
- **Unit tests**: Test `execute_pre_commit_checks` with `checks=["fix_quality"]` — verify it invokes format, lint, markdown fix, type check; verify response shape.
- **Integration tests**: Test `run_composite_workflow(operation="quality_check")` still produces expected results.
- **Regression**: Existing `execute_pre_commit_checks` tests (phase A/B, individual checks) must remain passing.
- **AAA pattern**: All tests follow Arrange-Act-Assert.

## Dependencies

- None.

## Success Criteria

- `fix_quality_issues` is no longer a registered MCP tool (or is a deprecation shim).
- `execute_pre_commit_checks(checks=["fix_quality"])` provides equivalent behavior.
- All callers migrated.
- Tool count reduced by 1.
- Pre-commit and fix-quality workflows pass.

## Risks & Mitigation

- **Risk**: Breaking fix-quality workflows. **Mitigation**: Keep `fix_quality_issues` as thin shim during transition; remove only after all callers migrated and tests pass.
