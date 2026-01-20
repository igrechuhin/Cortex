# Phase 31: Fix optimize_context Stale File Errors

**Status:** Planning  
**Priority:** ASAP  
**Created:** 2026-01-16  
**Target Completion:** 2026-01-17

## Goal

Fix the `optimize_context` MCP tool errors where it attempts to read non-existent files from the memory bank, causing retry exhaustion warnings. The tool is trying to access files that are listed in the metadata index but don't exist on disk, leading to unnecessary retry attempts and error logging.

## Context

**Error Logs Analysis:**

From the MCP server logs (lines 98-176), the `optimize_context` tool is failing with retry exhaustion errors:

```text
2026-01-16 14:36:46,175 - cortex.core.retry - WARNING - Transient error, retrying in 0.60s (attempt 1/3): [Errno 2] No such file or directory: '/Users/i.grechukhin/Repo/Cortex/.cortex/memory-bank/test_verification.md'
...
2026-01-16 14:36:49,435 - cortex.core.retry - ERROR - Retry exhausted after 3 attempts: [Errno 2] No such file or directory: '/Users/i.grechukhin/Repo/Cortex/.cortex/memory-bank/test_verification.md'
```

**Files Causing Errors:**

1. `test_verification.md` - Missing file, 3 retry attempts
2. `test_links.md` - Missing file, 3 retry attempts  
3. `tool-verification-summary-2026-01-13.md` - Missing file, 3 retry attempts

**Root Cause Analysis:**

1. **Metadata Index Contains Stale Entries**: The `MetadataIndex.list_all_files()` method returns files that are in the index JSON but no longer exist on disk. These are likely leftover entries from previous test runs or temporary files that were deleted.

2. **Retry Logic Treats FileNotFoundError as Transient**: The `FileSystemManager.read_file()` method uses `retry_async()` with `exceptions=(OSError, IOError, PermissionError)`. Since `FileNotFoundError` is a subclass of `OSError`, it gets retried 3 times even though the file doesn't exist.

3. **No Existence Check Before Reading**: The `_read_all_files_for_optimization()` function in `phase4_context_operations.py` doesn't check if files exist before attempting to read them. It relies on catching `FileNotFoundError`, but the retry logic executes before the exception is caught.

4. **No Index Cleanup Mechanism**: There's no automatic cleanup of stale entries from the metadata index when files are deleted.

**Impact:**

