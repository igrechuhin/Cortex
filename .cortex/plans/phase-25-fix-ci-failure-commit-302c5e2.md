# Phase 25: Fix CI Failure - Commit 302c5e2

**Status:** Planning  
**Priority:** ASAP  
**Created:** 2026-01-16  
**Target Completion:** 2026-01-16

## Goal

Investigate and fix the GitHub Actions CI failure from commit `302c5e2` ("Fix type errors, test failures, and code quality issues #90"). The quality check failed with exit code 1, preventing the commit from passing CI validation.

## Context

**Failed GitHub Actions Run:**

- **URL:** <https://github.com/igrechuhin/Cortex/actions/runs/21059818223>
- **Commit:** `302c5e2` - "Fix type errors, test failures, and code quality issues #90"
- **Workflow:** `quality.yml`
- **Failure:** Quality check step failed with exit code 1
- **Annotation:** "Process completed with exit code 1"
- **Total Duration:** 34 seconds
- **Job:** `quality` (30s duration)

**Recent Work Context:**

Based on roadmap and activeContext, recent work included:

- Fixed type errors by making private functions public in `validation_dispatch.py`
- Fixed unused call result warnings in test files
- Fixed implicit string concatenation in `test_roadmap_sync.py`
- Fixed test failures in `test_consolidated.py`
- Fixed 11 linting errors using ruff check --fix
- Added pyright ignore comments for legitimate test access to private functions
- All tests passing locally with 90.39% coverage (2,451 passed, 2 skipped)
- All code quality checks passing locally (file size, function length)
- Type checking: 0 errors in src/ locally
- All files properly formatted locally (Black check passed, 284 files unchanged)

**Quality Checks in CI Pipeline:**

1. Black formatting check (`black --check src/ tests/ .cortex/synapse/scripts/`)
2. Ruff linting (`ruff check src/ tests/ .cortex/synapse/scripts/`)
3. Pyright type checking (`pyright src/`)
4. File size checks (`.cortex/synapse/scripts/python/check_file_sizes.py` - max 400 lines)
5. Function length checks (`.cortex/synapse/scripts/python/check_function_lengths.py` - max 30 lines)
6. Test execution with coverage (`pytest` with `--cov-fail-under=90`)

**Potential Failure Causes:**

- Environment differences between local and CI (Python version, dependency versions)
- Missing dependencies in CI environment
- Import path differences between local and CI
- Test failures that don't occur locally
- Coverage dropping below 90% threshold in CI
- File size or function length violations not caught locally
- Type checking differences (pyright version differences)
- Formatting differences (Black version differences)
- Linting differences (Ruff version differences)
- Missing files or changes not committed to git
- CI-specific path resolution issues

**Related Plans:**

- **Phase 23:** Fix CI Failure After Validation Refactor (commit `612af0e`) - Similar issue, different commit
- **Phase 22:** Fix Commit Pipeline Quality Gate - General pipeline improvements
- **Phase 20:** Code Review Fixes - Ongoing work that may have introduced issues

## Approach

Systematically investigate the CI failure by:

1. **Analyze GitHub Actions logs** - Identify which specific step failed and why
2. **Reproduce failure locally** - Run all quality checks in CI-like environment
3. **Compare local vs CI** - Identify environment differences
4. **Fix identified issues** - Address root causes
5. **Verify CI will pass** - Ensure all checks pass before committing fix

## Implementation Steps

### Step 1: Analyze GitHub Actions Failure

**Priority:** Critical  
**Effort:** Low (30 minutes)  
**Impact:** High - Understanding root cause

**Tasks:**

1. **Review GitHub Actions run details:**
   - Access full workflow logs: <https://github.com/igrechuhin/Cortex/actions/runs/21059818223>
   - Identify which specific step failed (Black, Ruff, Pyright, file sizes, function lengths, or tests)
   - Extract exact error messages and stack traces
   - Note any warnings that might indicate issues
   - Check if failure is in a specific step or multiple steps

