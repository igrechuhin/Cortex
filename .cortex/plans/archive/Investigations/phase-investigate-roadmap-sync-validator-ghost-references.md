# Phase: Investigate Roadmap Sync Validator Ghost References

## Status

- Initial status: Planning

## Goal

Investigate and fix why the roadmap sync validator (`validate(check_type="roadmap_sync")`) reports 32 invalid references in "Recent Findings" and "Completed Milestones" sections that do not exist in the current `roadmap.md` file. This is blocking commits and causing confusion.

## Context

During roadmap sync validation on 2026-02-04, the validator reported:

- **32 invalid references** in phases "Recent Findings" and "Completed Milestones"
- References include files like `config_status.py`, `prompts.py`, `phase5_execution.py`, etc.
- Context snippets show completed work markers (✅) and references to archived plans

**Critical Finding**: The current `roadmap.md` file:

- Does NOT contain "Recent Findings" or "Completed Milestones" sections
- Contains only: Blockers, Active Work, Future Enhancements, and Pending plans sections
- Has 62 file references total, but NONE match the invalid references reported by the validator
- The sections "Recent Findings" and "Completed Milestones" appear to be from an older version of the roadmap that was moved to `activeContext.md`

**Evidence**:

- Manual grep of `roadmap.md` shows no matches for "Recent Findings" or "Completed Milestones"
- Manual regex search finds 62 file references, none matching the reported invalid ones
- The validator consistently reports the same 32 invalid references across multiple runs
- Both `.cortex/memory-bank/roadmap.md` and the `roadmap.md` reached via the IDE `memory-bank` symlink are identical (no diff)

**Impact**:

- Commits are blocked because `valid: false` is returned
- The validator appears to be reading from a cached/stale version or there's a parsing bug
- This prevents legitimate commits and creates confusion

## Approach

1. **Investigate file reading path** - Verify what content the validator actually receives
2. **Check for caching issues** - Investigate if `FileSystemManager.read_file()` caches content
3. **Examine parsing logic** - Verify `parse_roadmap_references()` isn't finding false positives
4. **Check for symlink/version issues** - Verify the validator reads from the correct file
5. **Add debugging/logging** - Instrument the validator to see what content it's parsing
6. **Fix root cause** - Address the underlying issue (caching, parsing bug, or file reading bug)
7. **Add regression tests** - Ensure this doesn't happen again

## Implementation Steps

### Step 1: Reproduce and Document the Issue

1.1 **Run validation and capture full output**

- Call `validate(check_type="roadmap_sync")` multiple times
- Capture the exact JSON response with all invalid references
- Document the context snippets and phase names reported

1.2 **Verify current roadmap.md content**

- Read `roadmap.md` via `manage_file()` and via direct file read
- Confirm no "Recent Findings" or "Completed Milestones" sections exist
- Document all actual sections and file references present

1.3 **Check roadmap history**

- Review `.cortex/history/roadmap_v*.md` files
- Identify when "Recent Findings" and "Completed Milestones" sections existed
- Determine if validator might be reading from a history file

### Step 2: Investigate File Reading Path

2.1 **Add debug logging to `handle_roadmap_sync_validation()`**

- Log the file path being read
- Log file size and modification time
- Log first 500 characters of content read
- Log whether file exists and is readable

2.2 **Verify FileSystemManager.read_file() behavior**

- Check if `read_file()` caches content
- Verify it reads from the correct path
- Check for any async/await issues that might cause stale reads

2.3 **Compare file reads**

- Read roadmap via `fs_manager.read_file()` (as validator does)
- Read roadmap via direct `Path.read_text()`
- Compare content byte-by-byte to ensure they match

### Step 3: Investigate Parsing Logic

3.1 **Test `parse_roadmap_references()` with actual roadmap content**

- Pass current `roadmap.md` content to `parse_roadmap_references()`
- Verify it only finds references that actually exist
- Check if regex pattern is matching unintended text

3.2 **Check phase tracking logic**

- Verify `current_phase` tracking in `parse_roadmap_references()`
- Ensure it's not persisting phase state incorrectly
- Check if phase names are being matched incorrectly

3.3 **Examine regex pattern**

- Test the file reference regex pattern: `r"`?([a-zA-Z0-9_./-]+\.(py|md|ts|js|tsx|jsx|go|rs|java|kt))(?::(\d+))?`?`
- Verify it's not matching false positives
- Check if it's matching content from other files or cached content

### Step 4: Check for Caching or Stale Content Issues

4.1 **Investigate FileSystemManager caching**

- Review `FileSystemManager` implementation for any caching mechanisms
- Check if file content is cached between reads
- Verify file modification time checks

4.2 **Check for symlink issues**

- Verify the `memory-bank` symlink under `.cursor/` resolves `roadmap.md` to the canonical file
- Check if validator might be reading from wrong location
- Ensure path resolution is correct

