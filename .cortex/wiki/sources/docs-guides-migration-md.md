# Migration Guide

This guide helps you migrate from old Memory Bank formats to the standardized
`.cortex/` structure.

> **Canonical reference**: The authoritative, up-to-date description of the
> migration flow is [docs/prompts/migrate.md](../prompts/migrate.md), which
> mirrors the `migrate` MCP prompt (`MIGRATE_PROMPT` in
> `src/cortex/setup/prompts.py`). This page gives a task-oriented walkthrough;
> if anything here disagrees with `docs/prompts/migrate.md`, that page wins.

## Overview

Cortex supports automatic migration from several legacy formats into
`.cortex/memory-bank/`, `.cortex/plans/`, and `.cortex/synapse/`:

1. **A leftover `.cursor/memory-bank/` directory** — a real directory (not a
   symlink) left over from a pre-removal Cortex version. Cortex no longer
   generates or maintains anything under `.cursor/`; a plain
   `.cursor/memory-bank` symlink (rather than a real directory) is cleaned up
   automatically the next time the Cortex MCP server starts, not by this
   migration.
2. **doc-mcp-style**: Files in `docs/memory-bank/`
3. **Scattered files**: Memory Bank files throughout the project
4. **Root-level `memory-bank/`** or **`.memory-bank/`**: older standardized layouts

## Automatic Migration

### Step 1: Check Migration Status

Before migrating, check what needs to be migrated:

```json
{
  "tool": "check_migration_status",
  "args": {
    "project_root": "/path/to/your/project"
  }
}
```

**Response**:

```json
{
  "needs_migration": true,
  "legacy_format": "doc-mcp-style",
  "files_found": {
    "projectBrief.md": "/project-root/docs/memory-bank/projectBrief.md",
    "productContext.md": "/project-root/docs/memory-bank/productContext.md"
  },
  "recommended_action": "migrate_to_standard_structure"
}
```

### Step 2: Run Migration

Migrate to the standardized `.cortex/` structure:

```json
{
  "tool": "migrate_project_structure",
  "args": {
    "project_root": "/path/to/your/project",
    "backup": true
  }
}
```

**What happens** (see [docs/prompts/migrate.md](../prompts/migrate.md) for the
full step-by-step flow used by the `migrate` prompt):

1. **Backup created** (optional) before any files move
2. **Core files moved** to `.cortex/memory-bank/`
3. **Non-standard files** (topic notes, ad-hoc docs found in a legacy
   memory-bank directory) relocated to `.cortex/notes/`, not copied into
   `.cortex/memory-bank/`
4. **Plans organized** into `.cortex/plans/`
5. **Rules moved** into `.cortex/synapse/rules/` (if using Synapse)
6. **Links updated** in all migrated files
7. **`.mcp.json`** written/updated at the project root
8. **Legacy directories removed** after successful validation — no `.cursor/`
   symlinks or directories are created or recreated

**Response**:

```json
{
  "status": "success",
  "files_migrated": 7,
  "backup_location": ".cortex-backup-20260101-103000",
  "new_structure": {
    "memory_bank": [
      ".cortex/memory-bank/projectBrief.md",
      ".cortex/memory-bank/productContext.md",
      ".cortex/memory-bank/activeContext.md"
    ],
    "plans": [
      ".cortex/plans/active/feature-auth.md"
    ]
  },
  "non_standard_files_relocated": [
    ".cortex/notes/legacy-analysis.md"
  ],
  "config_files": [".mcp.json"]
}
```

### Step 3: Verify Migration

Check structure health:

```json
{
  "tool": "check_structure_health",
  "args": {
    "project_root": "/path/to/your/project"
  }
}
```

**Expected result**:

```json
{
  "health_score": 95,
  "status": "healthy",
  "checks": {
    "required_directories": "pass",
    "configuration": "pass"
  }
}
```

## Manual Migration

If automatic migration doesn't work or you prefer manual control, the target
layout is always `.cortex/`:

```text
project-root/
├── .cortex/
│   ├── memory-bank/
│   │   ├── projectBrief.md
│   │   ├── productContext.md
│   │   ├── activeContext.md
│   │   ├── systemPatterns.md
│   │   ├── techContext.md
│   │   ├── progress.md
│   │   └── roadmap.md
│   ├── plans/
│   │   ├── active/
│   │   └── completed/
│   ├── synapse/
│   │   └── rules/
│   ├── notes/
│   └── config/
└── .mcp.json
```

There is no `.cursor/` directory or symlink involved in a current install —
Cortex reads and writes only under `.cortex/` and `.mcp.json`.

### From doc-mcp-style

**Before**:

```text
project-root/
└── docs/
    └── memory-bank/
        ├── projectBrief.md
        ├── productContext.md
        └── ...
```

**Steps**:

```bash
# 1. Backup
cp -r docs/memory-bank/ .cortex-backup-$(date +%Y%m%d-%H%M%S)/

# 2. Create structure
mkdir -p .cortex/memory-bank

# 3. Move core files
mv docs/memory-bank/*.md .cortex/memory-bank/

# 4. Clean up
rm -rf docs/memory-bank/
```

### From scattered files

**Before**:

```text
project-root/
├── docs/
│   └── projectBrief.md
├── planning/
│   └── activeContext.md
└── architecture/
    └── systemPatterns.md
```

**Steps**:

```bash
# 1. Find all Memory Bank files
find . -name "projectBrief.md" -o -name "productContext.md" -o -name "activeContext.md" \
       -o -name "systemPatterns.md" -o -name "techContext.md" -o -name "progress.md"

# 2. Create backup
mkdir -p .cortex-backup-$(date +%Y%m%d-%H%M%S)
# Copy found files to backup

# 3. Create structure
mkdir -p .cortex/memory-bank

# 4. Move files to standard location
mv docs/projectBrief.md .cortex/memory-bank/
mv planning/activeContext.md .cortex/memory-bank/
mv architecture/systemPatterns.md .cortex/memory-bank/
# ... move remaining files
```

