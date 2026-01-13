# Phase 14: Centralize Path Resolution Using Path Resolver

## Status

- **Status**: 🔴 PENDING - High Priority
- **Priority**: High (Code Quality & Maintainability)
- **Start Date**: 2026-01-13
- **Type**: Refactoring

## Problem Statement

The codebase has a centralized path resolver (`src/cortex/core/path_resolver.py`) that provides `get_cortex_path()` for consistent path resolution, but many locations still use direct path construction like `root / ".cortex" / "memory-bank"` instead of the centralized resolver.

### Current State

- **Path Resolver**: Exists and provides `get_cortex_path(project_root, CortexResourceType)` ✅
- **Current Usage**: Only used in:
  - `src/cortex/tools/phase1_foundation_rollback.py` (1 location) ✅
  - `tests/helpers/path_helpers.py` (test utilities) ✅
- **Direct Path Construction**: Found 24+ instances across multiple files ❌

### Issue Details

**Direct Path Construction Locations:**

1. **`src/cortex/tools/validation_operations.py`** (5 instances):
   - Line 38: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 66: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 85: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 132: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 166: `memory_bank_dir = root / ".cortex" / "memory-bank"`

2. **`src/cortex/tools/phase2_linking.py`** (4 instances):
   - Line 135: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 365: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 616: `memory_bank_dir = root / ".cortex" / "memory-bank"`
   - Line 820: `memory_bank_dir = root / ".cortex" / "memory-bank"`

3. **`src/cortex/tools/file_operations.py`** (2 instances):
   - Line 276: `(root / ".cortex" / "memory-bank").glob("*.md")`
   - Line 560: `memory_bank_dir = root / ".cortex" / "memory-bank"`

4. **`src/cortex/managers/container_factory.py`** (2 instances):
   - Line 160: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 172: `memory_bank_path = project_root / ".cortex" / "memory-bank"`

5. **`src/cortex/managers/initialization.py`** (8 instances):
   - Line 555: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 576: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 587: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 600: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 621: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 642: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 661: `memory_bank_path = project_root / ".cortex" / "memory-bank"`
   - Line 681: `memory_bank_path = project_root / ".cortex" / "memory-bank"`

6. **`src/cortex/analysis/structure_analyzer.py`** (2 instances):
   - Line 57: `memory_bank_dir = self.project_root / ".cortex" / "memory-bank"`
   - Line 314: `memory_bank_dir = self.project_root / ".cortex" / "memory-bank"`

7. **`src/cortex/core/file_system.py`** (1 instance):
   - Line 43: `self.memory_bank_dir: Path = self.project_root / ".cortex" / "memory-bank"`

**Impact:**
- Inconsistent path resolution across codebase
- Harder to maintain if path structure changes
- Violates DRY principle
- Risk of path resolution bugs (as seen in Phase 13)
- Makes it harder to support alternative directory structures

## Solution

Replace all direct path constructions with centralized `get_cortex_path()` calls.

### Implementation Strategy

#### Phase 1: Core Infrastructure (Foundation)
1. **Verify Path Resolver Completeness**
   - [ ] Ensure `CortexResourceType` enum covers all needed resource types
   - [ ] Verify `get_cortex_path()` handles all cases correctly
   - [ ] Check if any additional resource types need to be added

2. **Update Core Managers**
   - [ ] Fix `src/cortex/core/file_system.py` (1 instance)
   - [ ] Fix `src/cortex/managers/initialization.py` (8 instances)
   - [ ] Fix `src/cortex/managers/container_factory.py` (2 instances)
   - **Impact**: Core infrastructure uses centralized resolver

#### Phase 2: MCP Tools (User-Facing)
3. **Update MCP Tool Files**
   - [ ] Fix `src/cortex/tools/file_operations.py` (2 instances)
   - [ ] Fix `src/cortex/tools/phase2_linking.py` (4 instances)
   - [ ] Fix `src/cortex/tools/validation_operations.py` (5 instances)
   - **Impact**: All MCP tools use consistent path resolution

#### Phase 3: Analysis & Structure (Internal)
4. **Update Analysis Tools**
   - [ ] Fix `src/cortex/analysis/structure_analyzer.py` (2 instances)
   - **Impact**: Analysis tools use centralized resolver

