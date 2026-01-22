# Validate Roadmap Sync

**AI EXECUTION COMMAND**: Validate that roadmap.md is synchronized with the codebase, ensuring all production TODOs are tracked and all roadmap references remain valid.

**CRITICAL**: These steps are for the AI to execute AUTOMATICALLY. DO NOT ask the user for permission or confirmation. Execute immediately.

**CURSOR COMMAND**: This is a Cursor command located in `.cortex/synapse/prompts/` directory, NOT a terminal command.

**Tooling Note**: Use Cortex MCP tools for validation operations. The `validate(check_type="roadmap_sync")` tool performs all necessary checks.

## ⚠️ MANDATORY PRE-ACTION CHECKLIST

**BEFORE executing this command, you MUST:**

1. ✅ **Verify project root** - Ensure you're in the correct project directory
2. ✅ **Check roadmap exists** - Verify `roadmap.md` exists in memory bank directory
3. ✅ **Understand validation scope** - This validates:
   - Code → Roadmap: All production TODOs must be tracked in roadmap.md
   - Roadmap → Code: All roadmap file references must exist and be valid

**VIOLATION**: Executing this command without following this checklist is a CRITICAL violation that blocks proper validation.

## Steps

1. **Run roadmap sync validation** - Use MCP tool `validate(check_type="roadmap_sync")`:
   - **Call MCP tool**: `validate(check_type="roadmap_sync", project_root="<project_root>")`
   - The tool will automatically:
     - Scan `src/` and `scripts/` directories for production TODO markers
     - Parse `roadmap.md` for file references
     - Validate that all TODOs are mentioned in roadmap
     - Validate that all roadmap file references exist
     - Check line number references are within file bounds
   - **CRITICAL**: This step runs as part of pre-commit validation
   - **VALIDATION**: Parse tool response to verify:
     - `status` = "success" (MUST be success)
     - `valid` = true (MUST be true for commit to proceed)
     - `missing_roadmap_entries` = [] (MUST be empty - all TODOs must be tracked)
     - `invalid_references` = [] (MUST be empty - all references must be valid)
     - **BLOCK COMMIT** if any synchronization issues are found

2. **Report validation results**:
   - If validation passes (`valid = true`):
     - Report success: "Roadmap synchronization validation passed"
     - All production TODOs are tracked in roadmap.md
     - All roadmap references are valid
   - If validation fails (`valid = false`):
     - **BLOCK COMMIT** and report failures:
     - List all missing roadmap entries (TODOs not tracked):
       - For each entry: `file_path:line - snippet`
       - Example: `src/cortex/tools/pre_commit_tools.py:56 - # TODO: Add other language adapters`
     - List all invalid references (roadmap entries pointing to missing files):
       - For each reference: `file_path:line - context`
       - Example: `src/cortex/core/old_module.py:42 - See old_module.py:42 for details`
     - List all warnings (line numbers exceeding file length, etc.)
     - Provide actionable guidance:
       - For missing entries: "Add roadmap entries for all production TODOs"
       - For invalid references: "Update or remove roadmap references to non-existent files"

3. **Fix synchronization issues** (if validation failed):
   - **For missing roadmap entries**:
     - Read `roadmap.md` using `manage_file(file_name="roadmap.md", operation="read")`
     - Add appropriate roadmap entries for each missing TODO
     - Ensure entries include file path and context
     - Re-run validation after fixes
   - **For invalid references**:
     - Update roadmap.md to remove or fix invalid file references
     - If file was renamed, update reference to new path
     - If file was deleted, remove the roadmap entry or update context
     - Re-run validation after fixes

4. **Re-verify after fixes**:
   - Run validation again: `validate(check_type="roadmap_sync")`
   - Ensure `valid = true` before proceeding with commit
   - All issues must be resolved before commit can proceed

## Success Criteria

The roadmap sync validation is considered successful when:

- ✅ `status` = "success" (validation tool executed successfully)
- ✅ `valid` = true (no synchronization issues found)
- ✅ `missing_roadmap_entries` = [] (all production TODOs are tracked)
- ✅ `invalid_references` = [] (all roadmap references are valid)
- ✅ Warnings (if any) are non-blocking and documented

## Error Handling

If validation fails:

- **BLOCK COMMIT** - Do not proceed with commit until all issues are resolved
- **Report detailed errors** - List all missing entries and invalid references
- **Provide actionable guidance** - Explain how to fix each issue
- **Re-run after fixes** - Verify all issues are resolved before allowing commit

## Notes

- This validation ensures roadmap.md remains a reliable source of truth
- Production TODOs are defined as TODO markers in `src/` and `scripts/` directories, excluding test/example files
- Roadmap references are detected via file path patterns (e.g., `src/file.py` or `src/file.py:123`)
- Line number references are validated to ensure they don't exceed file length
- This validation is **MANDATORY** for commits - commits are blocked if validation fails

## Integration with Commit Workflow

This command is called automatically by the commit workflow (Step 10):

- Commit workflow checks if `.cortex/prompts/validate-roadmap-sync.md` exists
- If file exists, workflow executes all steps from this command
- If validation fails, commit is blocked until issues are resolved
- This ensures roadmap stays synchronized with codebase automatically
