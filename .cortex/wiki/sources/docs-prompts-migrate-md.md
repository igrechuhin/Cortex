# Migrate

This prompt template guides you through migrating a project from legacy structure to the new `.cortex/` structure.

## Prerequisites

- Cortex server installed and configured
- Project with legacy structure detected (a leftover real `.cursor/memory-bank/` directory from a pre-removal Cortex version, root-level `memory-bank/`, or `.memory-bank/`)
- Git repository initialized (for version history preservation)

## Prompt

```text
Please migrate my project from legacy structure to the new .cortex/ structure.
```

## What Happens

The assistant will perform complete migration:

### Step 1: Detect legacy structure

- Checks for legacy formats:
  - `.cursor/memory-bank/` (old Cursor-centric format — a real directory, not a
    symlink; a plain `.cursor/memory-bank` symlink is a leftover from a
    pre-removal Cortex version and is cleaned up automatically on server
    start, not by this migration)
  - `memory-bank/` (root-level format)
  - `.memory-bank/` (old standardized format)
  - Any other legacy locations

### Step 2: Initialize new .cortex/ structure

- Creates new `.cortex/` directory structure (same as `initialize` prompt)
- Creates `.cortex/memory-bank/`, `.cortex/plans/`, `.cortex/config/`
- Initializes Memory Bank with 7 core files (if not already present)
- Sets up MCP server configuration (`.mcp.json`) — includes cortex, serena, and
  codegraph MCP server entries (same as the `initialize` prompt's Step 3)
- Initializes the CodeGraph index (same as the `initialize` prompt's Step 3b)

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

#### Step 2b: Detect language and scaffold Synapse rules/scripts

After `.cortex/` structure exists (Step 2), the migration flow **detects primary
language(s)** from project markers (for example `Package.swift`, `package.json`,
`pom.xml`, `build.gradle` / `build.gradle.kts`, `settings.gradle` / `settings.gradle.kts`,
`gradlew` / `gradlew.bat`, `gradle/wrapper/gradle-wrapper.properties`,
`mvnw` / `mvnw.cmd`, `.mvn/wrapper/maven-wrapper.properties`, `Cargo.toml`,
`go.mod`, `*.sln`, `*.csproj`, `pyproject.toml`, `setup.py`, `setup.cfg`, `tox.ini`, `requirements.txt`,
`Pipfile`, `Pipfile.lock`, `poetry.lock`, `uv.lock`, `pdm.toml`, `pdm.lock`, `pixi.toml`,
`environment.yml` / `environment.yaml`,
`conda-lock.yml`, `.python-version`, `MANIFEST.in`, `constraints.txt`, `runtime.txt`, `.flake8`,
`pytest.ini`, `.coveragerc`, `pyrightconfig.json`, `mypy.ini`, `.mypy.ini`, `ruff.toml`, `.ruff.toml`,
`noxfile.py`, dominant `*.py`) and can scaffold language-specific
content without manual copy-paste:

1. **Detect** — `detect_languages_for_migration` runs on the project root; results
   appear on the migration report as `detected_languages` (list, ordered).
2. **Confirm** — When running migration interactively, confirm or adjust the
   detected set before relying on scaffolded files.
3. **Rules** — Starter `.mdc` files are copied from
   `.cortex/synapse/rules/_templates/<lang>/` into
   `.cortex/synapse/rules/<lang>/` when templates exist; existing files are not
   overwritten.
4. **Scripts** — For languages without Python analysis scripts under
   `scripts/python/`, migration may create `.cortex/synapse/scripts/<lang>/`
   stubs (for example `run_quality_check.sh` and `README.md`) so you can wire
   your native toolchain.
5. **Report** — The migration output lists what was created under
   `rules_scaffolded`, `scripts_scaffolded`, and `scaffolded_languages`.

**Quality gate routing:** `run_quality_gate()` (Phase A) runs in a detached worker
that resolves the project language via framework adapters and
`LanguageQualityRouter`, then executes the matching adapter (for example
`SwiftAdapter` for SwiftPM projects). Python Synapse scripts under
`scripts/python/` apply only when the detected language is Python; other
languages use adapter commands or language-specific stubs. Markdown lint
(`rumdl`) still runs for all projects when included in Phase A.

### Step 3: Migrate legacy files

Only the 7 canonical memory bank core files (`projectbrief.md`, `productContext.md`,
`activeContext.md`, `systemPatterns.md`, `techContext.md`, `progress.md`,
`roadmap.md`; plus the legacy `memorybankinstructions.md` if present) are copied
into `.cortex/memory-bank/`. Any other file found in a legacy memory-bank
directory (topic notes, analysis files, ad-hoc documentation) is moved to
`.cortex/notes/` instead — with a one-line summary + link added to the most
relevant memory bank file so agents can discover it — and reported separately.

- Core file mappings:
  - `.cursor/memory-bank/<core-file>` → `.cortex/memory-bank/<core-file>`
  - `memory-bank/<core-file>` (repo root) → `.cortex/memory-bank/<core-file>`
  - `.memory-bank/knowledge/<core-file>` → `.cortex/memory-bank/<core-file>`
- Other directory mappings:
  - `.cursor/synapse/` → `.cortex/synapse/` (only if a real directory, not a symlink)
  - `.cursor/plans/` → `.cortex/plans/` (only if a real directory, not a symlink)
  - `rules/` → `.cortex/synapse/` (if using Synapse)
  - `.plan/` → `.cortex/plans/`
  - `docs/plans/` → `.cortex/plans/`

### Step 4: Preserve content and history

- Copies all files preserving content
- Migrates version history to `.cortex/history/`
- Updates metadata index to `.cortex/index.json`
- Preserves all snapshots and version information

### Step 5: Update references and links

Scans every file in `.cortex/memory-bank/` and `.cortex/plans/` for stale path
references and rewrites them:

- `.cursor/memory-bank/` → `.cortex/memory-bank/`
- `.cursor/plans/` → `.cortex/plans/`
- `.cursor/synapse/` → `.cortex/synapse/`
- `.cursor/scripts/` → removed or replaced with actual tool invocations
- `.cursor/rules/` → removed (rules now live in `.cortex/synapse/`)
- Any instruction in `memorybankinstructions.md` that says to sync
  `.cursor/memory-bank/` or `.cursor/rules/` is removed — Cortex no longer
  maintains a `.cursor/` workspace

### Step 6: Validate migration

- Verifies all 7 core files exist in `.cortex/memory-bank/`
- Verifies any non-standard files were relocated to `.cortex/notes/` (not left in `memory-bank/`)
- Verifies no stale `.cursor/` path references remain in `.cortex/memory-bank/` or `.cortex/plans/` files
- Ensures version history is intact

### Step 7: Remove legacy directories

After migrating all content, removes the now-empty legacy directories
(`.cursor/memory-bank/`, `.cursor/plans/`, `.cursor/synapse/`, `memory-bank/`,
`.memory-bank/`, etc.). This step does **not** recreate `.cursor/` or any
symlinks under it — Cortex no longer maintains a `.cursor/` workspace. Any
leftover `.cursor/` artifacts (symlinks, synced agent files, generated
`mcp.json`) from a prior Cortex version are removed automatically the next
time the Cortex MCP server starts.

## Expected Output

### Successful Migration

```json
{
  "status": "success",
  "message": "Project migrated successfully",
  "legacy_locations_detected": [
    "cursor_legacy_memory_bank",
    "memory-bank"
  ],
  "migrations": {
    "memory_bank": {"from": "cursor_legacy_memory_bank", "to": ".cortex/memory-bank/", "files": 7},
    "synapse": {"from": ".cursor/synapse", "to": ".cortex/synapse/", "files": 12},
    "plans": {"from": ".cursor/plans", "to": ".cortex/plans/", "files": 5}
  },
  "non_standard_files_relocated": [
    "vdsp_vsubd_notes.md"
  ],
  "directories_created": [
    ".cortex",
    ".cortex/memory-bank",
    ".cortex/plans"
  ],
  "path_references_updated": 3,
  "detected_language": "python",
  "post_edit_hook_written": true,
  "detected_languages": ["python"],
  "scaffolded_languages": [],
  "rules_scaffolded": [],
  "scripts_scaffolded": [],
  "files_migrated": 24,
  "versions_migrated": 15,
  "legacy_directories_removed": [
    "cursor_legacy_memory_bank",
    "memory-bank"
  ],
  "duration_ms": 1234
}
```

(`cursor_legacy_memory_bank` stands in for the pre-migration `.cursor/memory-bank/`
real directory, a leftover from a pre-removal Cortex version — not a symlink.)

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
- Project has files in old locations (a leftover real `.cursor/memory-bank/` directory, root `memory-bank/`, or `.memory-bank/`)

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
| `.cursor/memory-bank/` (real directory, not a symlink) | `.cortex/memory-bank/` | Core files only; other files go to `.cortex/notes/` |
| `memory-bank/` (repo root) | `.cortex/memory-bank/` | Core files only; other files go to `.cortex/notes/` |
| `.memory-bank/knowledge/` | `.cortex/memory-bank/` | Migrates knowledge files |
| `.cursor/synapse/` (real directory, not a symlink) | `.cortex/synapse/` | |
| `.cursor/plans/` (real directory, not a symlink) | `.cortex/plans/` | |
| `rules/` | `.cortex/synapse/` | If using Synapse |
| `.plan/` | `.cortex/plans/` | Legacy plan directory |
| `docs/plans/` | `.cortex/plans/` | Documentation plans |

## Markdown Linting After Migration

After migration, plans live directly under `.cortex/plans/` — there is no
`.cursor/` symlink involved anymore. Linters such as rumdl resolve relative
links from the real file location, so links that referenced sibling plans via
an old `.cursor/plans/` root from a prior Cortex version must be verified.

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