### From a leftover `.cursor/memory-bank/` directory

Only relevant if you have a **real directory** (not a symlink) at
`.cursor/memory-bank/`, left over from a Cortex version before Cursor
integration was removed:

```bash
# 1. Backup
cp -r .cursor/memory-bank/ .cortex-backup-$(date +%Y%m%d-%H%M%S)/

# 2. Create structure
mkdir -p .cortex/memory-bank

# 3. Move core files only (relocate anything else to .cortex/notes/)
mv .cursor/memory-bank/*.md .cortex/memory-bank/

# 4. Remove the legacy directory
rm -rf .cursor/memory-bank/
```

A plain `.cursor/memory-bank` **symlink** (rather than a real directory) does
not need manual handling — Cortex removes leftover `.cursor/` artifacts
automatically on the next MCP server start.

## Migration Scenarios

### Scenario 1: Fresh Start (No Existing Files)

Use `setup_project_structure` for guided setup:

```json
{
  "tool": "setup_project_structure",
  "args": {
    "project_root": "/path/to/project",
    "interactive": true
  }
}
```

Prompts you for:

- Project name and type
- Team size
- Primary technologies
- Generates initial files automatically

### Scenario 2: Existing Memory Bank (Old Format)

Use `migrate_project_structure`:

```json
{
  "tool": "migrate_project_structure",
  "args": {
    "project_root": "/path/to/project",
    "backup": true
  }
}
```

Automatically detects format and migrates.

### Scenario 3: Partial Migration (Keep Old Structure)

Keep old structure alongside new:

```bash
# Create new structure without removing old files
mkdir -p .cortex/memory-bank
cp projectBrief.md productContext.md .cortex/memory-bank/

# Use both structures during transition
```

Later, clean up old files:

```bash
# After verifying new structure works
rm projectBrief.md productContext.md ...
```

### Scenario 4: Multi-Project Migration

Migrate multiple projects:

```bash
#!/bin/bash
for project in project1 project2 project3; do
  cd "$project"
  uvx --from git+https://github.com/igrechuhin/cortex.git cortex \
    --tool migrate_project_structure \
    --project-root "$(pwd)" \
    --backup true
  cd ..
done
```

## Post-Migration Tasks

### 1. Update .gitignore

Configuration files (`validation.json`, `optimization.json`, `learning.json`) live under `.cortex/config/`. If you have existing files at `.cortex/validation.json`, `.cortex/optimization.json`, or `.cortex/learning.json`, move them into `.cortex/config/`.

Add metadata files to `.gitignore`:

```gitignore
# Cortex MCP (transient/generated files)
.cortex/.session/
.cortex/.cache/
.cortex/history/
.cortex-backup-*/
```

Do **not** add `.cortex/memory-bank/`, `.cortex/plans/`, or `.cortex/config/`
— those contain project data that should be tracked by version control.

### 2. Validate Links

Check all links after migration:

```json
{
  "tool": "validate_links",
  "args": {
    "project_root": "/path/to/project"
  }
}
```

Fix any broken links found.

### 3. Check Quality

Run the quality gate:

```json
{
  "tool": "run_quality_gate",
  "args": {}
}
```

Address any issues found.

### 4. Verify MCP Configuration

Confirm `.mcp.json` at the project root has the correct server entries:

```bash
cat .mcp.json
```

### 5. Configure Optimization

Set up optimization preferences:

```json
{
  "tool": "configure_optimization",
  "args": {
    "project_root": "/path/to/project",
    "config": {
      "token_budget.default_budget": 100000,
      "rules.enabled": true
    }
  }
}
```

## Rollback Migration

If migration causes issues, rollback:

```bash
# 1. Find backup directory
ls -d .cortex-backup-*

# 2. Restore files
cp -r .cortex-backup-20260101-103000/* .

# 3. Remove new structure
rm -rf .cortex/memory-bank .cortex/plans
```

## Migration Checklist

- [ ] Backup created
- [ ] All core files moved to `.cortex/memory-bank/`
- [ ] Non-standard files relocated to `.cortex/notes/`
- [ ] Plans organized in `.cortex/plans/`
- [ ] Rules moved to `.cortex/synapse/rules/` (if using Synapse)
- [ ] `.mcp.json` present and correct at the project root
- [ ] Links validated and fixed
- [ ] Quality check passed
- [ ] `.gitignore` updated
- [ ] Old files/directories archived or removed
- [ ] No stale `.cursor/` path references remain

## Common Migration Issues

### Issue: File paths broken after migration

**Solution**: Use link validation and fix:

```json
{
  "tool": "validate_links",
  "args": {
    "project_root": "/path/to/project",
    "fix_broken_links": true
  }
}
```

### Issue: Stale `.cursor/` references remain in memory bank files

**Solution**: Rerun the `migrate` prompt's reference-update step (see
[docs/prompts/migrate.md](../prompts/migrate.md), Step 5), which rewrites any
`.cursor/memory-bank/`, `.cursor/plans/`, `.cursor/synapse/`, `.cursor/scripts/`,
or `.cursor/rules/` reference found in `.cortex/memory-bank/` or
`.cortex/plans/` content.

## See Also

- [Migrate Prompt](../prompts/migrate.md) - Canonical, current migration flow
- [Getting Started](../getting-started.md) - Initial setup
- [Configuration Guide](./configuration.md) - Configure after migration
- [Troubleshooting](./troubleshooting.md) - Common issues
- [Project Structure](../architecture.md) - Standard structure details
