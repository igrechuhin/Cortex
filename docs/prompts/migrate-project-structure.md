# Migrate Project Structure

This prompt template guides you through migrating your project to the standardized structure.

## Prerequisites

- Cortex server installed and configured
- Existing project with old structure
- Backup recommended before migration

## Prompt

```text
Please migrate my project structure at [PROJECT_ROOT] to the standardized format.

I need you to:
1. Detect the current structure
2. Create the new .cursor/ directory structure
3. Move existing files to correct locations
4. Preserve all content and history
5. Update references and links
6. Validate the migration
```

## What Happens

The assistant will:

1. Scan current project structure
2. Identify files to migrate
3. Create new directory structure
4. Move files to standardized locations:
   - Old memory bank → `.cursor/memory-bank/`
   - Old rules → `.cursor/rules/`
   - Old plans → `.cursor/plans/`
5. Update file references and transclusions
6. Validate all links work
7. Report migration results

## Expected Output

### Successful Migration

```json
{
  "status": "success",
  "message": "Project structure migrated successfully",
  "migrations": {
    "memory_bank": {
      "from": "memory-bank/",
      "to": ".cursor/memory-bank/",
      "files": 7
    },
    "rules": {
      "from": "rules/",
      "to": ".cursor/rules/",
      "files": 3
    },
    "plans": {
      "from": ".plan/",
      "to": ".cursor/plans/",
      "files": 25
    }
  },
  "links_updated": 42,
  "duration_ms": 456
}
```

### No Migration Needed

```json
{
  "status": "up_to_date",
  "message": "Project already uses standardized structure",
  "structure_version": "2.0"
}
```

### Failed Migration

```json
{
  "status": "failed",
  "message": "Migration failed",
  "error": "Failed to move file: ...",
  "rollback_status": "rolled back to original state"
}
```

## Migration Mappings

The migration handles these common patterns:

### Old → New Locations

- `memory-bank/` → `.cursor/memory-bank/`
- `.cursor/memory-bank/` → `.cursor/memory-bank/` (no change)
- `rules/` → `.cursor/rules/`
- `.plan/` → `.cursor/plans/`
- `docs/plans/` → `.cursor/plans/`

### File Renames

- `memorybankinstructions.md` → `memory-bank-instructions.md`
- Old template files → New template format

## Safety Features

- **Dry-run mode**: Preview changes without applying
- **Automatic rollback**: Revert on any error
- **Content validation**: Verify all content after migration
- **Link updating**: Automatically fix broken links
- **Backup creation**: Create snapshot before migration

## Post-Migration

After successful migration:

1. Verify all files are in correct locations
2. Check that links still work
3. Run `check_structure_health` to validate
4. Update any custom scripts or tools
5. Optionally delete old directories

## Rollback

If you need to rollback:

```text
Please rollback the project structure migration.
```

The assistant will:

- Restore from pre-migration snapshot
- Move files back to original locations
- Restore original links and references