- Unnecessary retry attempts (3 per missing file = 9 total retries)
- Error log pollution with retry warnings and exhaustion errors
- Potential performance degradation from retry delays
- Poor user experience with confusing error messages
- Metadata index inconsistency (index doesn't match actual files)

**Current Code Flow:**

1. `optimize_context` tool called
2. `_read_all_files_for_optimization()` gets file list from `metadata_index.list_all_files()`
3. For each file, calls `fs_manager.read_file(file_path)`
4. `read_file()` uses `retry_async()` which retries `OSError` (includes `FileNotFoundError`)
5. Retry logic logs warnings and retries 3 times before raising exception
6. Exception caught in `_read_all_files_for_optimization()` and skipped with `continue`
7. Process continues but with error logs

## Approach

**Multi-Layered Solution:**

1. **Immediate Fix**: Check file existence before reading to avoid retries for known non-existent files
2. **Index Validation**: Add validation to check metadata index consistency and clean stale entries
3. **Retry Logic Improvement**: Exclude `FileNotFoundError` from retries when file existence is known
4. **Preventive Measures**: Add validation when updating metadata index to prevent adding non-existent files
5. **Cleanup Tool**: Add mechanism to clean up stale entries from metadata index

## Implementation Steps

### Step 1: Fix Immediate Retry Issue in optimize_context

**File:** `src/cortex/tools/phase4_context_operations.py`

**Changes:**

1. **Check file existence before reading**:
   - Use `metadata_index.get_file_metadata(file_name)` to check if file has `exists: false` flag
   - Or check `file_path.exists()` before calling `read_file()`
   - Skip files that don't exist to avoid retry attempts

2. **Update `_read_all_files_for_optimization()` function**:

   ```python
   for file_name in all_files:
       file_path = metadata_index.memory_bank_dir / file_name
       
       # Check if file exists before attempting to read
       if not file_path.exists():
           # Check metadata to see if file was marked as non-existent
           metadata = await metadata_index.get_file_metadata(file_name)
           if metadata and metadata.get("exists", True):
               # File was in index but doesn't exist - stale entry
               # Log warning and skip
               logger.warning(f"Skipping stale index entry: {file_name}")
           continue
       
       try:
           content, _ = await fs_manager.read_file(file_path)
           files_content[file_name] = content
           # ... rest of logic
   ```

**Testing:**

- Add unit test for `_read_all_files_for_optimization()` with stale index entries
- Verify no retry attempts for non-existent files
- Verify files are skipped gracefully

### Step 2: Improve FileSystemManager.read_file() Retry Logic

**File:** `src/cortex/core/file_system.py`

**Changes:**

1. **Add optional `check_exists` parameter**:
   - When `check_exists=True`, check file existence before retrying
   - Skip retries for `FileNotFoundError` when file is known not to exist

2. **Update `read_file()` method**:

   ```python
   async def read_file(
       self, 
       file_path: Path, 
       check_exists: bool = False
   ) -> tuple[str, str]:
       """Read file content and compute hash with retry logic.
       
       Args:
           file_path: Path to file to read
           check_exists: If True, check existence before retrying FileNotFoundError
       
       Returns:
           Tuple of (content, sha256_hash)
       """
       # Check existence if requested
       if check_exists and not file_path.exists():
           raise FileNotFoundError(f"File not found: {file_path}")
       
       async def read_operation() -> tuple[str, str]:
           # ... existing logic
       
       # Exclude FileNotFoundError from retries if check_exists was True
       exceptions = (OSError, IOError, PermissionError)
       if check_exists:
           # Filter out FileNotFoundError from retries
           exceptions = tuple(e for e in exceptions if e is not FileNotFoundError)
       
       return await retry_async(
           read_operation,
           max_retries=3,
           base_delay=0.5,
           exceptions=exceptions,
       )
   ```

**Alternative Approach (Simpler):**

- Don't retry `FileNotFoundError` at all in `read_file()` since file existence is deterministic
- Only retry for transient errors (permission issues, I/O errors during read)

**Testing:**

- Add unit test for `read_file()` with non-existent file
- Verify no retries for `FileNotFoundError`
- Verify retries still work for transient errors

### Step 3: Add Metadata Index Validation and Cleanup

**File:** `src/cortex/core/metadata_index.py`

**Changes:**

1. **Add `validate_index_consistency()` method**:
   - Check all files in index against actual filesystem
   - Identify stale entries (in index but not on disk)
   - Return list of stale file names

2. **Add `cleanup_stale_entries()` method**:
   - Remove stale entries from index
   - Update index metadata
   - Log cleanup actions

3. **Add `file_exists_in_index()` check**:
   - Check if file exists in index before adding
   - Validate file exists on disk when updating metadata

**Implementation:**

```python
async def validate_index_consistency(self) -> list[str]:
    """Validate index consistency with filesystem.
    
    Returns:
        List of stale file names (in index but not on disk)
    """
    if self._data is None:
        await self.load()
    
    stale_files: list[str] = []
    files_dict = self._data.get("files", {})
    
    for file_name in files_dict.keys():
        file_path = self.memory_bank_dir / file_name
        if not file_path.exists():
            stale_files.append(file_name)
    
    return stale_files

async def cleanup_stale_entries(self, dry_run: bool = False) -> int:
    """Remove stale entries from index.
    
    Args:
        dry_run: If True, only report what would be cleaned
    
    Returns:
        Number of entries cleaned
    """
    stale_files = await self.validate_index_consistency()
    
    if not stale_files:
        return 0
    
    if dry_run:
        logger.info(f"Would clean {len(stale_files)} stale entries: {stale_files}")
        return len(stale_files)
    
    # Remove stale entries
    for file_name in stale_files:
        if file_name in self._data.get("files", {}):
            del self._data["files"][file_name]
            logger.info(f"Removed stale index entry: {file_name}")
    
    await self.save()
    return len(stale_files)
```

**Testing:**

- Add unit tests for `validate_index_consistency()`
- Add unit tests for `cleanup_stale_entries()`
- Test with mix of existing and stale entries

### Step 4: Update Metadata Index Update Logic

**File:** `src/cortex/core/metadata_index.py`

**Changes:**

1. **Validate file existence in `update_file_metadata()`**:
   - Check if file exists on disk before updating metadata
   - Set `exists: false` flag if file doesn't exist
   - Log warning for non-existent files

2. **Add validation in file operations**:
   - When files are deleted, remove from index
   - When files are created, add to index with `exists: true`

**Implementation:**

```python
async def update_file_metadata(
    self,
    file_name: str,
    path: Path,
    exists: bool | None = None,  # Allow explicit setting
    # ... other parameters
):
    """Update metadata for a file.
    
    If exists is None, check filesystem.
    """
    if exists is None:
        exists = path.exists()
    
    if not exists:
        logger.warning(f"Updating metadata for non-existent file: {file_name}")
    
    # ... rest of update logic
```

**Testing:**

- Add unit test for updating metadata of non-existent file
- Verify `exists` flag is set correctly
- Test file deletion removes from index

### Step 5: Add Cleanup to optimize_context Tool

**File:** `src/cortex/tools/phase4_context_operations.py`

**Changes:**

1. **Optionally clean stale entries before optimization**:
   - Add parameter to enable cleanup
   - Call `metadata_index.cleanup_stale_entries()` if enabled
   - Log cleanup results

2. **Or automatically skip stale entries**:
   - Use existence check from Step 1
   - Skip files that don't exist without cleanup

**Testing:**

- Add integration test for optimize_context with stale entries
- Verify no errors logged
- Verify optimization works correctly

### Step 6: Add MCP Tool for Index Cleanup

**File:** `src/cortex/tools/phase1_foundation_operations.py` (or new file)

**Changes:**

1. **Add `cleanup_metadata_index` MCP tool**:
   - Allow manual cleanup of stale entries
   - Support dry-run mode
   - Return cleanup statistics

**Tool Signature:**

```python
@mcp.tool()
async def cleanup_metadata_index(
    project_root: str | None = None,
    dry_run: bool = False,
) -> str:
    """Clean up stale entries from metadata index.
    
    Args:
        project_root: Project root directory
        dry_run: If True, only report what would be cleaned
    
    Returns:
        JSON string with cleanup results
    """
```

**Testing:**

- Add unit tests for cleanup tool
- Test dry-run mode
- Test actual cleanup

### Step 7: Update Progressive Loader

**File:** `src/cortex/optimization/progressive_loader.py`

**Changes:**

1. **Apply same fixes to `_read_all_files_for_loading()`**:
   - Check file existence before reading
   - Skip stale entries gracefully

**Testing:**

- Add unit test for progressive loader with stale entries
- Verify no retry attempts

### Step 8: Add Comprehensive Tests

**Test Files:**

1. `tests/unit/test_phase4_context_operations.py`:
   - Test `_read_all_files_for_optimization()` with stale entries
   - Test no retry attempts for non-existent files
   - Test graceful handling of missing files

2. `tests/unit/test_file_system.py`:
   - Test `read_file()` with non-existent file
   - Test no retries for `FileNotFoundError`
   - Test retries still work for transient errors

3. `tests/unit/test_metadata_index.py`:
   - Test `validate_index_consistency()`
   - Test `cleanup_stale_entries()`
   - Test updating metadata for non-existent files

4. `tests/integration/test_optimize_context.py`:
   - Integration test with stale index entries
   - Verify no error logs
   - Verify optimization works correctly

## Dependencies

- **Phase 20: Code Review Fixes** - May need to coordinate if file size violations affect these files
- No blocking dependencies

## Success Criteria

1. ✅ **No Retry Errors**: `optimize_context` tool no longer logs retry warnings for non-existent files
2. ✅ **Graceful Handling**: Missing files are skipped without errors
3. ✅ **Index Consistency**: Metadata index validation and cleanup tools available
4. ✅ **Test Coverage**: Comprehensive tests for all changes (90%+ coverage maintained)
5. ✅ **No Regressions**: All existing tests pass
6. ✅ **Performance**: No performance degradation from existence checks

## Testing Strategy

### Unit Tests

- Test file existence checks before reading
- Test retry logic excludes `FileNotFoundError` appropriately
- Test metadata index validation and cleanup
- Test graceful handling of stale entries

### Integration Tests

- Test `optimize_context` with stale index entries
- Test `load_progressive_context` with stale entries
- Test cleanup tool end-to-end

### Manual Testing

1. Create test scenario with stale index entries:
   - Add files to memory bank
   - Update metadata index
   - Delete files from disk
   - Run `optimize_context` tool
   - Verify no retry errors

2. Test cleanup tool:
   - Create stale entries
   - Run cleanup in dry-run mode
   - Verify correct detection
   - Run actual cleanup
   - Verify entries removed

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Existence checks add overhead | Performance degradation | Medium | Use efficient `Path.exists()` checks, cache results if needed |
| Breaking existing functionality | Tests fail, regressions | Low | Comprehensive test coverage, careful implementation |
| Index cleanup removes valid entries | Data loss | Low | Dry-run mode, validation before cleanup, backup index |
| Retry logic changes break transient error handling | Reliability issues | Low | Only exclude `FileNotFoundError`, keep other retries |

## Timeline

- **Step 1-2**: Fix immediate retry issue (2-3 hours)
- **Step 3-4**: Add index validation and cleanup (3-4 hours)
- **Step 5-7**: Update related tools (2-3 hours)
- **Step 8**: Add comprehensive tests (3-4 hours)
- **Total**: 10-14 hours

## Notes

- The retry logic in `retry.py` treats `OSError` (which includes `FileNotFoundError`) as transient, but file existence is deterministic - if a file doesn't exist, retrying won't help
- The metadata index should be kept in sync with actual files, but there's no automatic cleanup mechanism currently
- Consider adding a background task or hook to clean up stale entries when files are deleted
- The `exists` flag in metadata could be used to skip non-existent files without filesystem checks

## Related Issues

- Similar issues may exist in other tools that read files from memory bank
- Consider audit of all file reading operations for similar problems
- Metadata index consistency should be validated periodically
