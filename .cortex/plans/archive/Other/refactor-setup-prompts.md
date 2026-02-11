# Refactor Setup Prompts: Simplify to 3 Prompts

## Status

Planning

## Goal

Simplify the setup prompt system from 4 separate prompts to 3 unified prompts that better match user workflows:

- `initialize` - Complete setup for new projects (with default synapse_repo_url)
- `migrate` - For projects with old/legacy structure (does initialize + migration, then removes legacy)
- `setup_synapse` - Allows overriding the default synapse_repo_url (always available)

## Context

### Current State

Currently, there are 4 setup prompts:

1. `initialize_memory_bank` - Creates memory bank with 7 core files
2. `setup_project_structure` - Creates full `.cortex/` directory structure
3. `setup_cursor_integration` - Configures Cursor IDE integration
4. `setup_synapse` - Adds Synapse repository as Git submodule

And 3 migration prompts:

1. `check_migration_status` - Checks if migration is needed
2. `migrate_memory_bank` - Migrates memory bank files
3. `migrate_project_structure` - Migrates entire project structure

### Problems with Current Approach

- Too many prompts for what should be simple operations
- Users need to run multiple prompts in sequence for complete setup
- Migration prompts are separate from initialization, causing confusion
- No default synapse_repo_url in initialization
- Users must manually chain operations

### User Requirements

1. **`initialize`** - Should be a single prompt that:
   - Creates complete `.cortex/` structure (memory-bank, plans, config)
   - Initializes memory bank with 7 core files
   - Sets up Cursor integration (symlinks + mcp.json)
   - Optionally sets up Synapse with default URL (`https://github.com/igrechuhin/Synapse.git`)
   - Only shown when project is not initialized

2. **`migrate`** - Should be a single prompt that:
   - Detects legacy structure (`.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/`)
   - First runs `initialize` to create new structure
   - Migrates all legacy files to new structure
   - Preserves content and version history
   - Removes legacy directories after successful migration
   - Only shown when migration is needed

3. **`setup_synapse`** - Should:
   - Allow overriding default synapse_repo_url
   - Always be available (not conditional)
   - Work for both new projects and existing projects

## Approach

### Phase 1: Refactor Prompt Definitions

1. **Create `initialize` prompt**:
   - Combine functionality of `initialize_memory_bank`, `setup_project_structure`, and `setup_cursor_integration`
   - Include optional Synapse setup with default URL
   - Register conditionally: only if `not memory_bank_initialized and not structure_configured`
   - Prompt should guide through:
     - Creating `.cortex/` directory structure
     - Initializing memory bank with 7 core files
     - Setting up Cursor integration (symlinks + mcp.json)
     - Optionally setting up Synapse with default URL

2. **Create `migrate` prompt**:
   - Combine functionality of `check_migration_status`, `migrate_memory_bank`, and `migrate_project_structure`
   - First step: Run initialization (create new structure)
   - Second step: Migrate legacy files
   - Third step: Remove legacy directories
   - Register conditionally: only if `migration_needed`
   - Prompt should guide through:
     - Detecting legacy structure
     - Creating new `.cortex/` structure (via initialize)
     - Migrating all legacy files
     - Validating migration
     - Removing legacy directories

3. **Update `setup_synapse` prompt**:
   - Make it always available (remove conditional registration)
   - Add default parameter: `synapse_repo_url: str = "https://github.com/igrechuhin/Synapse.git"`
   - Update prompt to handle both new and existing projects

### Phase 2: Update Conditional Registration Logic

1. **Update `config_status.py`**:
   - Ensure `get_project_config_status()` correctly identifies:
     - Projects needing initialization (not initialized AND not configured)
     - Projects needing migration (legacy structure detected)
   - Add helper to check if project needs complete initialization

2. **Update `prompts.py`**:
   - Remove old prompt registrations:
     - `initialize_memory_bank`
     - `setup_project_structure`
     - `setup_cursor_integration`
     - `check_migration_status`
     - `migrate_memory_bank`
     - `migrate_project_structure`
   - Add new prompt registrations:
     - `initialize` (conditional: `not initialized and not configured`)
     - `migrate` (conditional: `migration_needed`)
     - `setup_synapse` (always available)

### Phase 3: Update Documentation

1. **Update README.md**:
   - Replace "Setup Prompts" section (lines 182-192) with new 3-prompt structure
   - Update "Which Prompt Should I Use?" table
   - Remove migration prompts section
   - Update prompt descriptions

2. **Update docs/prompts/README.md**:
   - Update available prompts list
   - Remove old prompt documentation references
   - Add new prompt documentation

3. **Create/Update prompt documentation files**:
   - `docs/prompts/initialize.md` - New unified initialize prompt
   - `docs/prompts/migrate.md` - New unified migrate prompt
   - Update `docs/prompts/setup-synapse.md` - Update with default parameter

### Phase 4: Update Tests

1. **Update conditional prompt tests**:
   - `tests/integration/test_conditional_prompts.py`
   - Test new conditional logic for `initialize` and `migrate`
   - Test that `setup_synapse` is always available
   - Remove tests for old prompts

2. **Add integration tests**:
   - Test `initialize` prompt flow
   - Test `migrate` prompt flow (with legacy structure)
   - Test `setup_synapse` with default and custom URLs

## Implementation Steps

### Step 1: Create New Prompt Templates

