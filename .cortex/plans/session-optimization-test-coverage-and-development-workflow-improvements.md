# Session Optimization: Test Coverage and Development Workflow Improvements

**Created from**: End-of-session analysis 2026-02-16T15:29  
**Status**: PENDING  
**Priority**: Medium

## Overview

This plan addresses workflow improvements identified during the test coverage improvement session (2026-02-16). The session successfully increased coverage from 89.30% to 89.68% but revealed several optimization opportunities for future sessions.

## Goals

1. Improve coverage gap identification efficiency
2. Enable proactive file size limit enforcement
3. Provide guidance for strategic test coverage improvement
4. Reduce test development friction

## Steps

### Step 1: Coverage Visualization Tool (High Priority)

**Goal**: Create tool to identify files with most uncovered lines

**Tasks**:

- Create `scripts/python/analyze_coverage_gaps.py`
- Tool should:
  - Parse coverage JSON report
  - Sort files by uncovered line count
  - Output top N files with line numbers
  - Support filtering by directory/module
- Add to pre-commit pipeline as optional check
- Document usage in `docs/guides/testing.md`

**Success Criteria**:

- Tool outputs top 10 files with uncovered lines
- Can be run standalone: `python scripts/python/analyze_coverage_gaps.py`
- Integrated into commit pipeline as optional Step 12.6

### Step 2: File Size Pre-Commit Warning (High Priority)

**Goal**: Warn developers when files approach 400-line limit

**Tasks**:

- Add file size check to pre-commit hook (`.pre-commit-config.yaml`)
- Check runs before quality gate
- Warns at 350 lines, errors at 400 lines
- Add IDE integration guidance (Cursor rule or VSCode setting)
- Document in `docs/guides/code-quality.md`

**Success Criteria**:

- Pre-commit hook warns at 350 lines
- Pre-commit hook blocks at 400 lines
- IDE integration documented for Cursor/VSCode

### Step 3: Test Coverage Guidance Documentation (High Priority)

**Goal**: Document coverage prioritization strategy

**Tasks**:

- Add section to `docs/guides/testing.md`:
  - Coverage expectations (90%+ acceptable, 95%+ ideal)
  - Prioritization strategy (which modules/files to focus on)
  - Common patterns for quick coverage gains
  - Integration test patterns for handler dispatch tools
- Add test planning checklist to implement prompt Step 4
- Reference coverage guidance in commit prompt Step 12

**Success Criteria**:

- Documentation includes coverage prioritization guidance
- Implement prompt includes test planning checklist
- Commit prompt references coverage guidance

### Step 4: Canonical Import Documentation (Medium Priority)

**Goal**: Standardize import paths for common test models

**Tasks**:

- Create `tests/helpers/imports.py` with re-exports:
  - `ValidationResultModel`, `ValidationErrorModel` from `cortex.validation.models`
  - Common manager types from `cortex.managers.types`
  - Common exceptions from `cortex.core.exceptions`
- Update `tests/helpers/README.md` with import guidance
- Migrate existing tests to use canonical imports (optional, gradual)

**Success Criteria**:

- `tests/helpers/imports.py` provides canonical imports
- README documents import patterns
- New tests use canonical imports

### Step 5: Coverage Threshold Flexibility (Medium Priority)

**Goal**: Allow 89.5%+ as acceptable when close to 90%

**Tasks**:

- Update `execute_pre_commit_checks` to accept 89.5%+ with warning
- Require 90%+ for release/CI
- Document threshold policy in commit prompt and `docs/guides/testing.md`
- Update quality gate documentation

**Success Criteria**:

- Pre-commit accepts 89.5%+ with warning message
- CI still requires 90%+
- Policy documented in commit prompt and testing guide

### Step 6: Test Template for Common Patterns (Low Priority)

**Goal**: Create test templates for faster test creation

**Tasks**:

- Create `tests/helpers/test_templates.py` with:
  - `test_error_path_template()` for error handling
  - `test_edge_case_template()` for edge cases
  - `test_validation_template()` for validation logic
- Document usage in `tests/helpers/README.md`
- Add examples in test files

**Success Criteria**:

- Test templates available in `tests/helpers/`
- README documents template usage
- Examples added to existing test files

## Dependencies

- Step 1 (Coverage Visualization) can be done independently
- Step 2 (File Size Warning) can be done independently
- Step 3 (Coverage Guidance) can be done independently
- Step 4 (Import Documentation) can be done independently
- Step 5 (Threshold Flexibility) depends on testing infrastructure
- Step 6 (Test Templates) can be done independently

## Estimated Effort

- **Step 1**: 2-3 hours (script development + integration)
- **Step 2**: 1-2 hours (pre-commit hook + documentation)
- **Step 3**: 1-2 hours (documentation + prompt updates)
- **Step 4**: 1 hour (imports.py + README)
- **Step 5**: 1-2 hours (threshold logic + documentation)
- **Step 6**: 1-2 hours (templates + examples)

**Total**: 7-12 hours

## Related Plans

- Session Optimization: Testing Coverage Documentation and Planning (2026-02-16 Analysis) - PENDING
- Quality gate improvements (existing roadmap items)

## Notes

- Steps can be implemented incrementally
- High-priority steps (1-3) should be completed first
- Medium-priority steps (4-5) can follow
- Low-priority step (6) is optional enhancement
