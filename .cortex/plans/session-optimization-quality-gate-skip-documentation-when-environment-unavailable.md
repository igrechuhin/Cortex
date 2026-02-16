# Session Optimization: Quality Gate Skip Documentation When Environment Unavailable

**Status:** PENDING
**Created:** 2026-02-13
**Source:** End-of-session analysis 2026-02-13 (session-optimization-2026-02-13T19-33.md)

## Goal

Document when and how to treat the implement-step quality gate as "skipped" when `execute_pre_commit_checks` fails due to environment issues (e.g. ruff/black not in path, type_check download/certificate failure) and the change set is documentation-only, so agents and users are not blocked and commit-pipeline expectations are clear.

## Context

During Phase 50 Step 5 (documentation-only updates), the mandatory quality gate (`execute_pre_commit_checks(checks=["quality"])`) could not be run: ruff/black were not found at the expected .venv paths, and type_check failed due to network/certificate when downloading the Python build. No code was changed; only docs and AGENTS.md were updated. The implement prompt requires the quality gate to pass before memory bank updates; without documentation, doc-only sessions in constrained environments are left in a gray area (skip vs block).

## Approach

1. Add a short subsection to the implement prompt (Step 4.7 or ERROR HANDLING) and/or to docs/guides/troubleshooting.md describing when the quality gate can be considered "skipped - environment" (documentation-only changes + execute_pre_commit_checks failing due to missing tools or type_check download/certificate).
2. Clarify that the commit pipeline should still run the full quality gate in an environment where ruff/black and type_check are available, so this is a session-time relaxation only for doc-only work.

## Implementation Steps

1. **Implement prompt**: In Step 4.7 (or adjacent), add a bullet or short paragraph: when the change set is documentation-only (no changes under `src/` or `tests/` that affect code behavior) and `execute_pre_commit_checks` fails due to "ruff/black not found" or "type_check download/certificate" (or similar environment failure), the step may be considered satisfied with a note that "Quality gate skipped - environment (doc-only session); run full pre-commit before commit."
2. **Troubleshooting (optional)**: In docs/guides/troubleshooting.md, add a small "Quality gate unavailable in environment" entry: symptoms (ruff/black not found, type_check download error), cause (venv not activated, network/certificate), and recommendation (for doc-only changes, proceed and run full pipeline before commit; for code changes, fix environment first).
3. **AGENTS.md (optional)**: One-line note under Commit pipeline that doc-only sessions may skip quality gate when tooling unavailable, with "run pre-commit before commit" reminder.

## Dependencies

- None.

## Success Criteria

- Implement prompt clearly states when quality gate can be skipped (doc-only + environment failure only).
- No change to behavior when environment is healthy; commit pipeline still requires full checks.
- Troubleshooting and/or AGENTS updated if scope permits.

## Testing Strategy

- **Coverage:** N/A (documentation and prompt text only).
- **Validation:** Manual review that wording does not allow skipping when code is changed or when failure is due to actual lint/type errors.
- **Integration:** Confirm implement prompt and docs are consistent.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Agents skip gate when they should not | Wording limited to "documentation-only" and "environment failure"; require note so commit pipeline still runs. |
| Confusion with fix_quality_issues connection-closed handling | Keep separate: this is "tools not installed / type_check unavailable"; connection-closed is already documented. |

## Notes

- Aligns with existing implement prompt "Connection closed during fix_quality_issues" special case: both are environment/session limitations, not server bugs.
- Report location: `.cortex/reviews/session-optimization-2026-02-13T19-33.md`