- [ ] Create `_INITIALIZE_PROMPT` template combining all initialization steps
- [ ] Create `_MIGRATE_PROMPT` template combining migration steps
- [ ] Update `_SETUP_SYNAPSE_PROMPT_TEMPLATE` with default parameter

### Step 2: Update Prompt Registration

- [ ] Remove old prompt function definitions
- [ ] Add new `initialize()` prompt function with conditional registration
- [ ] Add new `migrate()` prompt function with conditional registration
- [ ] Update `setup_synapse()` to always be registered with default parameter

### Step 3: Update Conditional Logic

- [ ] Review and update `config_status.py` if needed
- [ ] Ensure conditional registration logic works correctly
- [ ] Test conditional registration in different project states

### Step 4: Update Documentation

- [ ] Update README.md "Setup Prompts" section
- [ ] Update README.md "Which Prompt Should I Use?" table
- [ ] Update docs/prompts/README.md
- [ ] Create/update prompt documentation files

### Step 5: Update Tests

- [ ] Update `test_conditional_prompts.py` for new prompts
- [ ] Add integration tests for new prompt flows
- [ ] Remove tests for old prompts
- [ ] Ensure all tests pass

### Step 6: Verification

- [ ] Test `initialize` prompt in uninitialized project
- [ ] Test `migrate` prompt in project with legacy structure
- [ ] Test `setup_synapse` with default and custom URLs
- [ ] Verify conditional registration works correctly
- [ ] Verify documentation is accurate

## Technical Design

### New Prompt Structure

#### `initialize` Prompt

```python
@mcp.prompt()
def initialize() -> str:
    """Complete project initialization.
    
    Creates:
    - .cortex/ directory structure (memory-bank, plans, config)
    - Memory bank with 7 core files
    - Cursor integration (symlinks + mcp.json)
    - Optional Synapse setup with default URL
    
    Returns:
        Prompt message guiding complete initialization
    """
    # Conditional: only if not initialized and not configured
```

**Conditional Registration**: `if not _config_status["memory_bank_initialized"] and not _config_status["structure_configured"]`

#### `migrate` Prompt

```python
@mcp.prompt()
def migrate() -> str:
    """Migrate legacy structure to new .cortex/ structure.
    
    Steps:
    1. Initialize new .cortex/ structure
    2. Migrate legacy files
    3. Remove legacy directories
    
    Returns:
        Prompt message guiding migration process
    """
    # Conditional: only if migration needed
```

**Conditional Registration**: `if _config_status["migration_needed"]`

#### `setup_synapse` Prompt

```python
@mcp.prompt()
def setup_synapse(synapse_repo_url: str = "https://github.com/igrechuhin/Synapse.git") -> str:
    """Setup Synapse repository (always available).
    
    Args:
        synapse_repo_url: URL of Synapse repository (default provided)
    
    Returns:
        Prompt message guiding Synapse setup
    """
    # Always available
```

**Registration**: Always registered (no conditional)

### Prompt Content Structure

#### Initialize Prompt Content

Should guide through:

1. Creating `.cortex/` directory structure
2. Initializing memory bank with 7 core files
3. Setting up Cursor integration (symlinks + mcp.json)
4. Optionally setting up Synapse with default URL

#### Migrate Prompt Content

Should guide through:

1. Detecting legacy structure
2. Creating new `.cortex/` structure (via initialize steps)
3. Migrating all legacy files to new structure
4. Validating migration
5. Removing legacy directories after successful migration

## Dependencies

- No external dependencies
- Uses existing `config_status.py` for conditional registration
- Uses existing migration logic from `structure_migration.py`

## Success Criteria

- ✅ Only 3 setup prompts available: `initialize`, `migrate`, `setup_synapse`
- ✅ `initialize` and `migrate` are conditionally registered based on project state
- ✅ `setup_synapse` is always available
- ✅ `initialize` performs complete setup (structure + memory bank + Cursor + optional Synapse)
- ✅ `migrate` performs initialization first, then migration, then cleanup
- ✅ Default synapse_repo_url is used in `initialize` and `setup_synapse`
- ✅ All old prompts removed
- ✅ Documentation updated
- ✅ Tests updated and passing
- ✅ No breaking changes to existing functionality

## Risks & Mitigation

### Risk 1: Breaking Existing Workflows

**Mitigation**:

- Keep migration logic intact
- Ensure new prompts cover all functionality of old prompts
- Test thoroughly with different project states

### Risk 2: Conditional Registration Logic Issues

**Mitigation**:

- Review `config_status.py` logic carefully
- Add comprehensive tests for different project states
- Ensure edge cases are handled

### Risk 3: Migration Not Completing Properly

**Mitigation**:

- Ensure migration prompt includes initialization step
- Test migration flow thoroughly
- Ensure legacy cleanup only happens after successful migration

## Timeline

- **Step 1-2**: Prompt refactoring (2-3 hours)
- **Step 3**: Conditional logic updates (1 hour)
- **Step 4**: Documentation updates (1-2 hours)
- **Step 5**: Test updates (2-3 hours)
- **Step 6**: Verification (1-2 hours)

**Total Estimated Time**: 7-11 hours

## Notes

- This refactoring simplifies the user experience while maintaining all functionality
- The new structure better matches user mental models (initialize new project vs. migrate existing project)
- Default synapse_repo_url reduces friction for new projects
- Always-available `setup_synapse` allows users to override default or add Synapse later