4.3 **Check for version/index issues**

- Review `.cortex/index.json` for roadmap metadata
- Check if validator reads from index instead of file
- Verify no stale metadata is being used

### Step 5: Add Instrumentation and Debugging

5.1 **Add detailed logging to validation flow**

- Log roadmap content length and hash before parsing
- Log number of references found and their phases
- Log each invalid reference with full context

5.2 **Create test that reproduces the issue**

- Write a test that uses actual current `roadmap.md` content
- Verify it reproduces the ghost references
- Use this test to validate the fix

5.3 **Add content validation**

- Before parsing, verify roadmap content doesn't contain "Recent Findings"
- Log a warning if unexpected sections are found
- Add assertion to fail if ghost sections detected

### Step 6: Fix Root Cause

6.1 **Identify the bug**

- Based on investigation, determine root cause:
  - Caching issue in FileSystemManager
  - Parsing bug finding false positives
  - Reading from wrong file/location
  - Stale content from another source

6.2 **Implement fix**

- Fix caching if that's the issue (clear cache, add invalidation)
- Fix parsing logic if regex is wrong
- Fix file reading path if reading from wrong location
- Add safeguards to prevent similar issues

6.3 **Verify fix**

- Run validation again and confirm `valid: true`
- Verify no ghost references are reported
- Confirm all actual references are still validated correctly

### Step 7: Add Regression Tests

7.1 **Add test for current roadmap content**

- Test that validation passes with current `roadmap.md`
- Verify no false positives for non-existent sections
- Ensure all actual references are validated

7.2 **Add test for section detection**

- Test that validator correctly identifies roadmap sections
- Verify phase tracking works correctly
- Ensure completed-work sections aren't parsed if they don't exist

7.3 **Add test for file reading**

- Test that validator reads from correct file
- Verify no caching causes stale reads
- Ensure file modification time is checked

7.4 **Add integration test**

- Test full validation flow end-to-end
- Verify commit workflow can proceed when validation passes
- Ensure validation blocks commits when it should

## Dependencies

- Existing `validate` MCP tool and roadmap sync validation modules
- `FileSystemManager` for file reading
- `parse_roadmap_references()` parsing logic
- Current `roadmap.md` file structure

## Testing Strategy (MANDATORY, ≥95% Coverage for New Code)

- **Coverage Target**: Achieve at least 95% coverage for all new or modified validation and debugging code.

- **Unit Tests**:
  - Test `parse_roadmap_references()` with various roadmap content (including current content)
  - Test phase tracking logic with different section structures
  - Test file reference regex pattern with edge cases
  - Test `handle_roadmap_sync_validation()` with mocked file reads
  - Verify no false positives for non-existent sections

- **Integration Tests**:
  - Test full validation flow with actual current `roadmap.md`
  - Test validation with roadmap containing "Recent Findings" section (should work correctly)
  - Test validation with roadmap without those sections (current case)
  - Verify file reading path is correct

- **Edge Cases**:
  - Empty roadmap content
  - Roadmap with only section headers
  - Roadmap with malformed references
  - Roadmap with very long content
  - Concurrent validation calls (check for race conditions)

- **Regression Tests**:
  - Ensure existing validation behavior is preserved
  - Verify legitimate invalid references are still caught
  - Ensure TODO tracking still works correctly
  - Lock in correct behavior for current roadmap structure

## Risks & Mitigations

- **Risk**: Fix might break legitimate validation for other roadmaps
  - **Mitigation**: Add comprehensive tests covering various roadmap structures; verify fix doesn't affect correct validation

- **Risk**: Root cause might be complex (multiple issues)
  - **Mitigation**: Investigate systematically, document findings, fix incrementally with tests at each step

- **Risk**: Adding logging might impact performance
  - **Mitigation**: Use conditional logging (debug mode), keep logs concise, remove debug logs after fix is verified

- **Risk**: Fix might not address the actual root cause
  - **Mitigation**: Thorough investigation before fixing, add instrumentation to verify fix works, monitor for recurrence

## Timeline (Rough)

- **Day 1**: Steps 1-2 (Reproduce issue, investigate file reading)
- **Day 2**: Steps 3-4 (Investigate parsing, check caching)
- **Day 3**: Steps 5-6 (Add instrumentation, fix root cause)
- **Day 4**: Step 7 (Add regression tests, verify fix)

## Success Criteria

- ✅ Validator no longer reports ghost references from non-existent sections
- ✅ Validation passes (`valid: true`) with current `roadmap.md`
- ✅ All actual invalid references are still correctly detected
- ✅ Root cause is identified and fixed
- ✅ Regression tests prevent similar issues
- ✅ Commits are no longer blocked by false validation failures

## Notes

- This is a critical blocker that prevents commits
- The validator appears to be reading stale/cached content or has a parsing bug
- Investigation should be thorough to prevent recurrence
- Consider adding content hash validation to detect stale reads
