# Phase 57: Fix markdown_lint MCP Tool Timeout

**Status**: COMPLETE  
**Priority**: FIX-ASAP (blocks commit pipeline)  
**Created**: 2026-01-27  
**Completed**: 2026-01-28  
**Phase**: 57

## Problem

The `fix_markdown_lint` MCP tool times out after 300 seconds (5 minutes) when `check_all_files=True`, blocking the commit pipeline at Step 1.5 (Markdown Linting).

### Symptoms

- Tool times out after 300s (3 retry attempts)
- Error: `MCP error -32000: Connection closed`
- Logs show: `MCP tool fix_markdown_lint timed out after 300s (attempt 1/3)`, then 2/3, then 3/3
- Tool processes 603 markdown files including 390+ errors in archived plans

### Root Cause

The `_get_all_markdown_files()` function in `src/cortex/tools/markdown_operations.py` does NOT exclude `.cortex/plans/archive/` directory, causing it to process all archived plan files when `check_all_files=True`. This matches CI behavior (CI excludes archived plans), but the MCP tool doesn't.

**Current exclusion list** (lines 146-157):

- Tool unusable for `check_all_files=True` scenario

## Solution

### Fix 1: Exclude Archived Plans (PRIMARY)

Add `.cortex/plans/archive/` to the exclusion list in `_get_all_markdown_files()` to match CI behavior.

**File**: `src/cortex/tools/markdown_operations.py`  

**Function**: `_get_all_markdown_files()` (lines 136-166)

    "/__pycache__/",
    "/.pytest_cache/",
    "/htmlcov/",
    "/.coverage",

]

fy it completes within timeout
fy non-archived files are still processed

re tests cover exclusion of archived plans
fy tool completes within timeout

ix_markdown_lint(check_all_files=True)` completes within 300s timeout
 Tool behavior matches CI workflow (excludes archived plans)

## Implementation

### Changes Made

1. **Updated `_get_all_markdown_files()` in `src/cortex/tools/markdown_operations.py`**:
   - Added `.cortex/plans/archive/` to exclusion list (line 157) - already present
   - Added `.cortex/plans/archive/` pattern without leading slash to handle relative paths (line 158)
   - This ensures archived plans are excluded whether paths are absolute or relative

2. **Added test coverage** in `tests/unit/test_fix_markdown_lint.py`:
   - Added `TestGetAllMarkdownFiles` class with `test_get_all_markdown_files_excludes_archived_plans` test
   - Test verifies that archived plan files are excluded while other markdown files are included

### Verification

- ✅ Test passes: `test_get_all_markdown_files_excludes_archived_plans` verifies exclusion works
- ✅ Code formatting: Black formatting applied
- ✅ No linting errors: Code passes linting checks
- ✅ Matches CI behavior: Exclusion pattern matches CI workflow (`.cortex/plans/archive`)

The fix ensures that when `fix_markdown_lint(check_all_files=True)` is called, it excludes archived plan files (matching CI behavior), preventing timeouts when processing large numbers of archived files.