2. **Analyze error patterns:**
   - Check for import errors
   - Check for type errors
   - Check for test failures
   - Check for coverage threshold violations
   - Check for file size violations
   - Check for function length violations
   - Check for formatting issues
   - Check for linting issues

3. **Compare with local state:**
   - Note which checks pass locally but fail in CI
   - Identify environment-specific issues
   - Document any version differences

**Success Criteria:**

- Identified which quality check step failed
- Documented specific error message and stack trace
- Understood why local checks pass but CI fails
- Clear action plan for fixes

### Step 2: Reproduce Failure Locally

**Priority:** Critical  
**Effort:** Medium (1-2 hours)  
**Impact:** High - Confirming root cause

**Tasks:**

1. **Set up CI-like environment:**
   - Use Python 3.13 (same as CI)
   - Use `uv` for dependency management (same as CI)
   - Install dependencies: `uv sync --group dev --extra dev`
   - Verify tool versions match CI (Black, Ruff, Pyright, pytest)

2. **Run all quality checks in CI order:**

   ```bash
   # Step 1: Check formatting
   uv run black --check src/ tests/ .cortex/synapse/scripts/
   
   # Step 2: Check linting
   uv run ruff check src/ tests/ .cortex/synapse/scripts/
   
   # Step 3: Check types
   uv run pyright src/
   
   # Step 4: Check file sizes
   uv run python .cortex/synapse/scripts/python/check_file_sizes.py
   
   # Step 5: Check function lengths
   uv run python .cortex/synapse/scripts/python/check_function_lengths.py
   
   # Step 6: Run tests with coverage
   uv run python -m pytest tests/ -v --cov=src/cortex --cov-report=xml --cov-report=term --cov-fail-under=90
   ```

3. **Document failures:**
   - Capture full output of failing checks
   - Note any differences from local environment
   - Identify specific files/functions causing issues

4. **Check git status:**
   - Verify all changes are committed: `git status`
   - Check for untracked files: `git status --porcelain`
   - Verify commit matches CI: `git log -1 --oneline`

**Success Criteria:**

- Reproduced CI failure locally
- Identified specific failing checks
- Documented exact error messages
- Confirmed all changes are committed

### Step 3: Investigate Environment Differences

**Priority:** High  
**Effort:** Medium (1 hour)  
**Impact:** Medium - Understanding why local passes but CI fails

**Tasks:**

1. **Compare tool versions:**
   - Check Black version: `uv run black --version`
   - Check Ruff version: `uv run ruff --version`
   - Check Pyright version: `uv run pyright --version`
   - Check pytest version: `uv run pytest --version`
   - Compare with CI environment versions

2. **Check dependency resolution:**
   - Verify `requirements.txt` and `pyproject.toml` are up to date
   - Check if `uv sync` resolves dependencies correctly
   - Verify all dev dependencies are included

3. **Check path resolution:**
   - Verify relative paths work in CI environment
   - Check if `.cortex/synapse/scripts/` paths are accessible
   - Verify Python path includes necessary directories

4. **Check test environment:**
   - Verify test discovery works correctly
   - Check if coverage calculation matches local
   - Verify test fixtures and mocks work in CI

**Success Criteria:**

- Identified version differences (if any)
- Understood why environment differences cause failures
- Documented environment-specific issues

### Step 4: Fix Identified Issues

**Priority:** Critical  
**Effort:** Medium (2-4 hours)  
**Impact:** High - Resolves CI failure

**Tasks:**

1. **Fix import errors:**
   - Update any incorrect import statements
   - Fix circular import issues if any
   - Ensure all modules are properly exported

2. **Fix type errors:**
   - Resolve any type errors that appear in CI
   - Update type hints if needed
   - Fix type checking issues specific to CI environment

3. **Fix test failures:**
   - Update tests that fail in CI but pass locally
   - Fix environment-specific test issues
   - Ensure all tests pass in CI-like environment

4. **Fix coverage issues:**
   - If coverage drops below 90%, add missing tests
   - Verify coverage calculation is correct
   - Ensure coverage includes all necessary files

5. **Fix file size violations:**
   - If any file exceeds 400 lines, split further
   - Extract additional helper functions if needed

