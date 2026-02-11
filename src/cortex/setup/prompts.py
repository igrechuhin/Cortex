# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Setup and migration prompt templates.

These prompts are registered on the main MCP server when this module is
imported and project configuration indicates setup is needed. Import from
main.py only when should_mount_setup() is True so that setup prompts are
conditionally available.
"""

from cortex.core.icon_helpers import create_emoji_icon
from cortex.server import mcp
from cortex.tools.config_status import get_project_config_status

_config_status = get_project_config_status()

PROMPT_ICONS: dict[str, str] = {
    "initialize": "🏗️",
    "migrate": "🔄",
    "populate_tiktoken_cache": "💾",
}

_INITIALIZE_PROMPT = """Please initialize Cortex in my project with complete setup.

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
- Create .cursor/mcp.json with MCP server configuration:
{{
  "mcpServers": {{
    "cortex": {{
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
    }}
  }}
}}

**Step 4: Optionally setup Synapse (recommended)**
- Add Synapse repository as Git submodule to .cortex/synapse/
- Use default URL: https://github.com/igrechuhin/Synapse.git
- Or skip this step if you don't need shared rules/prompts

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
  "total_tokens": <token_count>
}}

If an old format is detected during initialization, please migrate it to the current format."""

_POPULATE_TIKTOKEN_CACHE_PROMPT = """Please populate the bundled tiktoken cache
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

_MIGRATE_PROMPT = """Please migrate my project from legacy structure to the new .cortex/ structure.

This prompt performs complete migration including:
1. Detecting legacy structure
2. Initializing new .cortex/ structure (via initialize steps)
3. Migrating all legacy files to new structure
4. Validating migration
5. Removing legacy directories after successful migration

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
- Setup Cursor integration (symlinks + mcp.json)

**Step 3: Migrate legacy files**
Copy/move all files from legacy locations to new structure:

Migration mappings:
- .cursor/memory-bank/ -> .cortex/memory-bank/ (+ symlink .cursor/memory-bank)
- memory-bank/ -> .cortex/memory-bank/ (+ symlink .cursor/memory-bank)
- .memory-bank/knowledge/ -> .cortex/memory-bank/
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

**Step 5: Update references and links**
- Update any internal references to old paths
- Fix broken links in memory bank files
- Update configuration files with new paths

**Step 6: Validate migration**
- Verify all files were migrated successfully
- Check that content is preserved correctly
- Validate symlinks are working
- Ensure version history is intact

**Step 7: Remove legacy directories**
- Only after successful validation
- Remove old .cursor/memory-bank/, memory-bank/, .memory-bank/ directories
- Keep .cursor/ directory but remove old content
- Clean up any other legacy locations

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
  "directories_created": [".cortex", ".cortex/memory-bank", ".cortex/plans", ".cursor"],
  "symlinks_created": [".cursor/memory-bank", ".cursor/synapse", ".cursor/plans"],
  "files_migrated": <total_count>,
  "versions_migrated": <count>,
  "links_updated": <count>,
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
        return _INITIALIZE_PROMPT


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
        return _MIGRATE_PROMPT


# Populate tiktoken cache: shown when cache is not available
if not _config_status.tiktoken_cache_available:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["populate_tiktoken_cache"])])
    def populate_tiktoken_cache() -> str:
        """Populate bundled tiktoken cache with encoding files for offline operation."""
        return _POPULATE_TIKTOKEN_CACHE_PROMPT
