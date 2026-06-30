# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Setup and migration prompt templates.

These prompts are registered on the main MCP server when this module is
imported and project configuration indicates setup is needed. Import from
main.py only when should_mount_setup() is True so that setup prompts are
conditionally available.
"""

from pathlib import Path

from cortex.core.icon_helpers import create_emoji_icon
from cortex.server import mcp
from cortex.setup.post_edit_hook_runtime import apply_project_post_edit_hook
from cortex.tools.config import get_project_config_status

_config_status = get_project_config_status()

PROMPT_ICONS: dict[str, str] = {
    "initialize": "🏗️",
    "migrate": "🔄",
    "populate_tiktoken_cache": "💾",
}

INITIALIZE_PROMPT = """Please initialize Cortex in my project with complete setup.

This prompt performs complete project initialization including:
1. Creating the .cortex/ directory structure (memory-bank, plans, config)
2. Initializing Memory Bank with all 7 core files
3. Setting up Cursor IDE integration (symlinks + mcp.json)
4. Optionally setting up Synapse with default URL

I need you to:

**Step 1: Create .cortex/ directory structure**
- Create .cortex/ directory
- Create .cortex/memory-bank/ directory
- Create .cortex/plans/ directory
- Create .cortex/config/ directory

**Step 2: Initialize Memory Bank with 7 core files**
Generate all 7 core files from templates:
- projectBrief.md - Foundation document
- productContext.md - Product context and requirements
- activeContext.md - Current active development context
- systemPatterns.md - System architecture patterns
- techContext.md - Technical context and decisions
- progress.md - Development progress tracking
- roadmap.md - Development roadmap and milestones
- Initialize the metadata index at .cortex/index.json
- Create initial snapshots in .cortex/history/

**Step 3: Setup Cursor IDE integration**
- Create .cursor/ directory with symlinks to .cortex/ subdirectories:
  - .cursor/memory-bank -> ../.cortex/memory-bank
  - .cursor/synapse -> ../.cortex/synapse
  - .cursor/plans -> ../.cortex/plans
- Create `.cursor/mcp.json` with MCP server configuration (for Cursor IDE users):
{{
  "mcpServers": {{
    "cortex": {{
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
    }},
    "serena": {{
      "command": "uv",
      "args": ["--from", "git+https://github.com/oraios/serena.git", "serena", "start-mcp-server", "--context", "ide-assistant", "--project", "<absolute_project_root>"]
    }},
    "codegraph": <see Step 3b for the correct entry>
  }}
}}
- Also create `.mcp.json` in the project root with the same `mcpServers` content (for Claude Code CLI users).
  Use `"type": "stdio"` on the cortex entry if running from a local venv.

**Step 3b: Initialize CodeGraph**
Resolve the binary, write the mcp.json entry, and index the project:

1. Run `which codegraph` (or `where codegraph` on Windows):
   - If found on PATH → use `"command": "codegraph", "args": ["serve", "--mcp"]`
   - If not found → check `~/Repo/codegraph/dist/bin/codegraph.js` (local dev checkout):
     - If that file exists → use `"command": "node", "args": ["<absolute_path>", "serve", "--mcp"]`
     - Otherwise → omit the `codegraph` key from mcp.json and skip steps 2–3 (note in output)

1b. Check Node.js version (for local checkout only):
   - Run `node --version`
   - If Node 25+: add `"env": {{"CODEGRAPH_ALLOW_UNSAFE_NODE": "1"}}` to the mcp.json entry
     (indexing on Node 25+ may be unstable; recommend Node 22 LTS for production)
   - If Node 20–24: no env override needed

2. Write the resolved entry into both `.cursor/mcp.json` and `.mcp.json` under `mcpServers.codegraph`
   (merge, do not overwrite other keys).

3. Run `CODEGRAPH_ALLOW_UNSAFE_NODE=1 node <path> init` (or `codegraph init`) in the project root:
   - This creates `.codegraph/` and indexes all source files (takes 5–60s)
   - Add `.codegraph/` to `.gitignore` if not already present
   - If init fails or times out, skip silently — CodeGraph will index on first MCP start

**Step 4: Optionally setup Synapse (recommended)**
- Add Synapse repository as Git submodule to .cortex/synapse/
- Use default URL: https://github.com/igrechuhin/Synapse.git
- Or skip this step if you don't need shared rules/prompts

