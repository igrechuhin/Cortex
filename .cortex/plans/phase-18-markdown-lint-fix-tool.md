# Phase 18: Markdown Lint Fix Tool

## Status

**Status**: Planning  
**Created**: 2026-01-14  
**Priority**: Medium  
**Estimated Effort**: 8-12 hours

## Goal

Create a tool that automatically scans all modified markdown files (git-based) in the working copy, detects markdownlint errors, and fixes them automatically. This will help maintain consistent markdown formatting across the codebase and reduce manual linting error fixes.

## Context

### Problem Statement

The project has many markdown files (memory bank files, documentation, prompts, rules) that frequently accumulate markdownlint errors such as:

- **MD024**: Multiple headings with the same content
- **MD032**: Lists should be surrounded by blank lines
- **MD009**: Trailing spaces
- **MD012**: Multiple blank lines
- **MD022**: Headings without blank lines
- **MD031**: Code blocks without blank lines
- **MD036**: Emphasis used as headings
- **MD029**: Inconsistent ordered list numbering
- **MD040**: Fenced code blocks without language tags
- **MD059**: Non-descriptive link text

These errors are detected by the IDE's markdownlint extension but require manual fixing, which is time-consuming and error-prone.

### Current State

- Project uses markdownlint for validation (`.markdownlint.json` config exists)
- Markdown formatting rules are documented in `.cortex/synapse/rules/markdown/markdown-formatting.mdc`
- No automated tool exists to fix markdownlint errors in modified files
- Manual fixing is required when errors are detected

### User Needs

1. **Automated Detection**: Automatically find all modified markdown files in the working copy
2. **Error Detection**: Run markdownlint on modified files to detect violations
3. **Auto-Fix**: Automatically fix all auto-fixable errors
4. **Reporting**: Report what files were fixed and what errors were resolved
5. **Integration**: Can be run as part of pre-commit workflow or standalone

## Approach

### High-Level Strategy

1. **Git Integration**: Use git commands to find modified markdown files in the working copy
2. **Markdownlint Integration**: Use markdownlint-cli2 (or similar) to detect and fix errors
3. **Script Implementation**: Create a Python script that orchestrates the process
4. **MCP Tool Integration**: Optionally expose as MCP tool for IDE integration
5. **Pre-commit Integration**: Integrate with existing pre-commit workflow

### Implementation Options

#### Option 1: Standalone Python Script (Recommended)

- **Location**: `scripts/fix_markdown_lint.py`
- **Dependencies**: `markdownlint-cli2` (npm package, can be called via subprocess)
- **Approach**: Python script that:
  1. Runs `git diff --name-only` to find modified files
  2. Filters for `.md` and `.mdc` files
  3. Runs `markdownlint-cli2` with `--fix` flag on each file
  4. Reports results

**Pros**:
- Simple to implement
- Easy to run standalone
- Can be integrated into pre-commit hooks
- No MCP server dependency

**Cons**:
- Requires npm/node.js for markdownlint-cli2
- Not directly accessible via MCP tools

#### Option 2: MCP Tool

- **Location**: `src/cortex/tools/markdown_tools.py`
- **Dependencies**: `markdownlint-cli2` (npm package)
- **Approach**: MCP tool that:
  1. Accepts optional file filter or uses git to find modified files
  2. Runs markdownlint with fix
  3. Returns structured results

**Pros**:
- Accessible via MCP protocol
- Can be called from IDE
- Structured JSON responses

**Cons**:
- More complex implementation
- Requires MCP server to be running
- May be overkill for simple script

#### Option 3: Hybrid Approach (Recommended)

- **Primary**: Standalone Python script in `scripts/`
- **Secondary**: Optional MCP tool wrapper that calls the script
- **Best of both worlds**: Simple script for CLI use, MCP tool for IDE integration

## Implementation Steps

### Step 1: Setup Dependencies

1. **Add markdownlint-cli2 dependency**:
   - Document npm installation requirement in README
   - Or use Python markdownlint wrapper if available
   - Check if `markdownlint-cli2` is available in PATH

2. **Verify markdownlint config**:
   - Ensure `.markdownlint.json` is properly configured
   - Review existing markdown formatting rules

