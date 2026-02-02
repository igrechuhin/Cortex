# Session Optimization (2026-02-02 16-37): Plan Status MD036 and Side-Effect Imports

Status: PENDING  
**Created**: 2026-02-02  
**Priority**: High  
**Source**: .cortex/reviews/session-optimization-2026-02-02T16-37.md

## Overview

Implement the three recommendations from the session optimization analysis (2026-02-02T16-37) to prevent (1) markdown lint MD036 in plan Status sections and (2) Pyright reportUnusedImport in tests that use side-effect-only imports. Reduces Step 12.0 and Step 12.2 failures during commit.

## Goal

- Add Synapse rule/prompt guidance so new plans use a Status format that passes MD036 and new tests that use side-effect imports satisfy Pyright.
- Add commit-prompt reminders so agents check these patterns before Step 12.

## Context

The analysis identified two mistake patterns from a commit run:

1. **Plan Status and MD036**: Plan files using `**PENDING**` or `**COMPLETE**` alone in a Status section trigger markdownlint MD036 (emphasis used instead of heading). Fix used: `Status: PENDING` (plain text).
2. **Side-effect imports**: Integration tests that `import cortex.main` only for registration trigger Pyright reportUnusedImport. Fix used: `_ = cortex.main`.

Root causes: no explicit rule for plan Status format (MD036), and no rule for satisfying reportUnusedImport when imports are side-effect only.

## Approach

Update Synapse rules and the commit prompt only; no production code changes. Verification via existing markdown lint and type check; optional integration test that commit prompt contains the new reminders.

## Implementation Steps

1. **Add Plan Status format rule (Recommendation 1)**
   - Target: `.cortex/synapse/rules/markdown/markdown-formatting.mdc` (or plan-creator prompt / plan template docs if preferred).
   - Add a short rule or bullet: In plan files, the Status section must use plain text or a heading for the status value. Use `Status: PENDING` or `### PENDING`, not `**PENDING**` or other emphasis-only lines; emphasis used instead of a heading triggers MD036.
   - Optionally add example: good `Status: PENDING`, bad `**PENDING**`.

2. **Add side-effect imports rule (Recommendation 2)**
   - Target: `.cortex/synapse/rules/python/python-testing-standards.mdc` or `.cortex/synapse/rules/python/python-coding-standards.mdc`.
   - Add a short subsection (e.g. "Side-effect imports"): For imports used only for side effects (e.g. test setup or registration), reference the module so the type checker does not report it as unused. Prefer `_ = module` or a single use (e.g. `getattr(module, '__name__')`). Do not rely only on `# noqa: F401` when using Pyright; it does not suppress reportUnusedImport.
   - Include one good example.

3. **Add commit prompt reminders (Recommendation 3)**
   - Target: `.cortex/synapse/prompts/commit.md` — Pre-Action Checklist or "COMMON ERRORS TO CATCH BEFORE COMMIT."
   - Add one bullet: New or modified plan files: ensure Status section uses `Status: VALUE` or a heading, not **VALUE** alone (avoids MD036). New or modified tests with side-effect imports: ensure the import is referenced (e.g. `_ = module`) to satisfy reportUnusedImport.

## Dependencies

- None. Synapse rules and prompts are in the repo (or submodule); path resolution via `get_structure_info()`.

## Success Criteria

- Markdown-formatting (or plan) rule includes the Plan Status format rule and example.
- Python testing or coding standards include the side-effect imports rule and example.
- Commit prompt contains the two reminders in the chosen section.
- Existing markdown lint and type check still pass (no regressions).
- Optional: integration test asserts commit prompt contains the new reminder text.

## Testing Strategy

- **Rule/prompt edits**: No new production code; changes are to Synapse `.mdc` and `.md` files.
- **Verification**: Run `fix_markdown_lint(check_all_files=True)` and `execute_pre_commit_checks(checks=["type_check"])` after edits; confirm zero errors.
- **Optional**: Add or extend an integration test (e.g. in tests that assert commit prompt content) to check that the commit prompt contains the Plan Status and side-effect-import reminder strings.
- **Regression**: Full test suite and quality gate must still pass.

## Risks and Mitigation

- **Synapse as submodule**: If rules/prompts live in Synapse submodule, edits are in the submodule; parent repo tracks the new commit. Mitigation: follow existing SessionOptimization flow (edit in .cortex/synapse, commit in submodule, then parent).
- **Wording drift**: Keep rule and prompt text concise so it stays in sync with the review. Mitigation: copy exact sentences from the review where possible.

## Timeline

- Single session (1–2 hours): all three steps are small, localized edits.

## Notes

- Review file: `.cortex/reviews/session-optimization-2026-02-02T16-37.md`
- Plans directory path: resolve via `get_structure_info()` → `structure_info.paths.plans`
- This plan itself uses `Status: PENDING` (not **PENDING**) to comply with the recommended format.