**Step 5: Update .gitignore for Cortex transient files**
- Open or create the root `.gitignore` file.
- Add the following entries if they are not already present (append under a
  `# Cortex MCP (transient/generated files)` comment block):
  ```
  # Cortex MCP (transient/generated files)
  .cortex/.session/
  .cortex/.cache/
  .cortex/history/
  .cortex-backup-*/
  ```
- Do NOT add `.cortex/memory-bank/`, `.cortex/plans/`, or `.cortex/config/` —
  those contain project data that should be tracked by version control.

**Step 5b: Emit post-edit quality hook**
Detect the project's primary language (inspect pyproject.toml / setup.py for Python,
Package.swift for Swift, package.json for TypeScript/JavaScript, Cargo.toml for Rust,
go.mod for Go, pom.xml / build.gradle for Java).

Then configure your tool's **post-edit hook** mechanism so it runs after edit operations
(whatever your environment calls this: "post-edit hook", "after-edit hook",
"on-save hook", "post-tool hook", etc.).

**Hook contract (tool-agnostic):**
- Trigger: after an edit is applied (or, if your tool only supports it, after file save)
- Working directory: project root
- Command: a fast, language-appropriate quality gate implemented as a script under
  `.cortex/synapse/scripts/<lang>/`
- Config update behavior: if your tool stores hook config in a file, **merge** changes
  and do not overwrite unrelated keys/settings.

If you are using Claude Code specifically, write/merge the following into
`.claude/settings.json` (create `.claude/` if needed; merge — do not overwrite unrelated keys):

{{
  "hooks": {{
    "PostToolUse": [
      {{
        "matcher": "Edit",
        "hooks": [
          {{
            "type": "command",
            "command": "<language-specific command from table below>"
          }}
        ]
      }}
    ]
  }}
}}

Language → command mapping:
- python      → python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20
- swift       → swift build 2>&1 | tail -20
- typescript  → npm test --if-present 2>&1 | tail -20
- javascript  → npm test --if-present 2>&1 | tail -20
- rust        → cargo test 2>&1 | tail -20
- go          → go test ./... 2>&1 | tail -20
- java        → ./mvnw test -q 2>&1 | tail -20
- unknown     → skip hook; warn: "No post-edit hook template for <lang>. Add one to .claude/settings.json manually."

If `.claude/settings.json` already contains the exact command, skip (no-op).
Report `post_edit_hook_written: true/false` and `detected_language: <lang>` in output.

**Step 6: Optional pre-commit hook for markdown lint**
- If the project has a Git repository (.git exists):
 - If .pre-commit-config.yaml does NOT exist: create it with a single local hook that runs markdown lint on all .md/.mdc files (id: markdownlint, name: Markdown lint (rumdl, all files), entry: uv run rumdl check --fix ., language: system, pass_filenames: false, always_run: true). This requires rumdl (for example via uv sync --extra dev) and pre-commit (e.g. pip install pre-commit).
 - If .pre-commit-config.yaml already exists: add the same markdownlint hook to the existing local repos/hooks so commits run markdown lint via rumdl.
  - Run `pre-commit install` to install the git hook (or instruct the user to run it once). If pre-commit is not installed, instruct the user to install it and run pre-commit install.
- If the project is not a Git repository, skip this step.

Expected directory structure after initialization:
.cortex/
├── memory-bank/     # Core memory bank files (7 files)
├── plans/           # Development plans
├── config/          # Configuration files
└── history/         # Version history

.cursor/ (symlinks for IDE compatibility):
├── memory-bank -> ../.cortex/memory-bank
├── synapse -> ../.cortex/synapse
└── plans -> ../.cortex/plans

Expected output format:
{{
  "status": "success",
  "message": "Cortex initialized successfully",
  "directories_created": [".cortex", ".cortex/memory-bank", ".cortex/plans", ".cortex/config", ".cursor"],
  "files_created": 7,
  "symlinks_created": [".cursor/memory-bank", ".cursor/synapse", ".cursor/plans"],
  "config_files": [".cursor/mcp.json"],
  "synapse_setup": <true/false>,
  "gitignore_updated": <true/false>,
  "detected_language": "<lang or unknown>",
  "post_edit_hook_written": <true/false>,
  "pre_commit_installed": <true/false or omitted if skipped>,
  "total_tokens": <token_count>
}}

If an old format is detected during initialization, please migrate it to the current format."""

SETUP_CODEGRAPH_PROMPT = """Please add CodeGraph to this Cortex-initialized project.

