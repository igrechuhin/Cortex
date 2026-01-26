# Phase 28: Enforce MCP Tools for All .cortex Operations

## Status

- **Status**: COMPLETE
- **Priority**: High
- **Start Date**: 2026-01-16
- **Completion Date**: 2026-01-26
- **Type**: Code Quality, Architecture Improvement

## Problem Statement

During a recent session, we discovered that the review process was writing files directly to `.cortex/` directory instead of using Cortex MCP tools. This led to:

1. **Duplicate file issue**: `code-review-report-2026-01-15.md` appeared in both `.cortex/` root (deprecated) and `.cortex/reviews/` (correct location)
2. **Inconsistent path usage**: Review prompt was instructing AI agents to write files directly instead of using MCP tools
3. **Missing structure integration**: `reviews` directory not included in structure config or path resolver

**Root Cause**: The review process (and potentially other prompts) don't enforce MCP tool usage for `.cortex/` file operations, leading to hardcoded paths and potential inconsistencies.

## Goals

1. **Enforce MCP Tool Usage**: All file operations within `.cortex/` directory MUST use Cortex MCP tools
2. **Complete Structure Integration**: Add `reviews` directory to structure config and path resolver
3. **Prompt Audits**: Review all prompts to ensure they use MCP tools for `.cortex/` operations
4. **Code Cleanup**: Remove any remaining hardcoded paths to `.cortex/` directories
5. **Prevent Future Issues**: Add validation and documentation to prevent regression

## Context

### Current State

- ✅ `REVIEWS` added to `CortexResourceType` enum in `path_resolver.py`
- ✅ Review prompt updated to require MCP tools
- ❌ `reviews` directory not in structure config
- ❌ `get_structure_info()` doesn't include reviews path
- ❌ No dedicated MCP tool for review reports
- ❌ Other prompts may have similar issues

### Session Findings

1. **Issue**: Duplicate file `code-review-report-2026-01-15.md` in both locations
2. **Fix Applied**:
   - Removed duplicate from `.cortex/` root
   - Added `REVIEWS` to path resolver enum
   - Updated review prompt to require MCP tools
3. **User Insight**: "All file accesses within `.cortex` must be performed via Cortex MCP tools"

## Implementation Steps

### Step 1: Add Reviews to Structure Config

**Goal**: Integrate `reviews` directory into structure configuration

**Tasks**:

1. Update `DEFAULT_STRUCTURE` in `src/cortex/structure/structure_config.py`:
   - Add `"reviews": "reviews"` to `layout` dictionary
2. Update `get_structure_info()` in `src/cortex/tools/phase8_structure.py`:
   - Add `reviews` path to `paths` dictionary
   - Add `reviews` existence check to `exists` dictionary
3. Update structure setup in `src/cortex/structure/lifecycle/setup.py`:
   - Add reviews directory to `_get_required_directory_list()`
4. Add tests for reviews directory in structure tests

**Success Criteria**:

- `get_structure_info()` returns reviews path
- Structure setup creates reviews directory
- All tests passing

**Estimated Effort**: 2-3 hours

### Step 2: Audit All Prompts for MCP Tool Usage

**Goal**: Ensure all prompts use MCP tools for `.cortex/` file operations

**Tasks**:

1. Search all prompts in `.cortex/synapse/prompts/` for:
   - Hardcoded `.cortex/` paths
   - Direct file write instructions
   - Missing MCP tool requirements
2. Review each prompt:
   - `review.md` - ✅ Already updated
   - `create-plan.md` - Check for hardcoded paths
   - `commit.md` - Check for hardcoded paths
   - `implement-next-roadmap-step.md` - Check for hardcoded paths
   - `validate-roadmap-sync.md` - Check for hardcoded paths
   - Any other prompts that write to `.cortex/`
3. Update prompts to:
   - Require MCP tools for `.cortex/` operations
   - Use `get_structure_info()` for path resolution
   - Use appropriate MCP tools (`manage_file()`, etc.)
4. Add tooling notes to all prompts that touch `.cortex/` files

**Success Criteria**:

- All prompts use MCP tools for `.cortex/` operations
- No hardcoded paths in prompts
- Clear tooling notes in all relevant prompts

**Estimated Effort**: 3-4 hours

### Step 3: Create Review Report MCP Tool (Optional)

**Goal**: Provide dedicated MCP tool for review reports

**Tasks**:

1. Evaluate if dedicated tool is needed:
   - Current approach: Use `Write` tool with path from `get_structure_info()`
   - Alternative: Create `save_review_report()` MCP tool
2. If creating tool:
   - Add to appropriate tool module (e.g., `phase8_structure.py` or new module)
   - Tool should:
     - Accept report content and date
     - Use path resolver to get reviews directory
     - Create directory if needed
     - Write file with proper naming
     - Return success/error status
