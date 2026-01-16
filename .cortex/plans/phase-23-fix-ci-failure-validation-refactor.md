# Phase 23: Fix CI Failure After Validation Refactor

**Status:** Planning  
**Priority:** ASAP  
**Created:** 2026-01-16  
**Target Completion:** 2026-01-16

## Goal

Investigate and fix the GitHub Actions CI failure from commit `612af0e` ("refactor: Split validation_operations.py into focused modules"). The quality check failed with exit code 1, preventing the commit from passing CI validation.

## Context

**Failed GitHub Actions Run:**

- **URL:** <https://github.com/igrechuhin/Cortex/actions/runs/21056088777>
- **Commit:** `612af0e` - "refactor: Split validation_operations.py into focused modules (Phase …"
- **Workflow:** `quality.yml`
- **Failure:** Quality check step failed with exit code 1
- **Annotation:** "Process completed with exit code 1"

**Recent Refactoring (Step 3.1 of Phase 20):**

- Split `validation_operations.py` from 1063 lines to 427 lines (60% reduction)
- Extracted 7 new modules:
  - `validation_schema.py` (83 lines)
  - `validation_duplication.py` (74 lines)
  - `validation_quality.py` (105 lines)
  - `validation_infrastructure.py` (35 lines)
  - `validation_timestamps.py` (33 lines)
  - `validation_roadmap_sync.py` (81 lines)
  - `validation_dispatch.py` (321 lines)
- Enhanced `validation_helpers.py` with missing functions
- Updated test imports to use new modules

**Quality Checks in CI Pipeline:**

1. Black formatting check (`black --check`)
2. Ruff linting (`ruff check`)
3. Pyright type checking (`pyright src/`)
4. File size checks (`check_file_sizes.py` - max 400 lines)
5. Function length checks (`check_function_lengths.py` - max 30 lines)
6. Test execution with coverage (`pytest` with `--cov-fail-under=90`)

**Potential Failure Causes:**

- Missing module files not committed to git
- Import errors in new modules or updated imports
- Type errors from refactoring
- File size violations in new modules
- Function length violations in new modules
- Test failures due to import changes
- Missing `__init__.py` exports for new modules

## Approach

Systematically investigate the CI failure by:

1. **Reproduce failure locally** - Run all quality checks to identify specific failures
2. **Check for missing files** - Verify all new modules are present and committed
3. **Verify imports** - Check all import statements are correct
4. **Fix identified issues** - Address any violations or errors found
5. **Verify CI passes** - Ensure all quality checks pass before committing fix

## Implementation Steps

### Step 1: Reproduce CI Failure Locally

**Priority:** Critical  
**Effort:** Low (30 minutes)  
**Impact:** High - Understanding root cause

**Tasks:**

1. **Run all quality checks locally:**

   ```bash
   # Check formatting
   uv run black --check src/ tests/ .cortex/synapse/scripts/
   
   # Check linting
   uv run ruff check src/ tests/ .cortex/synapse/scripts/
   
   # Check types
   uv run pyright src/
   
   # Check file sizes
   uv run python .cortex/synapse/scripts/python/check_file_sizes.py
   
   # Check function lengths
   uv run python .cortex/synapse/scripts/python/check_function_lengths.py
   
   # Run tests
   uv run python -m pytest tests/ -v --cov=src/cortex --cov-report=xml --cov-report=term --cov-fail-under=90
   ```

2. **Identify which check fails:**
   - Note the specific error message
   - Capture full output and stack traces
   - Document the failing step

3. **Check git status:**
   - Verify all new modules are tracked: `git ls-files | grep validation`
   - Check for untracked files: `git status --porcelain`
   - Verify no files were missed in the refactor

**Success Criteria:**

- Identified which quality check fails
- Documented specific error message
- Confirmed all new modules are in git

### Step 2: Verify Module Files and Imports

**Priority:** Critical  
**Effort:** Low (30 minutes)  
**Impact:** High - Common refactoring issue

**Tasks:**