CodeGraph provides semantic code intelligence (callers, callees, impact radius, symbol search)
to AI agents via MCP. It's 100% local, auto-syncing, and requires no cloud access.

**Step 1: Resolve the codegraph binary path**
- Run `which codegraph` to check if it's on PATH.
- If found: use the returned path as `<codegraph_binary>`.
- If not found: check common local checkout locations:
  - `~/Repo/codegraph/dist/bin/codegraph.js` (run with `node`)
  - `/usr/local/bin/codegraph`
  - Ask the user for the path if none found.
- For a local Node.js checkout use: `"command": "node", "args": ["<absolute_path_to_codegraph.js>", "serve", "--mcp"]`
- For a PATH-installed binary use: `"command": "codegraph", "args": ["serve", "--mcp"]`

**Step 1b: Check Node.js version (for local checkout only)**
- Run `node --version` to get the current Node.js version.
- If Node version is 25.x or higher: the MCP server entry must include
  `"env": {{"CODEGRAPH_ALLOW_UNSAFE_NODE": "1"}}` to bypass the startup version check.
  Note: indexing on Node 25+ may be unstable due to a V8 WASM bug; recommend installing
  Node 22 LTS (`brew install node@22`) for production use.
- If Node version is 20–24: no env override needed.
- If using a PATH-installed `codegraph` binary: skip this step (it manages its own runtime).

**Step 2: Add codegraph to the MCP config**
Determine the correct config file for the active agent:
- Claude Code CLI: `.mcp.json` in the project root (create if missing with `{{"mcpServers": {{}}}}`)
- Cursor IDE: `.cursor/mcp.json` (create if missing)
- Both present: update both

Merge the following entry under `mcpServers` — do NOT overwrite existing entries:
  - If binary is on PATH, Node 20–24:
    `"codegraph": {{"command": "codegraph", "args": ["serve", "--mcp"]}}`
  - If binary is on PATH, Node 25+:
    `"codegraph": {{"command": "codegraph", "args": ["serve", "--mcp"], "env": {{"CODEGRAPH_ALLOW_UNSAFE_NODE": "1"}}}}`
  - If using a local Node.js checkout, Node 20–24:
    `"codegraph": {{"command": "node", "args": ["<absolute_path_to_codegraph.js>", "serve", "--mcp"]}}`
  - If using a local Node.js checkout, Node 25+:
    `"codegraph": {{"command": "node", "args": ["<absolute_path_to_codegraph.js>", "serve", "--mcp"], "env": {{"CODEGRAPH_ALLOW_UNSAFE_NODE": "1"}}}}`

