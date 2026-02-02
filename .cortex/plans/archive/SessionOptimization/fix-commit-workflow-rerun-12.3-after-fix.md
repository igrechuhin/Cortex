# Fix Commit Workflow: Re-run Step 12.3 After Code Fixes in Step 12

Status: COMPLETE  
**Created**: 2026-02-02  
**Completed**: 2026-02-02  
**Priority**: Blocker (ASAP)  
**Source**: CI Ruff failure (GitHub Actions run 21592220363) after local commit pipeline passed; investigation in session.

## Overview

Commit pipeline passed locally but the quality gate failed on CI with Ruff lint (E402: module level import not at top of file). Root cause: a type-check fix applied in Step 12.2 (adding `_ = cortex.main` to satisfy reportUnusedImport) introduced a new lint violation (E402) because the line was placed between imports. Step 12.3 (quality/lint) was either not re-run after the fix or its result was not enforced, so the violating code was committed and CI failed.

This plan hardens the commit workflow so that **after any code change in Step 12.2 or 12.3, Step 12.3 (quality) must be re-run and verified zero errors** before proceeding to Step 12.4 or Step 13. Prevents "local pass, CI fail" when type/lint fixes introduce new lint issues.

## Goal

- Ensure the commit prompt explicitly requires **re-running Step 12.3 (quality)** after any code fix in Step 12.2 (type) or Step 12.3 (lint).
- Add an explicit reminder that **type/lint fixes can introduce new lint issues** (e.g. E402 when adding `_ = module` between imports); re-run 12.3 and parse full output to verify zero errors.
- Prevent commits that pass local checks but fail CI on Ruff (or other quality checks) due to fixes applied in the Final Validation Gate without re-validating quality.

## Context

- **Observed failure**: CI step "Lint with ruff" failed: `ruff check src/ tests/` reported E402 in `tests/integration/test_prompt_icons.py` (import not at top of file). Local pipeline had passed.
- **Root cause**: During Step 12, a type error (reportUnusedImport) was fixed by adding `_ = cortex.main`. That line was inserted between `import cortex.main` and `from cortex.server import mcp`, which violated E402. Step 12.3 (quality) was not re-run after this fix—or was not enforced—so the new E402 was not caught before commit.
- **Correct fix** (applied post-CI): Move all imports to the top, then add `_ = cortex.main` after the last import so no import is "not at top."
- **Workflow gap**: The commit prompt says to re-run 12.1 after fixing type errors and then "continue to 12.3," but it does not state unambiguously that **12.3 must be executed again** (not skipped) and that **fixes in 12.2/12.3 can introduce new lint**; agents may skip re-running 12.3 or misread success.

## Approach

Update the commit prompt (`.cortex/synapse/prompts/commit.md`) only: add mandatory re-run and verification language for Step 12.3 after code changes in Step 12.2 or 12.3, and add an explicit anti-pattern reminder (type/lint fixes can introduce E402 or other lint). Optionally add a checklist item or CRITICAL RULE bullet. No production code or CI workflow changes required.

## Implementation Steps

1. **Clarify "re-run Step 12.3" after fixes in Step 12.2**
   - In the commit prompt, locate the text that describes re-running Step 12.1 after fixing type errors in 12.2 and "continuing to 12.3."
   - Make it explicit: **After any code change in Step 12.2 (type) or Step 12.3 (lint), you MUST re-run Step 12.1 (format fix and check), then MUST re-run Step 12.3 (quality) and verify `results.quality.success` is true and error count is zero. Do not proceed to Step 12.4 or Step 13 until Step 12.3 has been run again and passed.**
   - Ensure the wording prevents interpreting "continue to 12.3" as "proceed past 12.3" without actually executing the quality check again.

2. **Add explicit reminder: fixes in 12.2/12.3 can introduce new lint**
   - In the same area or in "COMMON ERRORS TO CATCH BEFORE COMMIT" (or "CRITICAL RULE (Step 12)"), add a bullet or short paragraph:
   - **Type or lint fixes applied in Step 12.2 or 12.3 can introduce new lint issues** (e.g. Ruff E402 if a non-import line is placed between imports). You MUST re-run Step 12.3 (quality) after any such fix and parse the full tool output; verify zero errors before proceeding. Do not assume earlier 12.3 run still applies.
   - Optionally reference E402 and side-effect imports: e.g. "When adding `_ = module` to satisfy reportUnusedImport, place it after all imports to avoid E402."

3. **Strengthen Step 12.3 checklist / verification**
   - In the Step 12 checklist or "Verification Requirements," add an explicit item: **If you fixed type errors (12.2) or lint errors (12.3) during this run, confirm that Step 12.3 was executed again after the fix and that `results.quality.success` is true with zero errors.**
   - Ensure the checklist blocks Step 13 if 12.3 was not re-run after a code change in 12.2 or 12.3.

4. **Optional: integration test**
   - Add or extend an integration test that asserts the commit prompt contains the requirement to re-run Step 12.3 after code fixes in Step 12.2/12.3 (e.g. a string or pattern that indicates mandatory re-run of quality after type/lint fix). This guards against prompt drift.

## Dependencies

- None. Changes are limited to `.cortex/synapse/prompts/commit.md` (Synapse submodule if applicable).

## Success Criteria

- Commit prompt explicitly requires re-running Step 12.3 after any code change in Step 12.2 or 12.3, and states that type/lint fixes can introduce new lint (e.g. E402).
- Step 12 checklist or verification section includes an item that blocks commit if 12.3 was not re-run after a fix in 12.2/12.3.
- Optional: integration test confirms the commit prompt contains the re-run-12.3-after-fix requirement.
- Full test suite and quality gate pass after edits.

## Testing Strategy

- **Prompt edits**: No production code change; only commit prompt markdown.
- **Verification**: Run full commit pipeline (or at least `execute_pre_commit_checks(checks=["quality"])`) and Ruff locally to ensure no regressions.
- **Optional**: Integration test in `tests/integration/` (e.g. commit prompt content tests) that checks for the new re-run-12.3 and/or E402-reminder text in the commit prompt.
- **Regression**: Full test suite and quality gate (format, lint, type_check, quality, tests) must pass.

## Risks and Mitigation

- **Synapse submodule**: If the commit prompt lives in the Synapse submodule, edits are in the submodule; parent repo tracks the new commit. Mitigation: follow existing SessionOptimization flow (edit in .cortex/synapse, commit in submodule, then parent).
- **Prompt length**: Keep new text concise to avoid bloat. Mitigation: use short bullets and reference "Step 12.3" and "results.quality" by name.

## Timeline

- Single session (under 1 hour): prompt-only changes and optional test.

## Notes

- CI run: <https://github.com/igrechuhin/Cortex/actions/runs/21592220363>  
- Ruff error: E402 in `tests/integration/test_prompt_icons.py` (resolved by moving `_ = cortex.main` after all imports).
- Plans directory path: resolve via `get_structure_info()` → `structure_info.paths.plans`.
