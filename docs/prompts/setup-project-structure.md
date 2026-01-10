# Setup Project Structure

This prompt template guides you through setting up the standardized project structure.

## Prerequisites

- Cortex server installed and configured
- Memory Bank initialized
- Project directory exists

## Prompt

```
Please setup the standardized project structure in my project at [PROJECT_ROOT].

I need you to:
1. Create the .cursor/ directory structure
2. Setup memory-bank/ with core files
3. Create rules/ directory for project rules
4. Setup plans/ directory for development plans
5. Generate all necessary template files
6. Initialize directory indexes
```

## What Happens

The assistant will:

1. Create directory structure:

   ```
   .cursor/
   ├── memory-bank/     # Core memory bank files
   ├── rules/           # Project-specific rules
   ├── plans/           # Development plans
   │   └── archive/     # Archived plans
   └── integrations/    # IDE integration configs
   ```

2. Generate core memory bank files from templates
3. Create default rule files
4. Setup plan directory with README
5. Initialize metadata and indexes
6. Report setup status

## Expected Output

### Successful Setup

```json
{
  "status": "success",
  "message": "Project structure setup successfully",
  "directories_created": [
    ".cursor/memory-bank",
    ".cursor/rules",
    ".cursor/plans",
    ".cursor/plans/archive",
    ".cursor/integrations"
  ],
  "files_created": [
    "memory-bank/projectBrief.md",
    "memory-bank/productContext.md",
    "memory-bank/activeContext.md",
    "memory-bank/systemPatterns.md",
    "memory-bank/techContext.md",
    "memory-bank/progress.md",
    "memory-bank/roadmap.md"
  ],
  "total_files": 7
}
```

### Already Exists

```json
{
  "status": "already_exists",
  "message": "Project structure already exists",
  "suggestion": "Use check_structure_health to validate"
}
```

### Partial Setup

```json
{
  "status": "partial",
  "message": "Some structure exists, filled in missing parts",
  "created": [".cursor/plans", ".cursor/plans/archive"],
  "existing": [".cursor/memory-bank", ".cursor/rules"]
}
```

## Directory Structure Details

### memory-bank/

Contains all Memory Bank core files. This is the single source of truth for project context.

### rules/

Contains project-specific rules in MDC format:

- `python-security.mdc` - Security guidelines
- `python-testing-standards.mdc` - Testing standards
- `no-test-skipping.mdc` - Test quality rules
- Custom project rules

### plans/

Contains development plans and roadmaps:

- Active plans in root
- Completed plans in `archive/PhaseX/MilestoneY/`

### integrations/

IDE-specific configuration files for Claude, Cursor, etc.

## Post-Setup

After successful setup:

1. Review and customize generated files
2. Add project-specific rules
3. Create development plans
4. Use `check_structure_health` to validate
5. Use `get_structure_info` for overview

## Customization

You can customize the structure:

- Add additional directories
- Customize template content
- Configure rules indexing
- Setup shared rules submodule
