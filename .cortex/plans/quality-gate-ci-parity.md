---
title: "Ensure quality gate CI parity: close remaining gaps between local and CI checks"
component: quality
work_type: fix
status: IN_PROGRESS
priority: high
created: 2026-03-21
depends_on: []
---

## Goal

Audit and close all gaps between the local quality gate (`run_quality_gate()`) and CI (`quality.yml`), ensuring that if CI will fail, the local gate fails first — preventing dirty commits from reaching the remote.

## Context

- **Root cause incident**: Commit `4d6f7f9` passed local `run_quality_gate()` but failed CI due to MD036 markdown lint error. The detached worker correctly ran `rumdl check` and detected the error in `markdown_result`, but `_poll_phase_a_result()` only returned `envelope["result"]` — silently dropping the markdown lint result. Fix applied in this session.

- This plan goes beyond the specific bug fix to audit all CI steps against local gate coverage, ensuring no other check categories are similarly disconnected.

- CI checks (from `quality.yml`): formatting, synapse formatting, ruff lint, synapse lint, pyright (source), pyright (tests/scripts), file sizes, function lengths, cSpell spelling, rumdl markdown, tests (separate workflow).

- Local gate checks (from `pre_commit_phase_dispatch.py` Phase A): fix_errors, format, synapse_format, synapse_lint, type_check, quality, tests, eval_fast, markdown_lint.

## Implementation Steps

### Step 1: Audit CI vs local check coverage matrix

- **Files to read**: `.github/workflows/quality.yml`, `src/cortex/tools/execution/pre_commit_phase_dispatch.py`, `src/cortex/tools/execution/pre_commit_worker.py`
- Create a matrix: each CI step → corresponding local check name → verified working?
- Identify any CI steps that have no local equivalent or are running differently

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| CI step IDs in quality.yml | `.github/workflows/quality.yml` | quality.yml |
| Phase A check list | `pre_commit_phase_dispatch.py` | Lines 23-33 |
| Worker check execution | `pre_commit_worker.py` | Main execution path |

### Step 2: Verify cSpell parity

- CI runs cSpell (`quality.yml` step "Check spelling") — does the local gate include spelling?
- If not, assess whether to add it or document it as CI-only
- Spelling errors that only CI catches create the same "local passes, CI fails" problem

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `cspell` or `spelling` in local gate | `src/cortex/tools/execution/` | Phase dispatch, worker |
| cSpell step in quality.yml | `.github/workflows/quality.yml` | quality.yml |

### Step 3: Verify file-size and function-length check parity

- CI runs `check_file_sizes.py` and `check_function_lengths.py` — the local gate's `quality` check includes these via the Python adapter
- Verify the local adapter runs the exact same scripts with the same exclusions

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| File size check in adapter | `src/cortex/tools/execution/` | Quality adapter/helpers |
| Function length check | Same | Same |
| Exclusion lists match CI | Scripts vs adapter | Both |

### Step 4: Add integration test for markdown-result merging

- **2026-03-21 (done)**: Added `TestRunQualityGateMarkdownMerge.test_run_quality_gate_false_when_markdown_errors_in_envelope` in `tests/unit/test_poll_phase_a_markdown_merge.py` — mocks `_start_phase_a_job` + worker envelope so language checks pass and `markdown_result` fails, and asserts `run_quality_gate()` returns `preflight_passed: false` (regression guard for merge of `markdown_result` into the polled result).
- End-to-end path: `run_quality_gate()` with mocked detached worker envelope (language `result` passes, `markdown_result` reports errors) must yield `preflight_passed: false`.

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Integration test for quality gate | `tests/unit/test_poll_phase_a_markdown_merge.py` | Test file |
| `_poll_phase_a_result` merge logic | `pre_commit_zero_arg_tools.py` | Lines 105-145 |

### Step 5: Document CI parity expectations

- **File**: `docs/api/tools.md` (quality gate section)
- Add subsection: "CI parity guarantee" — document that `run_quality_gate()` must catch everything CI catches, and the process for adding new CI checks (must also add local equivalent)
- Reference the parity matrix from Step 1

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "CI parity" in docs | `docs/api/tools.md` | tools.md |

## Dependencies

- The markdown-result merging fix (already applied in this session) is a prerequisite.

## Success Criteria

- Complete parity matrix documented: every CI check maps to a local gate check
- Any gaps are either closed (local check added) or explicitly documented as CI-only with justification
- Integration test prevents regression of the markdown-result merging bug
- Zero "local passes, CI fails" incidents for checks that are supposed to have parity

## Testing Strategy

- Integration tests for the quality gate result merging
- Matrix audit is a documentation deliverable, not a code change
- Existing quality gate tests continue to pass
- 95%+ coverage maintained