### Step 2: Implement Git File Detection

1. **Create helper function** to get modified markdown files:
   ```python
   async def get_modified_markdown_files(project_root: Path) -> list[Path]:
       """Get list of modified markdown files from git."""
   ```

2. **Use git commands**:
   - `git diff --name-only` for staged + unstaged changes
   - `git diff --cached --name-only` for staged only
   - `git status --porcelain` for working copy changes
   - Filter for `.md` and `.mdc` extensions

3. **Handle edge cases**:
   - No git repository
   - No modified files
   - Untracked files (optional)

### Step 3: Implement Markdownlint Integration

1. **Create markdownlint runner**:
   ```python
   async def run_markdownlint_fix(file_path: Path, project_root: Path) -> dict[str, object]:
       """Run markdownlint --fix on a file."""
   ```

2. **Use subprocess** to call markdownlint-cli2:
   - Command: `markdownlint-cli2 --fix <file>`
   - Parse output for errors and fixes
   - Handle errors gracefully

3. **Support batch processing**:
   - Process multiple files efficiently
   - Report progress

### Step 4: Implement Main Script

1. **Create `scripts/fix_markdown_lint.py`**:
   - Parse command-line arguments (optional file filter, dry-run mode)
   - Get modified files from git
   - Run markdownlint fix on each file
   - Report results

2. **Output format**:
   - Summary: files processed, errors fixed, files unchanged
   - Per-file details: what errors were fixed
   - Exit code: 0 if all fixed, 1 if errors remain

### Step 5: Add Error Reporting

1. **Structured output**:
   - JSON output option for programmatic use
   - Human-readable summary for CLI use

2. **Error categorization**:
   - Auto-fixable errors (fixed automatically)
   - Manual-fix errors (require manual intervention)
   - Configuration errors (markdownlint not found, etc.)

### Step 6: Testing

1. **Unit tests**:
   - Test git file detection logic
   - Test markdownlint integration (mocked)
   - Test error handling

2. **Integration tests**:
   - Test with actual modified markdown files
   - Test with various error types
   - Test edge cases (no files, no git, etc.)

3. **Manual testing**:
   - Run on actual modified files
   - Verify fixes are correct
   - Verify no regressions

### Step 7: Documentation

1. **Update README**:
   - Document tool usage
   - Document dependencies (npm, markdownlint-cli2)
   - Document integration options

2. **Add docstrings**:
   - Comprehensive docstrings for all functions
   - Usage examples

### Step 8: Integration (Optional)

1. **Pre-commit hook**:
   - Add to `.git/hooks/pre-commit` or use pre-commit framework
   - Run automatically before commits

2. **MCP tool wrapper** (optional):
   - Create MCP tool that calls the script
   - Expose via `@mcp.tool()` decorator
   - Return structured JSON results

## Technical Design

### File Structure

```
scripts/
  └── fix_markdown_lint.py    # Main script

src/cortex/tools/
  └── markdown_tools.py        # Optional MCP tool wrapper
```

### Dependencies

- **markdownlint-cli2**: npm package for markdownlint with auto-fix
- **Python stdlib**: `subprocess`, `pathlib`, `asyncio` (if async)
- **Optional**: `aiofiles` for async file operations (if needed)

### Git Commands

```bash
# Get modified files (staged + unstaged)
git diff --name-only

# Get only staged files
git diff --cached --name-only

# Get working copy changes (includes untracked)
git status --porcelain | grep '^??' | cut -c4-  # untracked
git status --porcelain | grep '^ M' | cut -c4-  # modified
```

### Markdownlint Command

```bash
# Fix errors in a file
markdownlint-cli2 --fix path/to/file.md

# Check without fixing (dry-run)
markdownlint-cli2 path/to/file.md

# Use project config
markdownlint-cli2 --config .markdownlint.json --fix path/to/file.md
```

### Error Types to Fix

Based on the user's error examples:

