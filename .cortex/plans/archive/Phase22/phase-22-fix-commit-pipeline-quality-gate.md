# Phase 22: Fix Commit Pipeline Quality Gate

**Status:** COMPLETE  
**Priority:** ASAP  
**Created:** 2026-01-15  
**Target Completion:** 2026-01-17  
**Completed:** 2026-01-21

## Goal

Fix the commit pipeline (GitHub Actions workflow) to properly catch and fail on quality gate violations. The pipeline currently passes errors that prevent the quality gate from passing, requiring improvements to error handling, validation, and fail-fast mechanisms.

## Context

The commit pipeline (`quality.yml` workflow) is failing with errors that prevent the quality gate from passing. Analysis of the workflow and related scripts reveals potential issues:

**Current Workflow Issues:**

- GitHub Actions workflow (`quality.yml`) runs multiple quality checks but may not properly fail on violations
- Codecov upload step has `continue-on-error: true` and `fail_ci_if_error: false` (acceptable for coverage upload, but other steps should fail)
- No explicit fail-fast mechanism to stop on first error
- Scripts may not properly exit with error codes in all failure scenarios
- Missing validation of step outputs before proceeding to next steps

**Quality Checks in Pipeline:**

1. Black formatting check (`black --check`)
2. Ruff linting (`ruff check`)
3. Pyright type checking (`pyright src/`)
4. File size checks (`.cortex/synapse/scripts/python/check_file_sizes.py`)
5. Function length checks (`.cortex/synapse/scripts/python/check_function_lengths.py`)
6. Test execution with coverage (`pytest` with `--cov-fail-under=90`)

**Related Context:**

- Recent work on commit procedures and quality checks (2026-01-15)
- Comprehensive pre-commit validation system in place
- `execute_pre_commit_checks()` MCP tool available for structured quality checks
- Commit prompt (`.cortex/synapse/prompts/commit.md`) defines detailed validation requirements

## Approach

Improve the commit pipeline by:

1. **Investigate current failures** - Analyze the specific errors from the failed GitHub Actions run
2. **Enhance error handling** - Ensure all steps properly fail on violations
3. **Add validation** - Verify step outputs before proceeding
4. **Implement fail-fast** - Stop pipeline on first error
5. **Improve error reporting** - Better diagnostics and actionable error messages
6. **Align with commit prompt** - Ensure pipeline matches commit procedure requirements

## Implementation Steps

### Step 1: Investigate Current Pipeline Failures

**Priority:** Critical  
**Effort:** Medium (2-3 hours)  
**Impact:** High - Understanding root cause

**Tasks:**

1. **Analyze GitHub Actions run:**
   - Review failed workflow run: <https://github.com/igrechuhin/Cortex/actions/runs/21045376527>
   - Commit: `bb369a2` - "Fix type errors and function length violations"
   - Identify which step(s) failed (quality check step failed with exit code 1)
   - Extract error messages and stack traces from workflow logs
   - Determine if errors are being caught or silently ignored
   - Note: Local pre-commit checks all passed, but CI failed - investigate environment differences

2. **Review workflow configuration:**
   - Check `.github/workflows/quality.yml` for error handling issues
   - Verify all steps have proper exit code checking
   - Identify steps that might continue on error incorrectly
   - Check for missing validation of step outputs

3. **Test scripts locally:**
   - Run each quality check script manually to verify behavior
   - Test error scenarios (violations, missing dependencies, etc.)
   - Verify scripts exit with proper error codes (non-zero on failure)
   - Check if scripts output errors to stderr vs stdout

4. **Document findings:**
   - Create summary of specific failures
   - Identify root causes (missing error handling, incorrect exit codes, etc.)
   - List all issues preventing quality gate from passing

**Success Criteria:**

- Complete understanding of why pipeline passes errors
- Documented list of specific failures and root causes
- Clear action plan for fixes

### Step 2: Enhance Workflow Error Handling

**Priority:** Critical  
**Effort:** Medium (2-3 hours)  
**Impact:** High - Prevents errors from being ignored

**Tasks:**

