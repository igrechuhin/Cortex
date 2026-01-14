# Plan: Conditional Prompt Registration Based on Project Configuration

## Problem Statement

Currently, all MCP prompts (including one-time setup/migration prompts) are always registered when the MCP server starts. For properly configured projects, this pollutes the prompts list with unnecessary setup prompts that are no longer relevant.

## Goal

Only show setup/migration prompts when the project is NOT properly configured. For correctly configured projects, only show prompts that make sense for active development.

## Setup/Migration Prompts to Conditionally Register

Based on README.md:180-200, these prompts should only appear when needed:

### Setup Prompts (only if not configured)

- `initialize_memory_bank` - Only if memory bank doesn't exist
- `setup_project_structure` - Only if `.cortex/` structure doesn't exist
- `setup_cursor_integration` - Only if Cursor integration not configured
- `setup_shared_rules` (setup_synapse) - Always available (optional feature)

### Migration Prompts (only if migration needed)

- `check_migration_status` - Only if legacy format detected
- `migrate_memory_bank` - Only if migration needed
- `migrate_project_structure` - Only if migration needed

## Implementation Approach

### Phase 1: Create Configuration Status Checker

**File**: `src/cortex/tools/prompts.py` (or new helper module)

Create a synchronous function to check project configuration status at import time:

```python
def get_project_config_status() -> dict[str, bool]:
    """Check project configuration status synchronously at import time.
    
    Returns:
        Dictionary with status flags:
        - memory_bank_initialized: bool
        - structure_configured: bool
        - cursor_integration_configured: bool
        - migration_needed: bool
    """
```

**Requirements**:

- Must be synchronous (runs at import time, before async context)
- Must work from any working directory (walk up to find project root)
- Use existing `get_project_root()` from `cortex.managers.initialization` (already handles walking up directory tree)
- Must detect:
  - Memory bank exists at `.cortex/memory-bank/` with core files
  - `.cortex/` structure exists (directories: memory-bank, rules, plans, config)
  - Cursor integration configured (symlinks exist and are valid)
  - Legacy formats that need migration

### Phase 2: Conditional Prompt Registration

**File**: `src/cortex/tools/prompts.py`

Modify prompt registration to be conditional:

1. Check configuration status at module import time
2. Only register setup prompts if corresponding configuration is missing
3. Only register migration prompts if migration is needed
4. Always register `setup_synapse` (optional feature)

**Implementation Pattern**:

```python
# At module level (after status check)
_config_status = get_project_config_status()

# Conditional registration
if not _config_status["memory_bank_initialized"]:
    @mcp.prompt()
    def initialize_memory_bank() -> str:
        ...

if not _config_status["structure_configured"]:
    @mcp.prompt()
    def setup_project_structure() -> str:
        ...

if not _config_status["cursor_integration_configured"]:
    @mcp.prompt()
    def setup_cursor_integration() -> str:
        ...

if _config_status["migration_needed"]:
    @mcp.prompt()
    def check_migration_status() -> str:
        ...
    
    @mcp.prompt()
    def migrate_memory_bank() -> str:
        ...
    
    @mcp.prompt()
    def migrate_project_structure() -> str:
        ...

# Always available (optional feature)
@mcp.prompt()
def setup_synapse(synapse_repo_url: str) -> str:
    ...
```

### Phase 3: Configuration Detection Logic

**Detection Criteria**:

1. **Memory Bank Initialized**:
   - `.cortex/memory-bank/` directory exists
   - At least core files exist (projectBrief.md, productContext.md, activeContext.md, systemPatterns.md, techContext.md, progress.md, roadmap.md)

2. **Structure Configured**:
   - `.cortex/` directory exists
   - Required subdirectories exist: `memory-bank/`, `rules/`, `plans/`, `config/`
   - Structure config file exists at `.cortex/config/structure.json` (optional check)

3. **Cursor Integration Configured**:
   - `.cursor/` directory exists
   - Symlinks exist: `.cursor/memory-bank -> ../.cortex/memory-bank`
   - Symlinks are valid (not broken)

4. **Migration Needed**:
   - Legacy format detected:
     - `.cursor/memory-bank/` exists (old Cursor-centric format)
     - `memory-bank/` exists at root (root-level format)
     - `.memory-bank/` exists (old standardized format)
   - AND `.cortex/memory-bank/` does NOT exist (not yet migrated)

### Phase 4: Testing Strategy

**Test Cases**:

1. **Fresh Project** (no configuration):
   - All setup prompts should be registered
   - No migration prompts

2. **Properly Configured Project**:
   - No setup prompts registered
   - No migration prompts registered
   - Only active development prompts available

3. **Partially Configured Project**:
   - Only missing setup prompts registered
   - Example: Memory bank exists but structure incomplete

4. **Legacy Format Project**:
   - Migration prompts registered
   - Setup prompts may also be registered if structure incomplete

5. **Mixed State** (legacy + partial new):
   - Both migration and setup prompts as needed

**Test Files**:

- `tests/unit/test_prompts_conditional_registration.py` - Unit tests for status detection
- `tests/integration/test_prompts_registration.py` - Integration tests for prompt availability

### Phase 5: Edge Cases and Error Handling

**Edge Cases**:

- Project root detection fails (walk up directory tree)
- Permissions issues (can't read directories)
- Symlink resolution failures
- Concurrent access (multiple MCP instances)

**Error Handling**:

- Default to showing all prompts if status check fails (fail-safe)
- Log warnings if status check encounters errors
- Don't crash server if status check fails

### Phase 6: Documentation Updates

**Files to Update**:

- `README.md` - Update prompt sections to explain conditional availability
- `docs/prompts/README.md` - Document when prompts appear
- `CLAUDE.md` - Update prompt availability guidance

## Implementation Steps

1. ✅ Create plan document
2. Create `get_project_config_status()` function
3. Add unit tests for status detection
4. Modify `prompts.py` for conditional registration
5. Add integration tests
6. Update documentation
7. Test with various project states
8. Verify no regressions in existing functionality

## Success Criteria

- ✅ Setup prompts only appear when project is not configured
- ✅ Migration prompts only appear when migration is needed
- ✅ Properly configured projects have clean prompt list
- ✅ No breaking changes to existing functionality
- ✅ All tests pass
- ✅ Documentation updated

## Notes

- Status check must be synchronous (runs at import time)
- FastMCP requires decorators at module level, so conditional logic must be at import time
- Consider caching status check result to avoid repeated filesystem operations
- Status check should be fast (<100ms) to not slow down server startup
