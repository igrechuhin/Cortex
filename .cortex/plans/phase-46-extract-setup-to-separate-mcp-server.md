# Phase 46: Extract Setup Logic to Separate MCP Server

## Status

Planning

## Goal

Extract setup-related logic (prompts, tools, and initialization) into a separate FastMCP server and dynamically mount it when required, based on FastMCP's server composition capabilities.

## Context

### Current State

Setup logic is currently integrated into the main Cortex MCP server:

1. **Setup Prompts** (in `src/cortex/tools/prompts.py`):
   - `initialize_memory_bank` - Conditionally registered if memory bank not initialized
   - `setup_project_structure` - Conditionally registered if structure not configured
   - `setup_cursor_integration` - Conditionally registered if Cursor integration not configured
   - `setup_synapse` - Always available (optional feature)
   - `populate_tiktoken_cache` - Conditionally registered if cache not available

2. **Migration Prompts** (in `src/cortex/tools/prompts.py`):
   - `check_migration_status` - Conditionally registered if migration needed
   - `migrate_memory_bank` - Conditionally registered if migration needed
   - `migrate_project_structure` - Conditionally registered if migration needed

3. **Structure Tools** (in `src/cortex/tools/phase8_structure.py`):
   - `check_structure_health` - Always available
   - `get_structure_info` - Always available

4. **Configuration Status** (in `src/cortex/tools/config_status.py`):
   - `get_project_config_status()` - Synchronous function used at import time

5. **Manager Initialization** (in `src/cortex/managers/initialization.py`):
   - `get_managers()` - Lazy loading of managers
   - `initialize_managers()` - Eager initialization
   - `_post_init_setup()` - Post-initialization setup tasks

### FastMCP Server Composition

