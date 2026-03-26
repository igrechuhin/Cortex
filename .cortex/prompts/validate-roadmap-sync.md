# Validate Roadmap Sync

**AI EXECUTION COMMAND**: Validate that roadmap.md is synchronized with the codebase **and** the plans directory, ensuring all production TODOs are tracked, all roadmap references remain valid, and all non-archived plan files are registered in roadmap.md.

## Severity Levels

- ⛔ **GATE**: Blocks commit. Validation must pass.
- ✅ **CHECK**: Requires verification. Confirm before proceeding.
- ⚠️ **PREFER**: Best practice. Recommended but non-blocking.

## Status legend (scan-friendly)

- ✅ **Success** (passed / complete)
- ⚠️ **Warning** (non-blocking; proceed but report)
- ❌ **Error** (blocking; must fix before proceeding)
- ⛔ **Hard gate** (rule violation if skipped)

Execute all steps AUTOMATICALLY. DO NOT ask the user for permission.

**CURSOR COMMAND**: This is a Cursor command (e.g. in `.cortex/prompts/validate-roadmap-sync.md`). NOT a terminal command.

**Tooling Note**: Use Cortex MCP tools for validation operations. The `validate(check_type="roadmap_sync")` tool performs all necessary checks.

## Roadmap vs activeContext (responsibilities)

- **roadmap.md** = **future/upcoming work only** (blockers, active work, future enhancements, pending plans). No completed work.
- **activeContext.md** = **completed work only**. No in-progress or future work.
- **No overlap**: Do not duplicate the same work in both files. When work completes, move it from roadmap to activeContext.

This command validates **roadmap.md only**. It does not validate activeContext.md. Roadmap file references (e.g. `.cortex/plans/*.md`, `src/...`) must point to existing files, and every non-archived plan file under `.cortex/plans` must have a corresponding roadmap entry. Completed-work sections (e.g. "Recent Findings", "Completed Milestones") belong in activeContext; if they appear in roadmap.md, treat that as outdated content and fix by moving or removing them so roadmap contains only future/upcoming items.

## ⚠️ MANDATORY PRE-ACTION CHECKLIST

**BEFORE executing this command, you MUST:**

1. ✅ **Verify project root** - Ensure you're in the correct project directory
2. ✅ **Check roadmap exists** - Verify `roadmap.md` exists in memory bank directory (e.g. via `get_structure_info()` then check `paths.memory_bank` / `paths.memory_bank_root`)
3. ✅ **Understand validation scope** - This validates:
   - Code → Roadmap: All production TODOs must be tracked in roadmap.md
   - Roadmap → Code: All file references in roadmap.md must exist and be valid (roadmap = future work only; references are typically plan paths and source files)
   - Plans ↔ Roadmap: All **non-archived** plan files under `.cortex/plans` must be referenced in roadmap.md (no orphan plans), and all roadmap plan references must point to existing plan files

⛔ **VIOLATION**: Executing this command without following this checklist is a CRITICAL violation that blocks proper validation.

## Steps

1. **Run roadmap sync validation** - Use MCP tool `validate(check_type="roadmap_sync")`:
   - **Call MCP tool**: `validate(check_type="roadmap_sync")`. The server resolves the project root (workspace/repo) automatically.
   - The tool will automatically:
     - Scan `src/` and `scripts/` directories for production TODO markers
     - Parse `roadmap.md` for file references
     - Validate that all TODOs are mentioned in roadmap
     - Validate that all roadmap file references exist
     - Validate that all non-archived plan files under `.cortex/plans` are referenced in roadmap.md
     - Check line number references are within file bounds
   - **CRITICAL**: This step runs as part of pre-commit validation
   - **VALIDATION**: Parse tool response to verify:
     - `status` = "success" (MUST be success)
     - `valid` = true (MUST be true for commit to proceed)
     - `missing_roadmap_entries` = [] (MUST be empty - all TODOs must be tracked)
     - `invalid_references` = [] (MUST be empty - all references must be valid)
     - `unlinked_plans` = [] (MUST be empty - all non-archived plans are registered in roadmap.md)
     - **BLOCK COMMIT** if any synchronization issues are found

