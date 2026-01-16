# Phase 26: Unify Cache Directory Structure

## Status

- **Status**: PLANNING
- **Priority**: Medium
- **Start Date**: 2026-01-16
- **Type**: Refactoring/Infrastructure

## Goal

Refactor Cortex MCP tools to use a unified cache directory (`.cortex/.cache`) instead of the current task-specific cache directory (`.cortex/summaries`). This will provide a centralized location for all caching needs across Cortex MCP tools, making it easier to manage, clean, and extend caching functionality.

## Context

Currently, the `SummarizationEngine` uses `.cortex/summaries` as its cache directory. As Cortex grows and more tools require caching (e.g., relevance scoring, pattern analysis, refactoring suggestions), having separate cache directories for each tool creates maintenance overhead and inconsistency.

**Current State:**

- `SummarizationEngine` uses `.cortex/summaries` for summary caching
- Cache files stored as: `{file_name}.{strategy}.{content_hash}.json`
- No centralized cache management or utilities

**Target State:**

- All Cortex MCP tools use `.cortex/.cache` as the unified cache directory
- Cache files organized by tool/feature (e.g., `.cache/summaries/`, `.cache/relevance/`, etc.)
- Centralized cache utilities for common operations
- Path resolution via `CortexResourceType.CACHE` enum

## Approach

1. **Add CACHE to path resolver**: Extend `CortexResourceType` enum to include `CACHE`
2. **Update SummarizationEngine**: Change from `.cortex/summaries` to `.cortex/.cache/summaries`
3. **Create cache utilities**: Add helper functions for cache management (clear, size, cleanup)
4. **Update tests**: Fix all test references to use new cache path
5. **Documentation**: Update docs to reflect unified cache structure
6. **Migration**: Handle existing cache files if any exist

## Implementation Steps

### Step 1: Extend Path Resolver

**File**: `src/cortex/core/path_resolver.py`

- Add `CACHE = ".cache"` to `CortexResourceType` enum
- Update `get_cortex_path()` to handle `CortexResourceType.CACHE`
- Add helper function `get_cache_path(project_root: Path, cache_type: str | None = None) -> Path`:
  - Returns `.cortex/.cache` if `cache_type` is None
  - Returns `.cortex/.cache/{cache_type}` if `cache_type` is provided
  - Example: `get_cache_path(root, "summaries")` → `.cortex/.cache/summaries`

**Dependencies**: None

**Testing**:

- Test `CortexResourceType.CACHE` enum value
- Test `get_cortex_path()` with `CortexResourceType.CACHE`
- Test `get_cache_path()` with and without cache_type parameter

### Step 2: Update SummarizationEngine

**File**: `src/cortex/optimization/summarization_engine.py`

- Import `get_cache_path` from `cortex.core.path_resolver`
- Update `__init__` method:
  - Change default cache_dir from `.cortex/summaries` to `.cortex/.cache/summaries`
  - Use `get_cache_path(Path(metadata_index.project_root), "summaries")` as default
  - Keep support for custom `cache_dir` parameter for testing flexibility
- Update cache file paths to use subdirectory structure:
  - Current: `cache_dir / f"{file_name}.{strategy}.{content_hash}.json"`
  - Keep same format (no change needed, subdirectory already handled)

**Dependencies**: Step 1

**Testing**:

- Test default cache directory uses `.cortex/.cache/summaries`
- Test custom cache directory still works
- Test cache file creation in new location
- Test cache retrieval from new location

### Step 3: Create Cache Utilities Module

**File**: `src/cortex/core/cache_utils.py` (new file)

Create utility functions for cache management:

```python
def get_cache_dir(project_root: Path, cache_type: str | None = None) -> Path:
    """Get cache directory path."""
    
def clear_cache(project_root: Path, cache_type: str | None = None) -> int:
    """Clear cache files. Returns number of files deleted."""
    
def get_cache_size(project_root: Path, cache_type: str | None = None) -> int:
    """Get total cache size in bytes."""
    
def list_cache_files(project_root: Path, cache_type: str | None = None) -> list[Path]:
    """List all cache files."""
```

**Dependencies**: Step 1

**Testing**:

- Test `get_cache_dir()` with various cache types
- Test `clear_cache()` removes files correctly
- Test `get_cache_size()` calculates correctly
- Test `list_cache_files()` returns correct files

### Step 4: Update All Tests

**Files**:

- `tests/unit/test_summarization_engine.py`
- Any other tests that reference `.cortex/summaries`

**Changes**:

- Update test assertions to expect `.cortex/.cache/summaries` instead of `.cortex/summaries`
- Update test fixtures to use new cache path
- Ensure all tests pass with new cache structure