1. **Add explicit fail-fast:**
   - Set `fail-fast: true` at job level in `quality.yml`
   - Ensure all steps fail on non-zero exit codes (default behavior, but verify)
   - Remove any `continue-on-error: true` from quality check steps (keep only for Codecov upload)

2. **Add step output validation:**
   - Add explicit checks for error conditions after each quality check step
   - Parse step outputs to verify success (not just exit code)
   - Add validation for critical metrics (coverage percentage, violation counts, etc.)

3. **Improve error reporting:**
   - Add error summary step that collects all failures
   - Include actionable error messages in workflow annotations
   - Add step to display quality check results in readable format

4. **Add dependency checks:**
   - Verify required tools are available before running checks
   - Add explicit version checks for tools (Python, uv, black, ruff, pyright, pytest)
   - Fail early if dependencies are missing or incorrect versions

**Success Criteria:**

- Workflow fails immediately on first quality check violation
- All error conditions properly caught and reported
- Clear error messages in GitHub Actions UI
- No silent failures or ignored errors

### Step 3: Fix Script Exit Codes and Error Handling

**Priority:** Critical  
**Effort:** Medium (2-3 hours)  
**Impact:** High - Ensures scripts properly signal failures

**Tasks:**

1. **Review and fix check scripts:**
   - Verify `check_file_sizes.py` exits with code 1 on violations (already does, verify edge cases)
   - Verify `check_function_lengths.py` exits with code 1 on violations (already does, verify edge cases)
   - Add error handling for edge cases (file read errors, syntax errors, etc.)
   - Ensure all error paths exit with non-zero codes

2. **Add validation to scripts:**
   - Verify scripts check for required dependencies before running
   - Add validation for input parameters (project root, source directory, etc.)
   - Fail early with clear error messages if prerequisites not met

3. **Improve error messages:**
   - Make error messages more actionable (include fix suggestions)
   - Add context about what failed and why
   - Include file paths and line numbers for violations

4. **Test error scenarios:**
   - Test scripts with missing dependencies
   - Test scripts with invalid inputs
   - Test scripts with actual violations
   - Verify all scenarios exit with proper codes

**Success Criteria:**

- All scripts exit with code 1 on violations or errors
- All error paths properly handled
- Clear, actionable error messages
- Scripts fail early on missing prerequisites

### Step 4: Add Coverage Validation

**Priority:** High  
**Effort:** Low (1 hour)  
**Impact:** Medium - Ensures coverage threshold enforced

**Tasks:**

1. **Verify coverage check:**
   - Ensure `pytest` command includes `--cov-fail-under=90` (already present)
   - Verify coverage threshold is enforced (pytest should fail if coverage < 90%)
   - Add explicit validation of coverage percentage in workflow

2. **Add coverage reporting:**
   - Ensure coverage report is generated and visible in workflow
   - Add step to display coverage summary
   - Include coverage percentage in workflow annotations

3. **Handle coverage edge cases:**
   - Verify behavior when coverage is exactly 90.0%
   - Test behavior when coverage is below threshold
   - Ensure coverage check fails pipeline appropriately

**Success Criteria:**

- Coverage threshold properly enforced
- Pipeline fails if coverage < 90%
- Coverage results clearly displayed in workflow

### Step 5: Align Pipeline with Commit Prompt Requirements

**Priority:** High  
**Effort:** Medium (2-3 hours)  
**Impact:** Medium - Ensures consistency

**Tasks:**

1. **Compare pipeline with commit prompt:**
   - Review `.cortex/synapse/prompts/commit.md` for all validation requirements
   - Compare with `.github/workflows/quality.yml` steps
   - Identify any missing checks or misalignments

2. **Add missing validations:**
   - Add any checks required by commit prompt but missing from pipeline
   - Ensure all quality gates match commit procedure requirements
   - Add markdown linting check if required (currently not in pipeline)

3. **Ensure consistency:**
   - Verify thresholds match (file size 400 lines, function length 30 lines, coverage 90%)
   - Ensure error handling matches commit prompt expectations
   - Align error messages with commit prompt guidance

**Success Criteria:**

- Pipeline includes all checks required by commit prompt
- Thresholds and validation logic match commit procedure
- Consistent error handling and reporting

