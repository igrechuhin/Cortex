# Migrate

This prompt template guides you through migrating a project from legacy structure to the new `.cortex/` structure.

## Prerequisites

- Cortex server installed and configured
- Project with legacy structure detected (Memory Bank as `memory-bank/` under the IDE `.cursor/` directory, root-level `memory-bank/`, or `.memory-bank/`)
- Git repository initialized (for version history preservation)

## Prompt

```text
Please migrate my project from legacy structure to the new .cortex/ structure.
```

## What Happens

The assistant will perform complete migration:

### Step 1: Detect legacy structure

- Checks for legacy formats:
  - `memory-bank/` inside the IDE `.cursor/` tree (old Cursor-centric layout)
  - `memory-bank/` (root-level format)
  - `.memory-bank/` (old standardized format)
  - Any other legacy locations

### Step 2: Initialize new .cortex/ structure

- Creates new `.cortex/` directory structure (same as `initialize` prompt)
- Creates `.cortex/memory-bank/`, `.cortex/plans/`, `.cortex/config/`
- Initializes Memory Bank with 7 core files (if not already present)
- Sets up Cursor integration (symlinks + mcp.json)

#### Step 2a: Post-edit quality hook (auto-emitted)

During migration, Cortex **automatically** detects the project language and emits
instructions for a tool-agnostic **post-edit hook**. This hook runs your project's
quality checks after every edit, catching breakages early (circular imports, corrupted
edits, type-check issues).

**Language detection:** Cortex uses common project manifests and conventions to pick a
best-guess primary language for the repo. If ambiguous or unknown, the hook is skipped.

**Hook contract (tool-agnostic):**

- Trigger: after an edit is applied (or, if your tool only supports it, after file save)
- Working directory: project root
- Command: run a fast, language-appropriate script from `.cortex/synapse/scripts/<lang>/`
- Config update behavior: merge changes; do not overwrite unrelated settings

**Example hook config (Claude Code only):**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .cortex/synapse/scripts/<lang>/<chosen_script>.py"
          }
        ]
      }
    ]
  }
}
```

**Command selection:** For a recognized language `<lang>`, pick an appropriate fast
script from `.cortex/synapse/scripts/<lang>/` (prefer `post_edit_hook.py` if present;
otherwise choose a build/tests script). Unknown/unsupported languages skip the hook.

**Merge behavior:** If `.claude/settings.json` already exists, the hook is merged
(unrelated keys are preserved). If the exact command is already present, the step is
a no-op. The migration output includes `detected_language` and `post_edit_hook_written`.

**Customization:** Replace the `command` with your project's preferred fast gate
(tests, build, lint, etc.).

### Step 3: Migrate legacy files

- Copies/moves all files from legacy locations to new structure:
  - IDE `.cursor/` + `memory-bank/` → `.cortex/memory-bank/` (+ symlink under `.cursor/` named `memory-bank`)
  - `memory-bank/` (repo root) → `.cortex/memory-bank/` (+ same compatibility symlink under `.cursor/`)
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
- Removes old Memory Bank directories (IDE `.cursor/` + `memory-bank/`, root `memory-bank/`, `.memory-bank/`)
- Keeps `.cursor/` directory but removes old content
- Cleans up any other legacy locations

## Expected Output

### Successful Migration

```json
{
  "status": "success",
  "message": "Project migrated successfully",
  "legacy_locations_detected": [
    "cursor_ide_memory_bank",
    "memory-bank"
  ],
  "migrations": {
    "memory_bank": {"from": "cursor_ide_memory_bank", "to": ".cortex/memory-bank/", "files": 7},
    "synapse": {"from": ".cursor/synapse", "to": ".cortex/synapse/", "files": 12},
    "plans": {"from": ".cursor/plans", "to": ".cortex/plans/", "files": 5}
  },
  "directories_created": [
    ".cortex",
    ".cortex/memory-bank",
    ".cortex/plans",
    ".cursor"
  ],
  "symlinks_created": [
    "cursor_ide_memory_bank_symlink",
    ".cursor/synapse",
    ".cursor/plans"
  ],
  "detected_language": "python",
  "post_edit_hook_written": true,
  "files_migrated": 24,
  "versions_migrated": 15,
  "links_updated": 3,
  "legacy_directories_removed": [
    "cursor_ide_memory_bank",
    "memory-bank"
  ],
  "duration_ms": 1234
}
```

(`cursor_ide_memory_bank` and `cursor_ide_memory_bank_symlink` stand in for the pre-migration Memory Bank directory and its compatibility symlink under `.cursor/`.)

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
- Project has files in old locations (Memory Bank under IDE `.cursor/` as `memory-bank/`, root `memory-bank/`, or `.memory-bank/`)

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
| IDE `.cursor/` + `memory-bank/` | `.cortex/memory-bank/` | Creates compatibility symlink under `.cursor/` |
| `memory-bank/` (repo root) | `.cortex/memory-bank/` | Same symlink under `.cursor/` |
| `.memory-bank/knowledge/` | `.cortex/memory-bank/` | Migrates knowledge files |
| `.cursor/synapse/` | `.cortex/synapse/` | Creates symlink `.cursor/synapse` |
| `.cursor/plans/` | `.cortex/plans/` | Creates symlink `.cursor/plans` |
| `rules/` | `.cortex/synapse/` | If using Synapse |
| `.plan/` | `.cortex/plans/` | Legacy plan directory |
| `docs/plans/` | `.cortex/plans/` | Documentation plans |

## Markdown Linting After Migration

After migration, plans in `.cortex/plans/` are resolved from the `.cortex/` tree, not from
`.cursor/plans/` (which is a symlink). Linters such as rumdl resolve relative links from the
real file location and cannot follow symlinks, so links that referenced sibling plans via the
old `.cursor/plans/` root must be verified.

**Common link breakage patterns to fix after migrating plans to `.cortex/plans/archive/`:**

| Broken pattern (from within `archive/`) | Fix |
|---|---|
| `archive/some-plan.plan.md` | `some-plan.plan.md` (drop the `archive/` prefix — files are peers) |
| `some-plan.v1.plan.md` where only `some-plan.plan.md` exists | Update to the real filename |
| `../condition-aware-…` when the file moved to plans root | Use correct `../` relative path |
| `.cursor/reviews/old-review.md` where the file no longer exists | Strip the link, keep display text |

Run `rumdl check --enable MD057 .` after migration to find any remaining broken relative links.

## Next Steps

After migration:

1. **Verify migration** - Check that all files were migrated correctly
2. **Test functionality** - Ensure Memory Bank tools work with new structure
3. **Fix broken links** - Run `rumdl check --enable MD057 .` and fix any broken relative links
4. **Update documentation** - Update any project documentation referencing old paths
5. **Commit changes** - Commit the migration to version control

## Related Prompts

- **initialize** - Use this for new projects (no legacy structure)
- **setup_synapse** - Use this to add Synapse after migration if needed
