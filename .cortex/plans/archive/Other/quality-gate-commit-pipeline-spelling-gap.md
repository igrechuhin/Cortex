# Investigation: Commit Pipeline vs Quality Gate (Spelling)

**Related**: See [Session Optimization: Commit Pipeline Orchestration Refactor](.cortex/plans/session-optimization-commit-pipeline-orchestration-refactor.md) for the phase-based pipeline structure; this plan focuses on the spelling-check gap and CI alignment.

**Date**: 2026-02-02  
**CI run**: <https://github.com/igrechuhin/Cortex/actions/runs/21602372138>  
**Trigger**: Commit pipeline passed locally; quality gate failed in CI.

## Root causes

### 1. Spelling not in commit pipeline

- **CI** runs: format, lint, type_check (src + tests/scripts), file sizes, function lengths, **spelling**, markdown lint, tests.
- **Commit pipeline** (`execute_pre_commit_checks`) supports only: `fix_errors`, `format`, `format_ci_parity`, `type_check`, `quality`, `test_naming`, `tests`.
- **Spelling** is not a check in the MCP tool or in Step 12 of the commit prompt. The commit workflow therefore never runs spelling, so it cannot catch spelling failures before push.

### 2. CI spelling step failed (environment)

- The quality workflow step "Check spelling (cSpell)" runs `uv run python .cortex/synapse/scripts/python/check_spelling.py`.
- When `cspell` is not in PATH, the workflow runs `npm install -g cspell`, which failed with:
  - `npm error 404 '@cspell/rpc@9.6.3' is not in this registry`
- So the failure was due to **npm install** of cspell (likely a bad or missing dependency in a recent cspell version), not due to actual spelling errors in the repo.

## Fixes applied

1. **Commit pipeline**: Add `spelling` check to `execute_pre_commit_checks` (PreCommitCheck.SPELLING, pipeline step via synapse script `check_spelling.py`), and include it in Step 12 of the commit prompt so the same check runs locally as in CI.
2. **CI**: Harden the spelling step by pinning cspell to a known-good version (e.g. `cspell@8.6.1`) when installing, so the job does not fail on npm 404 for `@cspell/rpc`.

## References

- Agent transcript: commit workflow ran Step 12 (format, type_check, quality, test_naming, markdown lint, tests) with no spelling step.
- CI logs: `quality/16_Check spelling (cSpell).txt`, `quality/22_Quality check summary.txt`.