1. **MD024** (no-duplicate-heading): Rename duplicate headings
2. **MD032** (blanks-around-lists): Add blank lines around lists
3. **MD009** (no-trailing-spaces): Remove trailing spaces
4. **MD012** (no-multiple-blank-lines): Remove extra blank lines
5. **MD022** (blanks-around-headings): Add blank lines around headings
6. **MD031** (blanks-around-fences): Add blank lines around code blocks
7. **MD036** (no-emphasis-as-heading): Convert bold text to headings (manual)
8. **MD029** (list-marker-space): Fix list numbering (manual)
9. **MD040** (fenced-code-language): Add language tags (manual)
10. **MD059** (link-fragments): Fix link text (manual)

**Note**: Some errors (MD036, MD029, MD040, MD059) may require manual fixes as they involve semantic decisions.

## Testing Strategy

### Unit Tests

1. **Git file detection**:
   - Test with mock git output
   - Test filtering for markdown files
   - Test edge cases (no files, no git repo)

2. **Markdownlint integration**:
   - Mock subprocess calls
   - Test error handling
   - Test output parsing

3. **File processing**:
   - Test file path handling
   - Test error reporting
   - Test dry-run mode

### Integration Tests

1. **End-to-end workflow**:
   - Create test markdown files with known errors
   - Run tool on test files
   - Verify fixes are applied correctly
   - Verify no regressions

2. **Git integration**:
   - Test with actual git repository
   - Test with staged and unstaged changes
   - Test with untracked files (optional)

### Manual Testing

1. **Real-world scenarios**:
   - Run on actual modified files from the project
   - Verify fixes match expected behavior
   - Check for any unexpected changes

2. **Error handling**:
   - Test with missing markdownlint
   - Test with invalid git repository
   - Test with permission errors

## Success Criteria

1. ✅ **Tool successfully detects modified markdown files** from git working copy
2. ✅ **Tool runs markdownlint** on detected files
3. ✅ **Tool automatically fixes** all auto-fixable errors (MD009, MD012, MD022, MD031, MD032)
4. ✅ **Tool reports** what files were fixed and what errors were resolved
5. ✅ **Tool handles errors gracefully** (missing dependencies, git errors, etc.)
6. ✅ **Tool has comprehensive tests** (unit + integration)
7. ✅ **Tool is documented** with usage examples
8. ✅ **Tool integrates** with existing workflows (optional pre-commit hook)

## Risks & Mitigation

### Risk 1: Markdownlint Not Available

**Risk**: Tool fails if markdownlint-cli2 is not installed.

**Mitigation**:
- Check for markdownlint availability at startup
- Provide clear error message with installation instructions
- Document dependency in README

### Risk 2: Git Not Available

**Risk**: Tool fails if git is not available or not in a git repository.

**Mitigation**:
- Check for git availability
- Check if current directory is a git repository
- Provide fallback option to specify files manually

### Risk 3: Incorrect Fixes

**Risk**: Auto-fix might introduce incorrect changes.

**Mitigation**:
- Test thoroughly with various error types
- Support dry-run mode to preview changes
- Provide detailed reporting of what was fixed
- Use version control to allow easy rollback

### Risk 4: Performance Issues

**Risk**: Tool might be slow with many files.

**Mitigation**:
- Process files in parallel (if async)
- Report progress for large batches
- Optimize git commands

## Timeline

- **Step 1-2**: Setup and git integration (2 hours)
- **Step 3-4**: Markdownlint integration and main script (3-4 hours)
- **Step 5**: Error reporting (1 hour)
- **Step 6**: Testing (2-3 hours)
- **Step 7**: Documentation (1 hour)
- **Step 8**: Integration (optional, 1-2 hours)

**Total**: 8-12 hours

## Dependencies

- **External**: markdownlint-cli2 (npm package)
- **Internal**: None (standalone script)
- **Optional**: Pre-commit framework for hook integration

## Notes

- Consider adding this tool to the commit workflow (similar to code formatting)
- May want to add as pre-commit hook to catch errors before commit
- Could be extended to support other markdown linters (e.g., markdownlint-cli)
- Consider adding configuration file for tool-specific settings

## Related Work

- [Phase 12: Convert Commit Workflow Prompts to MCP Tools](../plans/phase-12-commit-workflow-mcp-tools.md) - Commit workflow improvements
- [Markdown Formatting Rules](../synapse/rules/markdown/markdown-formatting.mdc) - Existing markdown formatting standards
- `.markdownlint.json` - Existing markdownlint configuration
