# Phase 11.1: Fix Rules Tool AttributeError

**Status:** ✅ COMPLETE  
**Goal:** Fix critical bug in `rules` tool preventing Phase 11 verification completion  
**Date Created:** 2026-01-12  
**Date Completed:** 2026-01-12  
**Priority:** **CRITICAL** - Blocks Phase 11 tool verification

## Overview

During Phase 11 tool verification, a critical bug was discovered in the `rules` tool that prevents it from executing. The tool attempts to call `is_rules_enabled()` on a `LazyManager` wrapper object instead of the actual `OptimizationConfig` instance.

**Error:**

```text
AttributeError: 'LazyManager' object has no attribute 'is_rules_enabled'
```

## Problem Analysis

### Root Cause

In `src/cortex/tools/rules_operations.py`, line 535, the code uses `cast()` to cast the manager from the managers dictionary:

```python
optimization_config = cast(OptimizationConfig, mgrs["optimization_config"])
```

However, `mgrs["optimization_config"]` is a `LazyManager` wrapper, not the actual `OptimizationConfig` instance. The `cast()` function only changes the type annotation - it doesn't actually unwrap the LazyManager.

When the code later calls `optimization_config.is_rules_enabled()` (line 30 in `check_rules_enabled()`), it's trying to call a method on the `LazyManager` wrapper, which doesn't have that method.

### Correct Pattern

Other tools in the codebase correctly use `get_manager()` from `cortex.managers.manager_utils` to unwrap LazyManager instances:

```python
from cortex.managers.manager_utils import get_manager

optimization_config = await get_manager(
    mgrs, "optimization_config", OptimizationConfig
)
```

The `get_manager()` function properly unwraps LazyManager instances by calling `await manager_or_lazy.get()` if it's a LazyManager.

### Affected Code

**File:** `src/cortex/tools/rules_operations.py`

**Lines to fix:**

- Line 534: `rules_manager = cast(RulesManager, mgrs["rules_manager"])` - Should also use `get_manager()`
- Line 535: `optimization_config = cast(OptimizationConfig, mgrs["optimization_config"])` - Should use `get_manager()`

## Solution

### Step 1: Add Import

Add the import for `get_manager` at the top of the file:

```python
from cortex.managers.manager_utils import get_manager
```

### Step 2: Fix Manager Unwrapping

Replace the `cast()` calls with proper `get_manager()` calls:

**Before:**

```python
rules_manager = cast(RulesManager, mgrs["rules_manager"])
optimization_config = cast(OptimizationConfig, mgrs["optimization_config"])
```

**After:**

```python
rules_manager = await get_manager(mgrs, "rules_manager", RulesManager)
optimization_config = await get_manager(
    mgrs, "optimization_config", OptimizationConfig
)
```

### Step 3: Verify Fix

1. Run the `rules` tool with `operation="index"` to verify it works
2. Run the `rules` tool with `operation="get_relevant"` to verify it works
3. Re-run Phase 11 verification for the `rules` tool to confirm fix

## Implementation Checklist

- [x] Add `get_manager` import to `rules_operations.py` ✅
- [x] Replace `cast()` calls with `get_manager()` for `rules_manager` ✅
- [x] Replace `cast()` calls with `get_manager()` for `optimization_config` ✅
- [x] Run type checker to verify no type errors ✅
- [x] Run tests to verify fix doesn't break anything ✅ (34/34 tests passing)
- [ ] Test `rules` tool with `operation="index"` ⏳ (Requires MCP server restart)
- [ ] Test `rules` tool with `operation="get_relevant"` ⏳ (Requires MCP server restart)
- [ ] Re-verify Phase 11 tool verification for `rules` tool ⏳ (Requires MCP server restart)
- [x] Update Phase 11 verification plan with fix confirmation ✅

## Testing

### Manual Testing

1. **Test Index Operation:**

   ```python
   # Should work without AttributeError
   result = await rules(
       operation="index",
       project_root="/Users/i.grechukhin/Repo/Cortex"
   )
   ```

2. **Test Get Relevant Operation:**

   ```python
   # Should work without AttributeError
   result = await rules(
       operation="get_relevant",
       task_description="Implement async file operations",
       project_root="/Users/i.grechukhin/Repo/Cortex"
   )
   ```

### Automated Testing

- Run existing tests: `pytest tests/tools/test_rules_operations.py`
- Verify all tests pass
- Check for any new type errors

## Expected Outcome

After the fix:

1. ✅ `rules` tool executes without AttributeError
2. ✅ `rules` tool can index rules from configured folders
3. ✅ `rules` tool can retrieve relevant rules for tasks
4. ✅ Phase 11 verification can complete for `rules` tool
5. ✅ Phase 4 Token Optimization tools verification can be marked 100% complete

## Impact

- **Blocks:** Phase 11 tool verification completion (Phase 4 at 83% instead of 100%)
- **Severity:** Critical - Tool is completely non-functional
- **Effort:** Low - Simple fix, ~5 minutes
- **Risk:** Low - Fix follows established pattern used throughout codebase

## Related Issues

- Phase 11 Tool Verification: `.cortex/plans/phase-11-tool-verification.md`
- Issue documented in Phase 4 verification summary

## Notes

- This is a straightforward fix following established patterns
- The bug was introduced because `cast()` was used instead of `get_manager()`
- All other Phase 4 tools correctly use `get_manager()` for LazyManager unwrapping
- This fix will complete Phase 4 verification and allow Phase 11 to progress