**Step 3: Initialize CodeGraph index**
- Run `CODEGRAPH_ALLOW_UNSAFE_NODE=1 node <path> init` (or `codegraph init`) in the project root.
- This builds the semantic graph into `.codegraph/` (takes 5–60s depending on project size).
- Add `.codegraph/` to `.gitignore` if not already present (it's a local-only index).
- If init fails or times out, skip — CodeGraph will index on next `codegraph serve --mcp` start.

**Step 4: Add permissions for Claude Code**
- If `.claude/settings.json` exists, merge `"mcp__codegraph__*"` into `permissions.allow`:
{{
  "permissions": {{
    "allow": ["mcp__codegraph__*"]
  }}
}}
- Do NOT overwrite other permissions entries.

Expected output format:
{{
  "status": "success",
  "codegraph_binary": "<resolved path or 'codegraph' if on PATH>",
  "node_version": "<e.g. v22.14.0 or N/A for PATH binary>",
  "unsafe_node_env_added": <true/false>,
  "mcp_json_updated": true,
  "codegraph_init_run": <true/false>,
  "gitignore_updated": <true/false>,
  "permissions_updated": <true/false>
}}"""

POPULATE_TIKTOKEN_CACHE_PROMPT = """Please populate the bundled tiktoken cache
with encoding files.

The tiktoken cache is missing or empty, which may cause slower token
counting or require network access.

I need you to:
1. Check if `src/cortex/resources/tiktoken_cache/` directory exists
   (create if needed)
2. Run the populate script: `python3 scripts/populate_tiktoken_cache.py`
   - This downloads common encodings: cl100k_base, o200k_base, p50k_base
   - Or specify custom encodings:
     `python3 scripts/populate_tiktoken_cache.py --encodings cl100k_base o200k_base`
3. Verify cache files were downloaded (tiktoken uses SHA-1 hash of URL
   as filename)
4. Test that token counting works with cached files

Expected output format:
{{
  "status": "success",
  "message": "Tiktoken cache populated successfully",
  "cache_directory": "src/cortex/resources/tiktoken_cache/",
  "encodings_downloaded": ["cl100k_base", "o200k_base", "p50k_base"],
  "files_created": 3,
  "total_size_bytes": <size>
}}

If download fails:
- Check network connectivity
- Verify URLs are accessible
- Try downloading encodings one at a time
- Report which encodings failed and why"""

MIGRATE_PROMPT = """Please migrate my project from legacy structure to the new .cortex/ structure.

This prompt performs complete migration including:
1. Detecting legacy structure
2. Initializing new .cortex/ structure
3. Migrating core files; relocating non-standard files
4. Updating internal path references
5. Replacing legacy directories with symlinks
6. Validating migration

**Step 1: Detect legacy structure**
Check for legacy formats:
- .cursor/memory-bank/ (old Cursor-centric format)
- memory-bank/ (root-level format)
- .memory-bank/ (old standardized format)
- Any other legacy locations

**Step 2: Initialize new .cortex/ structure**
First, create the new structure (same as initialize prompt):
- Create .cortex/ directory structure (memory-bank, plans, config)
- Initialize Memory Bank with 7 core files (if not already present)
- Setup Cursor integration (symlinks + mcp.json) — include cortex, serena, and codegraph MCP server entries (same as initialize Step 3)
- Update .gitignore (same as initialize Step 5)
- Initialize CodeGraph index (same as initialize Step 3b)

**Step 2b: Emit post-edit quality hook**
Detect the project's primary language using common project manifests and conventions
(pick a best guess; if ambiguous, choose the most likely "primary" language).

If no clear primary language can be determined, treat as `unknown` and skip the hook (warn).

Then write/merge the following into the project's `.claude/settings.json`
(create `.claude/` if needed; merge — do not overwrite unrelated keys):

{{
  "hooks": {{
    "PostToolUse": [
      {{
        "matcher": "Edit",
        "hooks": [
          {{
            "type": "command",
            "command": "<language-specific command from table below>"
          }}
        ]
      }}
    ]
  }}
}}

Prefer a scripts-based hook (keeps agent instructions minimal and consistent):

- For a recognized language (e.g. `python`, `swift`), set `command` to run an appropriate
  script from `.cortex/synapse/scripts/<lang>/` (choose a fast gate like build/tests).
- Prefer `post_edit_hook.py` if present in that language folder; otherwise pick an
  existing script in the folder that best matches "fast post-edit quality check".
- If `unknown`, skip hook; warn: "No post-edit hook template for <lang>. Configure your tool's hook manually."

If `.claude/settings.json` already contains the exact command, skip (no-op).
Report `post_edit_hook_written: true/false` and `detected_language: <lang>` in output.

**Step 3: Migrate files — core files only into memory-bank/**
The 7 canonical memory bank core files are:
  projectbrief.md, productContext.md, activeContext.md,
  systemPatterns.md, techContext.md, progress.md, roadmap.md

Additionally allow: memorybankinstructions.md (legacy instructions file)

Migration mappings for core files:
- .cursor/memory-bank/<core-file> -> .cortex/memory-bank/<core-file>
- memory-bank/<core-file> -> .cortex/memory-bank/<core-file>
- .memory-bank/knowledge/<core-file> -> .cortex/memory-bank/<core-file>

For any OTHER files found in legacy memory-bank directories
(e.g. topic notes, analysis files, ad-hoc documentation):
- Do NOT copy them into .cortex/memory-bank/
- Move them to .cortex/notes/ instead
- These are project-specific reference files, not inter-session context
- For each relocated file, add a one-line summary + link in the most relevant
  memory bank file (techContext.md for tech-specific notes, systemPatterns.md
  for architectural notes) so agents can discover them. Example:
    ⚠️ vDSP_vsubD has counter-intuitive param order. See .cortex/notes/vdsp_vsubd_notes.md
- Report each relocated file in the migration output

Other directory mappings:
- .cursor/synapse/ -> .cortex/synapse/ (+ symlink .cursor/synapse)
- .cursor/plans/ -> .cortex/plans/ (+ symlink .cursor/plans)
- rules/ -> .cortex/synapse/ (if using Synapse)
- .plan/ -> .cortex/plans/
- docs/plans/ -> .cortex/plans/

**Step 4: Preserve content and history**
- Copy all files preserving content
- Migrate version history to .cortex/history/
- Update metadata index to .cortex/index.json
- Preserve all snapshots and version information

**Step 5: Update internal path references in memory bank content**
Scan every file in .cortex/memory-bank/ and .cortex/plans/ for stale path
references and rewrite them:

- .cursor/memory-bank/ -> .cortex/memory-bank/
- .cursor/plans/ -> .cortex/plans/
- .cursor/synapse/ -> .cortex/synapse/
- .cursor/scripts/ -> remove or replace with actual tool invocations
- .cursor/rules/ -> remove (rules now live in .cortex/synapse/)
- Any instruction in memorybankinstructions.md that says to sync
  .cursor/memory-bank/ or .cursor/rules/ should be updated to reflect
  the .cortex/ paths (or removed if the sync step no longer applies)

**Step 6: Replace legacy directories with symlinks**
After migrating all content:
- Remove .cursor/memory-bank/ directory (the real files are now in .cortex/)
- Create symlink: .cursor/memory-bank -> ../.cortex/memory-bank
- Remove .cursor/plans/ directory
- Create symlink: .cursor/plans -> ../.cortex/plans
- Remove .cursor/synapse/ directory (if present)
- Create symlink: .cursor/synapse -> ../.cortex/synapse
- Verify each symlink resolves correctly

This ensures that tools reading .cursor/ paths still work while the
authoritative content lives in .cortex/.

**Step 7: Validate migration**
- Verify all 7 core files exist in .cortex/memory-bank/
- Verify any non-standard files were relocated to .cortex/notes/ (not left in memory-bank/)
- Verify .cursor/ symlinks resolve to .cortex/ directories
- Verify no stale .cursor/ path references remain in .cortex/memory-bank/ or .cortex/plans/ files
- Ensure version history is intact

Safety requirements:
- Automatic rollback if migration fails
- Content validation after migration
- Version history preservation
- Atomic operation (succeeds completely or fails completely)
- Backup creation before migration (optional but recommended)

Expected output format:
{{
  "status": "success",
  "message": "Project migrated successfully",
  "legacy_locations_detected": ["<old_location1>", "<old_location2>"],
  "migrations": {{
    "memory_bank": {{"from": "<old_location>", "to": ".cortex/memory-bank/", "files": 7}},
    "synapse": {{"from": "<old_location>", "to": ".cortex/synapse/", "files": <count>}},
    "plans": {{"from": "<old_location>", "to": ".cortex/plans/", "files": <count>}}
  }},
  "non_standard_files_relocated": ["<file1>", "<file2>"],
  "directories_created": [".cortex", ".cortex/memory-bank", ".cortex/plans", ".cursor"],
  "symlinks_created": [".cursor/memory-bank", ".cursor/synapse", ".cursor/plans"],
  "path_references_updated": <count>,
  "gitignore_updated": <true/false>,
  "detected_language": "<lang or unknown>",
  "post_edit_hook_written": <true/false>,
  "files_migrated": <total_count>,
  "versions_migrated": <count>,
  "legacy_directories_removed": ["<old_location1>", "<old_location2>"],
  "duration_ms": <time>
}}"""


# Initialize prompt: shown when project is not initialized and not configured
# Exclude migration cases (migrate prompt handles those)
if (
    not _config_status.memory_bank_initialized
    and not _config_status.structure_configured
    and not _config_status.migration_needed
):

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["initialize"])])
    def initialize() -> str:
        """Complete project initialization.

        Creates:
        - .cortex/ directory structure (memory-bank, plans, config)
        - Memory bank with 7 core files
        - Cursor integration (symlinks + mcp.json)
        - Optional Synapse setup with default URL
        """
        _ = apply_project_post_edit_hook(Path.cwd())
        return INITIALIZE_PROMPT


# Migrate prompt: shown when migration is needed
if _config_status.migration_needed:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["migrate"])])
    def migrate() -> str:
        """Migrate legacy structure to new .cortex/ structure.

        Steps:
        1. Initialize new .cortex/ structure
        2. Migrate legacy files
        3. Remove legacy directories
        """
        _ = apply_project_post_edit_hook(Path.cwd())
        return MIGRATE_PROMPT


# Populate tiktoken cache: shown when cache is not available
if not _config_status.tiktoken_cache_available:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["populate_tiktoken_cache"])])
    def populate_tiktoken_cache() -> str:
        """Populate bundled tiktoken cache with encoding files for offline operation."""
        return POPULATE_TIKTOKEN_CACHE_PROMPT