3. Update review prompt to use new tool (if created)

**Success Criteria**:

- Decision made on tool approach
- If tool created: fully tested and documented
- Review prompt updated to use tool

**Estimated Effort**: 2-3 hours (if tool is created)

### Step 4: Code Cleanup - Remove Hardcoded Paths

**Goal**: Remove any remaining hardcoded `.cortex/` paths in codebase

**Tasks**:

1. Search codebase for hardcoded `.cortex/` paths:
   - `grep -r "\.cortex/" src/`
   - `grep -r "\.cursor/" src/` (check for hardcoded symlink paths)
2. Review each occurrence:
   - Replace with `get_cortex_path()` calls
   - Use `get_structure_info()` for dynamic paths
   - Use appropriate MCP tools
3. Update tests to use path resolver
4. Verify no regressions

**Success Criteria**:

- No hardcoded `.cortex/` paths in source code
- All paths obtained dynamically
- All tests passing

**Estimated Effort**: 2-3 hours

### Step 5: Add Validation and Documentation

**Goal**: Prevent future regressions and document requirements

**Tasks**:

1. Add validation to commit workflow:
   - Check for hardcoded `.cortex/` paths in prompts
   - Verify MCP tool usage in prompts
2. Update documentation:
   - Add section to `AGENTS.md` about MCP tool requirements
   - Document path resolution best practices
   - Add examples of correct vs incorrect approaches
3. Update workspace rules:
   - Add rule about MCP tool usage for `.cortex/` operations
   - Add rule about path resolution

**Success Criteria**:

- Validation in place
- Documentation updated
- Rules updated

**Estimated Effort**: 2-3 hours

## Dependencies

- **Phase 20: Code Review Fixes** - Some overlap with file size violations
- **Phase 14: Centralize Path Resolution** - Builds on path resolver work

## Technical Design

### Path Resolution Pattern

**Correct Approach**:

```python
# In prompts/tools:
1. Call `get_structure_info(project_root=None)` MCP tool
2. Extract path from response: `structure_info.paths.reviews`
3. Construct file path: `{reviews_path}/code-review-report-YYYY-MM-DD.md`
4. Use `Write` tool with constructed path
```

**Incorrect Approach**:

```python
# ❌ DON'T DO THIS:
- Hardcode `.cortex/reviews/code-review-report-2026-01-15.md`
- Use direct file writes without MCP tools
- Assume directory structure
```

### Structure Config Update

```python
DEFAULT_STRUCTURE = {
    "layout": {
        "root": ".cortex",
        "memory_bank": "memory-bank",
        "rules": "rules",
        "plans": "plans",
        "config": "config",
        "archived": "archived",
        "reviews": "reviews",  # NEW
    },
    # ...
}
```

## Testing Strategy

1. **Unit Tests**:
   - Test structure config includes reviews
   - Test `get_structure_info()` returns reviews path
   - Test path resolver with REVIEWS type

2. **Integration Tests**:
   - Test review prompt creates files in correct location
   - Test structure setup creates reviews directory
   - Test prompts use MCP tools correctly

3. **Validation Tests**:
   - Test commit workflow detects hardcoded paths
   - Test validation catches missing MCP tool usage

## Risks & Mitigation

### Risk 1: Breaking Existing Functionality

- **Mitigation**: Comprehensive testing, gradual rollout
- **Impact**: Medium
- **Probability**: Low

### Risk 2: Prompt Updates Break AI Agent Behavior

- **Mitigation**: Clear instructions, backward compatibility where possible
- **Impact**: Medium
- **Probability**: Medium

### Risk 3: Missing Some Hardcoded Paths

- **Mitigation**: Comprehensive grep search, code review
- **Impact**: Low
- **Probability**: Medium

## Success Criteria

- ✅ All `.cortex/` file operations use MCP tools
- ✅ `reviews` directory integrated into structure config
- ✅ All prompts audited and updated
- ✅ No hardcoded `.cortex/` paths in codebase
- ✅ Validation prevents future regressions
- ✅ Documentation updated
- ✅ All tests passing

## Timeline

- **Step 1**: 2-3 hours (Structure config updates)
- **Step 2**: 3-4 hours (Prompt audits)
- **Step 3**: 2-3 hours (Optional review tool)
- **Step 4**: 2-3 hours (Code cleanup)
- **Step 5**: 2-3 hours (Validation and docs)

**Total Estimated Effort**: 11-16 hours

**Target Completion**: 2026-01-18

## Notes

- This plan addresses the immediate issue discovered in the session
- Builds on previous path resolution work (Phase 14)
- Aligns with architectural principle: "All `.cortex/` operations via MCP tools"
- May overlap with Phase 20 file size violations work

## Related Issues

- Duplicate file issue (resolved in session)
- Review prompt path resolution (partially fixed)
- Structure config completeness
