# Migrate

This prompt template guides you through migrating a project from legacy structure to the new `.cortex/` structure.

## Prerequisites

- Cortex server installed and configured
- Project with legacy structure detected (`.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/`)
- Git repository initialized (for version history preservation)

## Prompt

```text
Please migrate my project from legacy structure to the new .cortex/ structure.
```

## What Happens

The assistant will perform complete migration:

### Step 1: Detect legacy structure

- Checks for legacy formats:
  - `.cursor/memory-bank/` (old Cursor-centric format)
  - `memory-bank/` (root-level format)
  - `.memory-bank/` (old standardized format)
  - Any other legacy locations

### Step 2: Initialize new .cortex/ structure

- Creates new `.cortex/` directory structure (same as `initialize` prompt)
- Creates `.cortex/memory-bank/`, `.cortex/plans/`, `.cortex/config/`
- Initializes Memory Bank with 7 core files (if not already present)
- Sets up Cursor integration (symlinks + mcp.json)

### Step 3: Migrate legacy files

- Copies/moves all files from legacy locations to new structure:
  - `.cursor/memory-bank/` → `.cortex/memory-bank/` (+ symlink `.cursor/memory-bank`)
  - `memory-bank/` → `.cortex/memory-bank/` (+ symlink `.cursor/memory-bank`)
  - `.memory-bank/knowledge/` → `.cortex/memory-bank/`
  - `.cursor/synapse/` → `.cortex/synapse/` (+ symlink `.cursor/synapse`)
  - `.cursor/plans/` → `.cortex/plans/` (+ symlink `.cursor/plans`)
  - `rules/` → `.cortex/synapse/` (if using Synapse)
  - `.plan/` → `.cortex/plans/`
  - `docs/plans/` → `.cortex/plans/`

### Step 4: Preserve content and history

- Copies all files preserving content
- Migrates version history to `.cortex/history/`
- Updates metadata index to `.cortex/index.json`
- Preserves all snapshots and version information

### Step 5: Update references and links

- Updates any internal references to old paths
- Fixes broken links in memory bank files
- Updates configuration files with new paths

### Step 6: Validate migration

- Verifies all files were migrated successfully
- Checks that content is preserved correctly
- Validates symlinks are working
- Ensures version history is intact

### Step 7: Remove legacy directories

- Only after successful validation
- Removes old `.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/` directories
- Keeps `.cursor/` directory but removes old content
- Cleans up any other legacy locations

## Expected Output

### Successful Migration

```json
{
  "status": "success",
  "message": "Project migrated successfully",
  "legacy_locations_detected": [
    ".cursor/memory-bank",
    "memory-bank"
  ],
  "migrations": {
    "memory_bank": {
      "from": ".cursor/memory-bank",
      "to": ".cortex/memory-bank/",
      "files": 7
    },
    "synapse": {
      "from": ".cursor/synapse",
      "to": ".cortex/synapse/",
      "files": 12
    },
    "plans": {
      "from": ".cursor/plans",
      "to": ".cortex/plans/",
      "files": 5
    }
  },
  "directories_created": [
    ".cortex",
    ".cortex/memory-bank",
    ".cortex/plans",
    ".cursor"
  ],
  "symlinks_created": [
    ".cursor/memory-bank",
    ".cursor/synapse",
    ".cursor/plans"
  ],
  "files_migrated": 24,
  "versions_migrated": 15,
  "links_updated": 3,
  "legacy_directories_removed": [
    ".cursor/memory-bank",
    "memory-bank"
  ],
  "duration_ms": 1234
}
```

### Migration Not Needed

```json
{
  "status": "up_to_date",
  "message": "Project is already using the .cortex/ structure",
  "current_location": ".cortex/memory-bank/",
  "files_count": 7
}
```

### Migration Failed

```json
{
  "status": "failed",
  "message": "Migration failed",
  "error": "Error details...",
  "rollback_performed": true,
  "suggestion": "Check error details and try again"
}
```

## When This Prompt Appears

This prompt is **conditionally registered** and only appears when:

- Legacy structure is detected (`migration_needed = true`)
- Project has files in old locations (`.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/`)

If your project is already using the `.cortex/` structure, this prompt will not appear.

## Safety Features

- **Automatic rollback** - If migration fails, changes are automatically rolled back
- **Content validation** - Content is validated after migration to ensure nothing was lost
- **Version history preservation** - All version history is preserved during migration
- **Atomic operation** - Migration succeeds completely or fails completely (no partial state)
- **Backup creation** - Optional backup creation before migration (recommended)

## Migration Mappings

| Legacy Location | New Location | Notes |
|----------------|--------------|-------|
| `.cursor/memory-bank/` | `.cortex/memory-bank/` | Creates symlink `.cursor/memory-bank` |
| `memory-bank/` | `.cortex/memory-bank/` | Creates symlink `.cursor/memory-bank` |
| `.memory-bank/knowledge/` | `.cortex/memory-bank/` | Migrates knowledge files |
| `.cursor/synapse/` | `.cortex/synapse/` | Creates symlink `.cursor/synapse` |
| `.cursor/plans/` | `.cortex/plans/` | Creates symlink `.cursor/plans` |
| `rules/` | `.cortex/synapse/` | If using Synapse |
| `.plan/` | `.cortex/plans/` | Legacy plan directory |
| `docs/plans/` | `.cortex/plans/` | Documentation plans |

## Next Steps

After migration:

1. **Verify migration** - Check that all files were migrated correctly
2. **Test functionality** - Ensure Memory Bank tools work with new structure
3. **Update documentation** - Update any project documentation referencing old paths
4. **Commit changes** - Commit the migration to version control

## Related Prompts

- **initialize** - Use this for new projects (no legacy structure)
- **setup_synapse** - Use this to add Synapse after migration if needed