**Dependencies**: Steps 1-2

**Testing**:

- Run full test suite for summarization engine
- Verify no test failures related to cache paths

### Step 5: Update Documentation

**Files**:

- `README.md` - Add `.cache` to directory structure documentation
- `docs/guides/configuration.md` - Document cache directory structure
- `docs/api/tools.md` - Update cache-related tool documentation

**Changes**:

- Document `.cortex/.cache` as unified cache directory
- Explain cache organization by tool/feature
- Document cache utilities and cleanup procedures

**Dependencies**: Steps 1-3

### Step 6: Handle Migration (if needed)

**File**: `src/cortex/core/migration.py` or new migration utility

**Changes**:

- Check if `.cortex/summaries` exists
- If exists, migrate cache files to `.cortex/.cache/summaries`
- Remove old `.cortex/summaries` directory after migration
- Log migration activity

**Dependencies**: Steps 1-2

**Testing**:

- Test migration from old to new cache structure
- Test that migrated files are accessible
- Test that old directory is cleaned up

## Technical Design

### Cache Directory Structure

```
.cortex/
├── .cache/                    # Unified cache directory
│   ├── summaries/             # SummarizationEngine cache
│   │   └── {file}.{strategy}.{hash}.json
│   ├── relevance/             # Future: Relevance scoring cache
│   ├── patterns/              # Future: Pattern analysis cache
│   └── refactoring/           # Future: Refactoring suggestions cache
├── memory-bank/
├── plans/
└── ...
```

### Path Resolution Pattern

```python
from cortex.core.path_resolver import get_cache_path, CortexResourceType

# Get base cache directory
cache_dir = get_cortex_path(project_root, CortexResourceType.CACHE)

# Get specific cache subdirectory
summaries_cache = get_cache_path(project_root, "summaries")
```

### Backward Compatibility

- Custom `cache_dir` parameter in `SummarizationEngine` remains supported
- Migration utility handles existing cache files
- No breaking changes to public API

## Dependencies

- **Path Resolver**: Must be updated first (Step 1)
- **SummarizationEngine**: Depends on Step 1
- **Tests**: Depends on Steps 1-2
- **Documentation**: Depends on Steps 1-3

## Success Criteria

- ✅ `CortexResourceType.CACHE` added to path resolver
- ✅ `SummarizationEngine` uses `.cortex/.cache/summaries` by default
- ✅ All tests pass with new cache structure
- ✅ Cache utilities module created and tested
- ✅ Documentation updated with new cache structure
- ✅ Migration utility handles existing cache files (if any)
- ✅ No breaking changes to public API
- ✅ Code quality checks pass (file size, function length, type hints)

## Testing Strategy

### Unit Tests

- **Path Resolver**: Test `CortexResourceType.CACHE` and `get_cache_path()`
- **SummarizationEngine**: Test cache directory initialization and file operations
- **Cache Utils**: Test all utility functions (get, clear, size, list)

### Integration Tests

- Test cache file creation and retrieval in new location
- Test migration from old to new cache structure
- Test cache cleanup operations

### Manual Testing

- Verify cache files created in `.cortex/.cache/summaries`
- Verify cache retrieval works correctly
- Verify migration handles existing files

## Risks & Mitigation

### Risk 1: Breaking Existing Cache Files

**Mitigation**:

- Migration utility automatically moves existing files
- Check for existing cache before migration
- Preserve file contents during migration

### Risk 2: Test Failures Due to Path Changes

**Mitigation**:

- Update all test assertions systematically
- Run full test suite after each step
- Use test fixtures for consistent cache paths

### Risk 3: Performance Impact from Subdirectory Structure

**Mitigation**:

- Subdirectory structure is minimal overhead
- Cache operations remain O(1) for file access
- No significant performance impact expected

## Timeline

- **Step 1**: 1 hour (path resolver extension)
- **Step 2**: 1 hour (SummarizationEngine update)
- **Step 3**: 2 hours (cache utilities creation)
- **Step 4**: 1 hour (test updates)
- **Step 5**: 1 hour (documentation)
- **Step 6**: 1 hour (migration utility)

**Total Estimated Time**: 7 hours

## Notes

- The `.cache` directory uses a leading dot to indicate it's a hidden/cache directory (following common conventions)
- Cache subdirectories are organized by tool/feature for easy management
- Future tools can easily add their own cache subdirectories
- Cache utilities provide common operations for all cache types
- Migration is automatic and transparent to users

## Future Enhancements

- Add cache size limits and automatic cleanup
- Add cache TTL (time-to-live) support
- Add cache statistics and monitoring
- Add cache compression for large files
- Add cache encryption for sensitive data