Based on [FastMCP documentation](https://gofastmcp.com/servers/composition#importing-vs-mounting):

- **`import_server`**: Static composition - copies components at startup, changes to subserver after import are not reflected
- **`mount`**: Dynamic composition - creates live link, changes to subserver are immediately reflected, supports runtime delegation

Since setup logic is conditional and should only be available when needed, **`mount`** is the appropriate choice for dynamic composition.

## Benefits of Extraction

1. **Cleaner Main Server**: Main Cortex server focuses on core functionality, setup logic is separated
2. **Conditional Availability**: Setup tools/prompts only available when needed (not initialized projects)
3. **Better Organization**: Setup logic grouped in dedicated server module
4. **Easier Maintenance**: Setup-related changes isolated from core functionality
5. **Protocol Compliance**: Aligns with FastMCP best practices for server composition
6. **Performance**: Setup server only loaded when needed (lazy mounting)

## Implementation Approach

### Step 1: Create Setup MCP Server Module

Create `src/cortex/setup/server.py`:

```python
from fastmcp import FastMCP

# Setup MCP server instance
setup_mcp = FastMCP("cortex-setup")
```

### Step 2: Extract Setup Prompts

Move setup prompts from `src/cortex/tools/prompts.py` to `src/cortex/setup/prompts.py`:

- `initialize_memory_bank`
- `setup_project_structure`
- `setup_cursor_integration`
- `setup_synapse`
- `populate_tiktoken_cache`
- `check_migration_status`
- `migrate_memory_bank`
- `migrate_project_structure`

All prompts should use `@setup_mcp.prompt()` decorator instead of `@mcp.prompt()`.

### Step 3: Extract Setup Tools

Move structure tools from `src/cortex/tools/phase8_structure.py` to `src/cortex/setup/tools.py`:

- `check_structure_health`
- `get_structure_info`

Tools should use `@setup_mcp.tool()` decorator.

### Step 4: Create Setup Server Initialization

Create `src/cortex/setup/__init__.py` that:

- Imports setup prompts and tools to ensure registration
- Exports `setup_mcp` server instance
- Provides helper function to check if setup server should be mounted

### Step 5: Implement Dynamic Mounting Logic

Update `src/cortex/main.py` or create `src/cortex/server_setup.py`:

```python
from cortex.server import mcp
from cortex.setup import setup_mcp
from cortex.tools.config_status import get_project_config_status

def mount_setup_server_if_needed():
    """Mount setup server if project needs initialization or migration."""
    config_status = get_project_config_status()
    
    needs_setup = (
        not config_status["memory_bank_initialized"]
        or not config_status["structure_configured"]
        or not config_status["cursor_integration_configured"]
        or config_status["migration_needed"]
        or not config_status["tiktoken_cache_available"]
    )
    
    if needs_setup:
        mcp.mount(setup_mcp, prefix="setup")
        return True
    return False
```

### Step 6: Update Main Entry Point

Update `src/cortex/main.py` to mount setup server before running:

```python
def main() -> None:
    """Entry point for the application when run with uvx."""
    # Mount setup server if needed
    mount_setup_server_if_needed()
    
    try:
        mcp.run(transport="stdio")
    # ... existing error handling ...
```

### Step 7: Handle Tool/Prompt Prefixing

When mounting with prefix `"setup"`, tools and prompts will be prefixed:

- `check_structure_health` → `setup_check_structure_health`
- `initialize_memory_bank` → `setup_initialize_memory_bank`

Consider:

- **Option A**: Mount without prefix (tools/prompts keep original names)
- **Option B**: Mount with prefix (explicit namespace, clearer separation)
- **Option C**: Mount with prefix but also expose without prefix for backward compatibility

**Recommendation**: Option B (with prefix) for clarity, but document the change.

### Step 8: Update Imports and Dependencies

- Remove setup-related imports from `src/cortex/tools/__init__.py`
- Update `src/cortex/tools/prompts.py` to remove setup prompts
- Update `src/cortex/tools/phase8_structure.py` to remove structure tools (or keep as re-exports for backward compatibility)
- Ensure `config_status.py` remains accessible to both servers

## Challenges and Considerations

### Challenge 1: Conditional Registration

**Issue**: Setup prompts are currently conditionally registered based on config status at import time.

**Solution**:

- Setup server always registers all prompts/tools
- Main server conditionally mounts setup server based on config status
- This is cleaner than conditional registration within the server

### Challenge 2: Shared Dependencies

**Issue**: Setup server needs access to managers, config status, etc.

**Solution**:

- Setup server can import and use shared modules (managers, config_status, etc.)
- No circular dependencies expected since setup server is separate module
- Both servers share the same project root and context

### Challenge 3: Backward Compatibility

**Issue**: Existing code/tests may reference tools/prompts by original names.

**Solution**:

- If using prefix, update all references to use prefixed names
- Or keep re-exports in original modules for backward compatibility
- Update tests to use new names or re-exports

### Challenge 4: Runtime Mounting Performance

**Issue**: Mounting at runtime may have slight performance overhead.

**Solution**:

- Mounting is synchronous and lightweight (FastMCP documentation)
- Only mounts when needed (uninitialized projects)
- Once initialized, setup server is not mounted, so no ongoing overhead

### Challenge 5: Testing

**Issue**: Need to test both mounted and unmounted scenarios.

**Solution**:

- Test setup server independently
- Test main server with setup server mounted
- Test main server without setup server (initialized projects)
- Integration tests for dynamic mounting logic

## Migration Strategy

### Phase 1: Preparation (No Breaking Changes)

1. Create `src/cortex/setup/` directory structure
2. Create setup server module with extracted prompts/tools
3. Keep original prompts/tools in place (duplicate temporarily)
4. Add mounting logic but don't activate yet

### Phase 2: Testing

1. Test setup server independently
2. Test mounting logic in isolation
3. Test main server with setup server mounted
4. Verify all setup functionality works with new structure

### Phase 3: Activation

1. Activate dynamic mounting in main entry point
2. Remove original setup prompts/tools from main server
3. Update all references to use prefixed names (if using prefix)
4. Update tests

### Phase 4: Cleanup

1. Remove duplicate code
2. Update documentation
3. Update roadmap with completion status

## Files to Create/Modify

### New Files

- `src/cortex/setup/__init__.py` - Setup server module initialization
- `src/cortex/setup/server.py` - Setup MCP server instance
- `src/cortex/setup/prompts.py` - Setup prompts (extracted from `tools/prompts.py`)
- `src/cortex/setup/tools.py` - Setup tools (extracted from `tools/phase8_structure.py`)
- `src/cortex/server_setup.py` - Dynamic mounting logic (optional, could be in `main.py`)

### Modified Files

- `src/cortex/main.py` - Add mounting logic
- `src/cortex/tools/prompts.py` - Remove setup prompts (or keep as re-exports)
- `src/cortex/tools/phase8_structure.py` - Remove structure tools (or keep as re-exports)
- `src/cortex/tools/__init__.py` - Remove setup-related imports

### Test Files

- `tests/unit/test_setup_server.py` - Test setup server independently
- `tests/integration/test_setup_mounting.py` - Test dynamic mounting
- Update existing tests that reference setup tools/prompts

## Success Criteria

1. ✅ Setup server created and functional
2. ✅ Dynamic mounting works correctly (mounts when needed, doesn't mount when not needed)
3. ✅ All setup prompts/tools accessible via setup server
4. ✅ Main server no longer contains setup logic
5. ✅ All tests passing
6. ✅ No regressions in functionality
7. ✅ Documentation updated

## Related Work

- [Conditional Prompt Registration](../plans/conditional-prompt-registration.md) - Related to conditional availability
- [Refactor Setup Prompts](../plans/refactor-setup-prompts.md) - May benefit from this extraction
- FastMCP 2.0 Migration (Phase 41) - Uses FastMCP 2.0 which supports composition

## Target Completion

2026-01-24

## Notes

- This refactoring improves code organization and aligns with FastMCP best practices
- Setup logic is naturally separated from core functionality
- Dynamic mounting ensures setup tools are only available when needed
- Consider this as part of broader server architecture improvements
