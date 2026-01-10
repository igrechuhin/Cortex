# Initialize Memory Bank

This prompt template guides you through initializing a Memory Bank in your project.

## Prerequisites

- Cortex server installed and configured
- Project directory exists

## Prompt

```
Please initialize a Memory Bank in my project at [PROJECT_ROOT].

I need you to:
1. Create the memory-bank/ directory
2. Generate all 7 core files from templates:
   - projectBrief.md - Foundation document
   - productContext.md - Product context and requirements
   - activeContext.md - Current active development context
   - systemPatterns.md - System architecture patterns
   - techContext.md - Technical context and decisions
   - progress.md - Development progress tracking
   - roadmap.md - Development roadmap and milestones
3. Initialize the metadata index
4. Create initial snapshots for version control

If an old format is detected, please migrate it to the current format.
```

## What Happens

The assistant will:
1. Check if Memory Bank is already initialized
2. Create `memory-bank/` directory if needed
3. Generate all core files from templates
4. Initialize metadata index at `.memory-bank-index`
5. Create initial version snapshots
6. Report success with file count and token statistics

## Expected Output

```json
{
  "status": "success",
  "message": "Memory Bank initialized successfully",
  "project_root": "/path/to/project",
  "files_created": 7,
  "total_tokens": 1234
}
```

## Migration

If an old Memory Bank format is detected (e.g., `.cursor/memory-bank/`), the assistant will automatically migrate it to the new `memory-bank/` location while preserving all content and version history.

## Next Steps

After initialization:
1. Review and customize the generated files
2. Fill in project-specific details
3. Start using Memory Bank tools for validation and optimization
