# Migration Guide

This guide helps you migrate from old Memory Bank formats to the standardized Cortex structure.

## Overview

Cortex supports automatic migration from several legacy formats:

1. **TradeWing-style**: Files in project root + `.cursor/plans`
2. **doc-mcp-style**: Files in `docs/memory-bank/`
3. **Scattered files**: Memory Bank files throughout project
4. **Cursor default**: Just `.cursorrules` file

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
  "legacy_format": "tradewing-style",
  "files_found": {
    "projectBrief.md": "/project-root/projectBrief.md",
    "productContext.md": "/project-root/productContext.md",
    "plans": "/project-root/.cursor/plans/"
  },
  "recommended_action": "migrate_to_standard_structure"
}
```

### Step 2: Run Migration

Migrate to standardized structure:

```json
{
  "tool": "migrate_project_structure",
  "args": {
    "project_root": "/path/to/your/project",
    "backup": true
  }
}
```

**What happens**:

1. **Backup created** at `.memory-bank-migration-backup-<timestamp>/`
2. **Files moved** to `.memory-bank/knowledge/`
3. **Plans organized** into `.memory-bank/plans/` (active/completed/archived)
4. **Rules moved** to `.memory-bank/rules/local/`
5. **Links updated** in all files
6. **Cursor symlinks** created for IDE integration
7. **Legacy files archived** for safety

**Response**:

```json
{
  "status": "success",
  "files_migrated": 7,
  "backup_location": ".memory-bank-migration-backup-20241225-103000",
  "new_structure": {
    "knowledge": [
      ".memory-bank/knowledge/projectBrief.md",
      ".memory-bank/knowledge/productContext.md",
      ".memory-bank/knowledge/activeContext.md"
    ],
    "plans": [
      ".memory-bank/plans/active/feature-auth.md"
    ],
    "rules": [
      ".memory-bank/rules/local/main.cursorrules"
    ]
  },
  "symlinks_created": [
    ".cursor/knowledge -> ../.memory-bank/knowledge",
    ".cursor/rules -> ../.memory-bank/rules",
    ".cursor/plans -> ../.memory-bank/plans",
    ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
  ]
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
    "symlinks": "pass",
    "configuration": "pass"
  }
}
```

## Manual Migration

If automatic migration doesn't work or you prefer manual control:

### From TradeWing-style

**Before**:

```text
project-root/
├── projectBrief.md
├── productContext.md
├── activeContext.md
├── systemPatterns.md
├── techContext.md
├── progress.md
└── .cursor/
    ├── plans/
    └── .cursorrules
```

**After**:

```text
project-root/
├── .memory-bank/
│   ├── knowledge/
│   │   ├── projectBrief.md
│   │   ├── productContext.md
│   │   ├── activeContext.md
│   │   ├── systemPatterns.md
│   │   ├── techContext.md
│   │   └── progress.md
│   ├── rules/
│   │   └── local/
│   │       └── main.cursorrules
│   └── plans/
│       ├── active/
│       └── completed/
└── .cursor/
    ├── knowledge -> ../.memory-bank/knowledge
    ├── rules -> ../.memory-bank/rules
    ├── plans -> ../.memory-bank/plans
    └── .cursorrules -> ../.memory-bank/rules/local/main.cursorrules
```

**Steps**:

```bash
# 1. Create backup
mkdir -p .memory-bank-migration-backup-$(date +%Y%m%d-%H%M%S)
cp -r projectBrief.md productContext.md *.md .cursor/ .memory-bank-migration-backup-*/

# 2. Create new structure
mkdir -p .memory-bank/knowledge
mkdir -p .memory-bank/rules/local
mkdir -p .memory-bank/plans/{active,completed,archived}

# 3. Move files
mv projectBrief.md productContext.md activeContext.md systemPatterns.md techContext.md progress.md .memory-bank/knowledge/

# 4. Move rules
cp .cursor/.cursorrules .memory-bank/rules/local/main.cursorrules

