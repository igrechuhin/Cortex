# Migrate Memory Bank

This prompt template guides you through migrating your Memory Bank to the latest format.

## Prerequisites

- Cortex server installed and configured
- Existing Memory Bank in old format
- Migration status checked

## Prompt

```text
Please migrate my Memory Bank at [PROJECT_ROOT] to the latest format.

I need you to:
1. Create the new memory-bank/ directory
2. Copy all files from .cursor/memory-bank/ to memory-bank/
3. Preserve all content and version history
4. Update the metadata index
5. Create snapshots in the new location
6. Validate the migration succeeded
```

## What Happens

The assistant will:

1. Create new `memory-bank/` directory
2. Copy all files with content preservation
3. Migrate version history and snapshots
4. Update metadata index
5. Validate all files migrated correctly
6. Report migration results

## Expected Output

### Successful Migration

```json
{
  "status": "success",
  "message": "Memory Bank migrated successfully",
  "old_location": ".cursor/memory-bank/",
  "new_location": "memory-bank/",
  "files_migrated": 7,
  "versions_migrated": 25,
  "duration_ms": 234
}
```

### Failed Migration

```json
{
  "status": "failed",
  "message": "Migration failed: [error details]",
  "error": "Detailed error message",
  "rollback_status": "rolled back to original state"
}
```

## Safety Features

- **Automatic rollback**: If migration fails, all changes are rolled back
- **Content validation**: All file content is validated after migration
- **Version preservation**: All version history is preserved
- **Atomic operation**: Migration either succeeds completely or fails completely

## Post-Migration

After successful migration:

1. Verify all files are in `memory-bank/`
2. Check that content is intact
3. Test basic operations (read, write, validate)
4. Optionally delete `.cursor/memory-bank/` directory
5. Continue using Memory Bank normally

## Rollback

If you need to rollback:

- The old directory `.cursor/memory-bank/` is preserved
- Use `rollback_file_version` tool to restore specific files
- Contact support if automatic rollback failed