#### Phase 4: Testing & Validation
5. **Add Tests**
   - [ ] Add unit tests for path resolver usage in each fixed module
   - [ ] Add integration tests to verify path resolution consistency
   - [ ] Add regression tests to prevent future direct path construction
   - [ ] Verify all existing tests still pass

6. **Code Quality Checks**
   - [ ] Add linting rule to detect direct path construction (if possible)
   - [ ] Update code review guidelines to prefer path resolver
   - [ ] Document path resolver usage in coding standards

#### Phase 5: Documentation & Cleanup
7. **Update Documentation**
   - [ ] Update coding standards to mandate path resolver usage
   - [ ] Add examples of correct path resolution in developer docs
   - [ ] Update ADRs if path resolution is architectural decision

8. **Final Verification**
   - [ ] Run full test suite
   - [ ] Verify no regressions
   - [ ] Check code coverage for path resolver usage
   - [ ] Verify all direct path constructions replaced

## Implementation Details

### Pattern to Replace

**Before:**
```python
memory_bank_dir = root / ".cortex" / "memory-bank"
# or
memory_bank_path = project_root / ".cortex" / "memory-bank"
# or
memory_bank_dir = self.project_root / ".cortex" / "memory-bank"
```

**After:**
```python
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
# or
memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
# or
memory_bank_dir = get_cortex_path(self.project_root, CortexResourceType.MEMORY_BANK)
```

### Special Cases

1. **FileSystemManager** (`file_system.py`):
   - Instance variable initialization in `__init__`
   - Should use path resolver for consistency

2. **Manager Initialization** (`initialization.py`):
   - Multiple manager creation functions
   - All should use path resolver

3. **Glob Patterns** (`file_operations.py` line 276):
   - `(root / ".cortex" / "memory-bank").glob("*.md")`
   - Should become: `get_cortex_path(root, CortexResourceType.MEMORY_BANK).glob("*.md")`

## Success Criteria

- ✅ All 24+ direct path constructions replaced with `get_cortex_path()` calls
- ✅ All imports added: `from cortex.core.path_resolver import CortexResourceType, get_cortex_path`
- ✅ All tests pass (100% pass rate)
- ✅ Code coverage maintained or improved
- ✅ No regressions in functionality
- ✅ Consistent path resolution across entire codebase
- ✅ Documentation updated with path resolver usage guidelines

## Testing Strategy

### Unit Tests
- Test each module after refactoring to verify path resolution
- Test path resolver with different project root configurations
- Test edge cases (missing directories, symlinks, etc.)

### Integration Tests
- Test end-to-end Memory Bank operations
- Test MCP tools with path resolver
- Verify consistency across all tools

### Regression Tests
- Add tests that detect direct path construction
- Add linting rules if possible
- Document in code review checklist

## Risk Mitigation

1. **Incremental Changes**: Fix one file at a time, test, then move to next
2. **Test Coverage**: Ensure high test coverage before refactoring
3. **Backward Compatibility**: Path resolver should produce same paths as direct construction
4. **Code Review**: Review each change carefully to ensure correctness

## Related Files

- `src/cortex/core/path_resolver.py` - Centralized path resolver (reference implementation)
- `tests/helpers/path_helpers.py` - Test utilities using path resolver (reference usage)
- `src/cortex/tools/phase1_foundation_rollback.py` - Example of correct usage

## Dependencies

- Path resolver must be complete and tested
- All resource types must be defined in `CortexResourceType` enum
- Test infrastructure must support path resolver testing

## Estimated Effort

- **Phase 1 (Core)**: 2-3 hours
- **Phase 2 (Tools)**: 2-3 hours
- **Phase 3 (Analysis)**: 1 hour
- **Phase 4 (Testing)**: 3-4 hours
- **Phase 5 (Documentation)**: 1-2 hours

**Total**: 9-13 hours (1-2 days)

## Notes

- This refactoring improves code maintainability and reduces risk of path resolution bugs
- Follows DRY principle by centralizing path resolution logic
- Makes it easier to support alternative directory structures in the future
- Aligns with existing test helper patterns that already use path resolver