# 5. Organize plans
mv .cursor/plans/*.md .memory-bank/plans/active/

# 6. Create symlinks (Unix/macOS)
ln -s ../.memory-bank/knowledge .cursor/knowledge
ln -s ../.memory-bank/rules .cursor/rules
ln -s ../.memory-bank/plans .cursor/plans
ln -s .memory-bank/rules/local/main.cursorrules .cursorrules

# 7. Windows (use junction points)
# mklink /J .cursor\knowledge ..\memory-bank\knowledge
# mklink /J .cursor\rules ..\memory-bank\rules
# mklink /J .cursor\plans ..\memory-bank\plans
# mklink .cursorrules .memory-bank\rules\local\main.cursorrules
```

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

**After**:

```text
project-root/
├── .memory-bank/
│   └── knowledge/
│       ├── projectBrief.md
│       ├── productContext.md
│       └── ...
└── .cursor/
    └── knowledge -> ../.memory-bank/knowledge
```

**Steps**:

```bash
# 1. Backup
cp -r docs/memory-bank/ .memory-bank-migration-backup-$(date +%Y%m%d-%H%M%S)/

# 2. Create structure
mkdir -p .memory-bank/knowledge
mkdir -p .cursor

# 3. Move files
mv docs/memory-bank/*.md .memory-bank/knowledge/

# 4. Create symlink
ln -s ../.memory-bank/knowledge .cursor/knowledge

# 5. Clean up
rm -rf docs/memory-bank/
```

### From Scattered Files

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

**After**:

```text
project-root/
└── .memory-bank/
    └── knowledge/
        ├── projectBrief.md
        ├── activeContext.md
        └── systemPatterns.md
```

**Steps**:

```bash
# 1. Find all Memory Bank files
find . -name "projectBrief.md" -o -name "productContext.md" -o -name "activeContext.md" \
       -o -name "systemPatterns.md" -o -name "techContext.md" -o -name "progress.md"

# 2. Create backup
mkdir -p .memory-bank-migration-backup-$(date +%Y%m%d-%H%M%S)
# Copy found files to backup

# 3. Create structure
mkdir -p .memory-bank/knowledge

# 4. Move files to standard location
mv docs/projectBrief.md .memory-bank/knowledge/
mv planning/activeContext.md .memory-bank/knowledge/
mv architecture/systemPatterns.md .memory-bank/knowledge/
# ... move remaining files

# 5. Create symlinks
mkdir -p .cursor
ln -s ../.memory-bank/knowledge .cursor/knowledge
```

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
mkdir -p .memory-bank/knowledge
cp projectBrief.md productContext.md .memory-bank/knowledge/

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

Add metadata files to `.gitignore`:

```gitignore
# Memory Bank Metadata (not tracked)
.memory-bank-index
.memory-bank-history/
.memory-bank-access-log.json
.memory-bank-learning.json
.memory-bank-approvals.json
.memory-bank-refactoring-history.json
.memory-bank-rollbacks.json
.memory-bank-validation.json
.memory-bank-optimization.json
.memory-bank-migration-backup-*/
```

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

Run quality check:

```json
{
  "tool": "get_quality_score",
  "args": {
    "project_root": "/path/to/project"
  }
}
```

Address any issues found.

### 4. Set Up Cursor Integration

Verify Cursor symlinks work:

```bash
# Check symlinks
ls -la .cursor/

# Should show:
# knowledge -> ../.memory-bank/knowledge
# rules -> ../.memory-bank/rules
# plans -> ../.memory-bank/plans
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
ls -d .memory-bank-migration-backup-*

# 2. Restore files
cp -r .memory-bank-migration-backup-20241225-103000/* .

# 3. Remove new structure
rm -rf .memory-bank/

# 4. Remove symlinks
rm .cursor/knowledge .cursor/rules .cursor/plans .cursorrules
```

## Migration Checklist

- [ ] Backup created
- [ ] All files moved to `.memory-bank/knowledge/`
- [ ] Plans organized in `.memory-bank/plans/`
- [ ] Rules moved to `.memory-bank/rules/local/`
- [ ] Cursor symlinks created and working
- [ ] Links validated and fixed
- [ ] Quality check passed
- [ ] .gitignore updated
- [ ] Old files archived or removed

## Common Migration Issues

### Issue: Symlink creation fails on Windows

**Solution**: Use junction points instead:

```cmd
mklink /J .cursor\knowledge ..\..memory-bank\knowledge
```

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

### Issue: Cursor IDE doesn't see new structure

**Solution**: Restart Cursor IDE and clear cache:

```bash
# macOS
rm -rf ~/Library/Application\ Support/Cursor/Cache/

# Linux
rm -rf ~/.config/Cursor/Cache/

# Windows
# Delete C:\Users\<username>\AppData\Roaming\Cursor\Cache\
```

## See Also

- [Getting Started](../getting-started.md) - Initial setup
- [Configuration Guide](./configuration.md) - Configure after migration
- [Troubleshooting](./troubleshooting.md) - Common issues
- [Project Structure](../architecture.md#project-structure) - Standard structure details
