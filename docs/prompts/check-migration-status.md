# Check Migration Status

This prompt template guides you through checking if your Memory Bank needs migration.

## Prerequisites

- Cortex server installed and configured
- Project directory exists

## Prompt

```
Please check if my Memory Bank at [PROJECT_ROOT] needs migration.

I need you to:
1. Detect the current Memory Bank format
2. Check if it's using an old directory structure
3. Identify what changes would be needed
4. Report the migration status
```

## What Happens

The assistant will:
1. Check for old format at `.cursor/memory-bank/`
2. Check for new format at `memory-bank/`
3. Validate file structure and metadata
4. Report whether migration is needed

## Expected Output

### No Migration Needed

```json
{
  "status": "up_to_date",
  "message": "Memory Bank is already using the latest format",
  "current_location": "memory-bank/",
  "files_count": 7
}
```

### Migration Needed

```json
{
  "status": "migration_needed",
  "message": "Old format detected at .cursor/memory-bank/",
  "old_location": ".cursor/memory-bank/",
  "new_location": "memory-bank/",
  "files_to_migrate": 7,
  "estimated_duration": "< 1 second"
}
```

### Not Initialized

```json
{
  "status": "not_initialized",
  "message": "No Memory Bank found",
  "suggestion": "Run initialize_memory_bank to create one"
}
```

## Next Steps

- If migration is needed, use the [Migrate Memory Bank](migrate-memory-bank.md) prompt
- If not initialized, use the [Initialize Memory Bank](initialize-memory-bank.md) prompt
- If up to date, continue using Memory Bank normally