1. **Verify all new modules exist:**
   - Check `src/cortex/tools/validation_schema.py` exists
   - Check `src/cortex/tools/validation_duplication.py` exists
   - Check `src/cortex/tools/validation_quality.py` exists
   - Check `src/cortex/tools/validation_infrastructure.py` exists
   - Check `src/cortex/tools/validation_timestamps.py` exists
   - Check `src/cortex/tools/validation_roadmap_sync.py` exists
   - Check `src/cortex/tools/validation_dispatch.py` exists

2. **Verify `__init__.py` exports:**
   - Check `src/cortex/tools/__init__.py` exports new modules if needed
   - Verify imports in `validation_operations.py` are correct
   - Check test imports are updated correctly

3. **Test imports:**

   ```python
   # Test that all imports work
   from cortex.tools.validation_schema import ...
   from cortex.tools.validation_duplication import ...
   from cortex.tools.validation_quality import ...
   from cortex.tools.validation_infrastructure import ...
   from cortex.tools.validation_timestamps import ...
   from cortex.tools.validation_roadmap_sync import ...
   from cortex.tools.validation_dispatch import ...
   ```

**Success Criteria:**

- All new modules exist and are tracked in git
- All imports work correctly
- No missing module errors

### Step 3: Fix Identified Issues

**Priority:** Critical  
**Effort:** Medium (1-2 hours)  
**Impact:** High - Resolves CI failure

**Tasks:**

1. **Fix import errors:**
   - Update any incorrect import statements
   - Add missing `__init__.py` exports if needed
   - Fix circular import issues if any

2. **Fix type errors:**
   - Resolve any type errors introduced by refactoring
   - Update type hints if needed
   - Fix type checking issues

3. **Fix file size violations:**
   - If any new module exceeds 400 lines, split further
   - Extract additional helper functions if needed

4. **Fix function length violations:**
   - If any function exceeds 30 lines, extract helpers
   - Refactor long functions into smaller ones

5. **Fix test failures:**
   - Update test imports to use new modules
   - Fix any test failures due to refactoring
   - Ensure all tests pass

6. **Fix formatting/linting:**
   - Run `black` to fix formatting issues
   - Run `ruff check --fix` to fix linting issues

**Success Criteria:**

- All quality checks pass locally
- No import errors
- No type errors
- No file size violations
- No function length violations
- All tests passing with 90%+ coverage

### Step 4: Verify CI Will Pass

**Priority:** Critical  
**Effort:** Low (15 minutes)  
**Impact:** High - Prevents re-failure

**Tasks:**

1. **Run full quality check suite:**
   - Execute all checks in the same order as CI
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

**Success Criteria:**

- All quality checks pass with exit code 0
- All changes committed and ready
- CI will pass on next push

## Dependencies

- **Phase 20: Code Review Fixes** - Step 3.1 (validation refactor) must be complete
- **Phase 22: Fix Commit Pipeline Quality Gate** - Related but separate (general pipeline improvements)

## Success Criteria

- ✅ CI failure root cause identified
- ✅ All quality checks pass locally
- ✅ All new modules properly committed
- ✅ All imports working correctly
- ✅ No type errors, file size violations, or function length violations
- ✅ All tests passing with 90%+ coverage
- ✅ CI will pass on next push

## Risks & Mitigation

**Risk 1: Missing files not committed**

- **Mitigation:** Verify all new modules are in git before investigating
- **Detection:** `git ls-files | grep validation` and `git status`

**Risk 2: Import errors from refactoring**

- **Mitigation:** Test all imports before committing
- **Detection:** Run `pyright src/` and check for import errors

**Risk 3: Test failures from import changes**

- **Mitigation:** Update all test imports to use new modules
- **Detection:** Run full test suite before committing

**Risk 4: File size or function length violations**

- **Mitigation:** Run quality check scripts before committing
- **Detection:** `check_file_sizes.py` and `check_function_lengths.py`

## Timeline

- **Step 1:** 30 minutes - Reproduce failure locally
- **Step 2:** 30 minutes - Verify modules and imports
- **Step 3:** 1-2 hours - Fix identified issues
- **Step 4:** 15 minutes - Verify CI will pass
- **Total:** 2-3 hours

## Notes

- This is a focused fix for the specific CI failure from commit `612af0e`
- Phase 22 addresses general pipeline improvements (separate work)
- All fixes should maintain backward compatibility
- Follow project coding standards (file size ≤400 lines, function length ≤30 lines)