2. **Report validation results**:
   - If validation passes (`valid = true`):
     - ✅ Report success: "Roadmap synchronization validation passed"
     - All production TODOs are tracked in roadmap.md
     - All roadmap references are valid
   - If validation fails (`valid = false`):
     - ❌ **BLOCK COMMIT** and report failures:
     - List all missing roadmap entries (TODOs not tracked):
       - For each entry: `file_path:line - snippet`
       - Example: `src/cortex/tools/pre_commit_tools.py:56 - # TODO: Add other language adapters`
     - List all invalid references (roadmap entries pointing to missing files):
       - For each reference: `file_path:line - context`
       - Example: `src/cortex/core/old_module.py:42 - See old_module.py:42 for details`
     - List all unlinked plans (plan files that exist under `.cortex/plans` but are not referenced in roadmap.md):
       - For each plan: path relative to project root (e.g. `.cortex/plans/phase-68-investigate-fix-quality-issues-mcp-connection-closed.md`)
     - List all warnings (line numbers exceeding file length, etc.)
     - Provide actionable guidance:
       - For missing entries: "Add roadmap entries for all production TODOs"
       - For invalid references: "Update or remove roadmap references to non-existent files; if references are from completed-work sections (e.g. Recent Findings, Completed Milestones), move that content to activeContext.md and keep roadmap.md for future/upcoming work only"
       - For unlinked plans: "For each non-archived plan file under `.cortex/plans`, either (a) add a corresponding roadmap entry in the appropriate section (Blockers / Active Work / Pending plans), or (b) archive/delete the plan if it is obsolete; roadmap and plans must be in sync in both directions"

3. **Fix synchronization issues** (if validation failed):
   - **For missing roadmap entries**:
     - Read `roadmap.md` using `manage_file(file_name="roadmap.md", operation="read")` (or Cortex MCP tools for path resolution).
     - Add appropriate roadmap entries for each missing TODO (under Future Enhancements or Pending plans as appropriate).
     - Ensure entries include file path and context.
     - Re-run validation after fixes.
   - **For invalid references**:
     - If the invalid references come from **completed-work** sections (e.g. "Recent Findings", "Completed Milestones") that should not be in roadmap: move that content to activeContext.md and remove those sections from roadmap.md so roadmap contains only future/upcoming work.
     - Otherwise: update roadmap.md to remove or fix invalid file references; if a file was renamed, update the reference; if deleted, remove the roadmap entry or update context.
     - Re-run validation after fixes.
   - **For unlinked plans**:
     - Decide whether each unlinked plan is still relevant:
       - If yes: add a roadmap entry linking to the plan in the correct section (e.g. Blockers (ASAP Priority), Active Work, or Pending plans), preserving roadmap ordering semantics.
       - If no: move the plan under the `archive/` subtree or remove it according to project conventions.
     - Ensure that after adjustments, every non-archived plan has at least one roadmap entry and that there are no stale plans left unattached to roadmap.md.
     - Re-run validation after fixes.

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
- ✅ `unlinked_plans` = [] (all non-archived plan files under `.cortex/plans` are registered in roadmap.md)
- ✅ Warnings (if any) are non-blocking and documented

## Error Handling

If validation fails:

- ❌ **BLOCK COMMIT** - Do not proceed with commit until all issues are resolved
- ❌ **Report detailed errors** - List all missing entries and invalid references
- ✅ **Provide actionable guidance** - Explain how to fix each issue
- ✅ **Re-run after fixes** - Verify all issues are resolved before allowing commit

## Notes

- **roadmap.md** = future/upcoming work only; **activeContext.md** = completed work only. This command validates roadmap.md only.
- This validation ensures roadmap.md remains a reliable source of truth for planned work and that its file references are valid.
- Production TODOs are defined as TODO markers in `src/` and `scripts/` directories, excluding test/example files.
- Roadmap references are detected via file path patterns (e.g. `.cortex/plans/foo.md`, `src/file.py` or `src/file.py:123`). All referenced files must exist.
- Line number references are validated to ensure they don't exceed file length.
- The server resolves the project root automatically; no need to pass it.
- This validation is **MANDATORY** for commits - commits are blocked if validation fails.

## Integration with Commit Workflow

This command is called automatically by the commit workflow (Step 10):

- Commit workflow checks if `.cortex/prompts/validate-roadmap-sync.md` exists
- If file exists, workflow executes all steps from this command
- If validation fails, commit is blocked until issues are resolved
- This ensures roadmap stays synchronized with codebase automatically