### Step 6: Add Comprehensive Testing

**Priority:** Medium  
**Effort:** Medium (2-3 hours)  
**Impact:** Medium - Prevents regressions

**Tasks:**

1. **Test workflow locally:**
   - Use `act` or similar tool to test GitHub Actions workflow locally
   - Test with violations (file size, function length, coverage, etc.)
   - Verify workflow fails appropriately on each violation type

2. **Add integration tests:**
   - Create test cases that trigger each quality check failure
   - Verify pipeline behavior for each failure scenario
   - Test error reporting and diagnostics

3. **Document test scenarios:**
   - Document how to test each quality check
   - Create test cases for common failure scenarios
   - Add troubleshooting guide for pipeline failures

**Success Criteria:**

- Workflow tested with all violation scenarios
- Integration tests verify proper failure behavior
- Test documentation available for future maintenance

### Step 7: Improve Error Diagnostics

**Priority:** Medium  
**Effort:** Low (1-2 hours)  
**Impact:** Low - Better developer experience

**Tasks:**

1. **Add diagnostic information:**
   - Include environment details in workflow (Python version, tool versions)
   - Add step to display project structure and file counts
   - Include summary of all quality check results

2. **Improve error annotations:**
   - Use GitHub Actions annotations for better error visibility
   - Add file-level annotations for violations
   - Include fix suggestions in error messages

3. **Add troubleshooting guide:**
   - Create documentation for common pipeline failures
   - Include steps to reproduce and fix issues
   - Add links to relevant documentation

**Success Criteria:**

- Clear diagnostic information in workflow output
- Actionable error messages with fix suggestions
- Troubleshooting documentation available

## Dependencies

- **Phase 20: Code Review Fixes** - May identify additional quality issues to address
- **Commit Procedure** - Pipeline must align with commit prompt requirements
- **Quality Check Scripts** - Scripts must be fixed before pipeline can properly validate

## Success Criteria

**Pipeline Quality:**

- ✅ Pipeline fails immediately on first quality check violation
- ✅ All quality checks properly enforced (formatting, linting, type checking, file size, function length, coverage)
- ✅ No errors silently ignored or passed through
- ✅ Clear error messages and diagnostics in GitHub Actions UI

**Error Handling:**

- ✅ All scripts exit with proper error codes on violations
- ✅ Workflow properly catches and reports all errors
- ✅ Fail-fast mechanism prevents unnecessary steps from running

**Alignment:**

- ✅ Pipeline matches commit prompt requirements
- ✅ All thresholds and validation logic consistent
- ✅ Error handling consistent across pipeline and commit procedure

**Testing:**

- ✅ Workflow tested with all violation scenarios
- ✅ Integration tests verify proper failure behavior
- ✅ Documentation available for troubleshooting

## Risks & Mitigation

### Risk 1: Breaking existing workflow

- **Mitigation:** Test changes in a branch first, verify all checks still work
- **Impact:** Medium - Could block commits if workflow breaks

### Risk 2: Missing edge cases in error handling

- **Mitigation:** Comprehensive testing of all failure scenarios
- **Impact:** Medium - Errors might still be missed

### Risk 3: Inconsistent behavior between local and CI

- **Mitigation:** Use same scripts and tools in both environments
- **Impact:** Low - Could cause confusion but not critical

## Timeline

- **Step 1 (Investigation):** 2-3 hours
- **Step 2 (Workflow Error Handling):** 2-3 hours
- **Step 3 (Script Fixes):** 2-3 hours
- **Step 4 (Coverage Validation):** 1 hour
- **Step 5 (Alignment):** 2-3 hours
- **Step 6 (Testing):** 2-3 hours
- **Step 7 (Diagnostics):** 1-2 hours

**Total Estimated Effort:** 12-18 hours  
**Target Completion:** 2026-01-17 (2 days)

## Notes

- This plan addresses the immediate issue of pipeline passing errors
- Future enhancements could include parallel execution of checks, caching, and performance optimizations
- Consider adding pre-commit hooks as additional safety net (but pipeline is primary gate)
- Monitor pipeline execution time to ensure changes don't significantly slow down CI