6. **Fix function length violations:**
   - If any function exceeds 30 lines, extract helpers
   - Refactor long functions into smaller ones

7. **Fix formatting/linting:**
   - Run `black` to fix formatting issues
   - Run `ruff check --fix` to fix linting issues
   - Ensure all files are properly formatted

8. **Fix environment-specific issues:**
   - Update paths if needed for CI environment
   - Fix any CI-specific configuration issues
   - Ensure all scripts work in CI environment

**Success Criteria:**

- All quality checks pass in CI-like environment
- No import errors
- No type errors
- No test failures
- Coverage ≥90%
- No file size violations
- No function length violations
- All files properly formatted and linted

### Step 5: Verify CI Will Pass

**Priority:** Critical  
**Effort:** Low (30 minutes)  
**Impact:** High - Prevents re-failure

**Tasks:**

1. **Run full quality check suite:**
   - Execute all checks in the same order as CI
   - Use CI-like environment (Python 3.13, uv, same tool versions)
   - Verify exit codes are 0 for all checks
   - Confirm no warnings that could cause issues

2. **Check git status:**
   - Ensure all changes are staged
   - Verify no untracked files
   - Confirm commit is ready

3. **Review changes:**
   - Verify all fixes are correct
   - Check that no regressions introduced
   - Ensure backward compatibility maintained
   - Document any breaking changes (if any)

4. **Pre-commit validation:**
   - Run `fix_quality_issues()` MCP tool if available
   - Verify all pre-commit checks pass
   - Ensure commit workflow requirements are met

**Success Criteria:**

- All quality checks pass with exit code 0 in CI-like environment
- All changes committed and ready
- CI will pass on next push
- No regressions introduced

## Dependencies

- **Phase 20: Code Review Fixes** - Recent fixes may have introduced issues
- **Phase 22: Fix Commit Pipeline Quality Gate** - Related but separate (general pipeline improvements)
- **Phase 23: Fix CI Failure After Validation Refactor** - Similar issue, may provide insights

## Success Criteria

- ✅ CI failure root cause identified
- ✅ Failure reproduced locally in CI-like environment
- ✅ Environment differences understood and addressed
- ✅ All quality checks pass locally in CI-like environment
- ✅ No import errors, type errors, or test failures
- ✅ Coverage ≥90%
- ✅ No file size or function length violations
- ✅ All files properly formatted and linted
- ✅ CI will pass on next push

## Risks & Mitigation

### Risk 1: Environment differences not reproducible locally

- **Mitigation:** Use exact same Python version and tool versions as CI
- **Detection:** Compare tool versions and dependency resolution

### Risk 2: Intermittent failures

- **Mitigation:** Run checks multiple times to verify consistency
- **Detection:** Monitor for flaky tests or non-deterministic behavior

### Risk 3: Missing files or uncommitted changes

- **Mitigation:** Verify all changes are committed before investigating
- **Detection:** `git status` and `git diff` checks

### Risk 4: Coverage threshold violations

- **Mitigation:** Run coverage checks locally before committing
- **Detection:** `pytest --cov-fail-under=90` will fail if coverage drops

### Risk 5: Version-specific issues

- **Mitigation:** Pin tool versions in `pyproject.toml` or `requirements.txt`
- **Detection:** Compare tool versions between local and CI

## Timeline

- **Step 1:** 30 minutes - Analyze GitHub Actions failure
- **Step 2:** 1-2 hours - Reproduce failure locally
- **Step 3:** 1 hour - Investigate environment differences
- **Step 4:** 2-4 hours - Fix identified issues
- **Step 5:** 30 minutes - Verify CI will pass
- **Total:** 5-8 hours

## Notes

- This is a focused fix for the specific CI failure from commit `302c5e2`
- The commit message suggests fixes were applied, but CI still failed - need to investigate why
- Local checks all passed, indicating environment differences or missing changes
- Follow project coding standards (file size ≤400 lines, function length ≤30 lines)
- Use `fix_quality_issues()` MCP tool for automatic quality fixes when appropriate
- Ensure all fixes maintain backward compatibility
