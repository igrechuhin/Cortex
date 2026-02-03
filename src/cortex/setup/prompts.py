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
    "initialize_memory_bank": "🏗️",
    "setup_project_structure": "📁",
    "setup_cursor_integration": "⚙️",
    "populate_tiktoken_cache": "💾",
    "check_migration_status": "🔍",
    "migrate_memory_bank": "🔄",
    "migrate_project_structure": "📦",
}

_INIT_MEMORY_BANK_PROMPT = """Please initialize a Memory Bank in my project.

I need you to:
1. Create the .cortex/memory-bank/ directory
2. Generate all 7 core files from templates:
   - projectBrief.md - Foundation document
   - productContext.md - Product context and requirements
   - activeContext.md - Current active development context
   - systemPatterns.md - System architecture patterns
   - techContext.md - Technical context and decisions
   - progress.md - Development progress tracking
   - roadmap.md - Development roadmap and milestones
3. Initialize the metadata index at .cortex/index.json
4. Create initial snapshots in .cortex/history/

If an old format is detected, please migrate it to the current format.

Expected output format:
{
  "status": "success",
  "message": "Memory Bank initialized successfully",
  "files_created": 7,
  "total_tokens": <token_count>
}"""

_SETUP_PROJECT_STRUCTURE_PROMPT = """Please setup the standardized Cortex
project structure.

I need you to:
1. Create the .cortex/ directory structure
2. Setup .cortex/memory-bank/ with core files
3. Create .cortex/synapse/ directory for Synapse repository (optional)
4. Setup .cortex/plans/ directory for development plans
5. Generate all necessary template files
6. Create .cursor/ symlinks for IDE compatibility

Expected directory structure:
.cortex/
├── memory-bank/     # Core memory bank files
├── rules/           # Project-specific rules
│   └── local/       # Local rules
├── plans/           # Development plans
│   ├── active/      # Active plans
│   ├── completed/   # Completed plans
│   └── archived/    # Archived plans
├── config/          # Configuration files
├── history/         # Version history
└── archived/        # Archived content

.cursor/ (symlinks for IDE compatibility):
├── memory-bank -> ../.cortex/memory-bank
├── synapse -> ../.cortex/synapse
└── plans -> ../.cortex/plans

Expected output format:
{
  "status": "success",
  "message": "Project structure setup successfully",
  "directories_created": [...],
  "files_created": [...],
  "total_files": <count>
}"""

_SETUP_CURSOR_INTEGRATION_PROMPT = """Please setup Cursor IDE integration in my project.

I need you to:
1. Create .cursor/ directory with symlinks to .cortex/ subdirectories
2. Generate Cursor-specific config files
3. Setup MCP server configuration
4. Configure memory bank integration
5. Setup rules and context loading
6. Test the integration

Symlinks to create:
- .cursor/memory-bank -> ../.cortex/memory-bank
- .cursor/synapse -> ../.cortex/synapse
- .cursor/plans -> ../.cortex/plans

Configuration files to create:
- .cursor/mcp.json - MCP server config with Cortex server

MCP configuration should include:
{
  "mcpServers": {
    "cortex": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
    }
  }
}

Expected output format:
{
  "status": "success",
  "message": "Cursor integration setup successfully",
  "symlinks_created": [".cursor/memory-bank", ".cursor/synapse", ".cursor/plans"],
  "config_files": [".cursor/mcp.json"],
  "mcp_server": {
    "name": "cortex",
    "status": "configured"
  }
}"""

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

_CHECK_MIGRATION_STATUS_PROMPT = """Please check if my project needs migration
to the .cortex/ structure.

I need you to:
1. Detect the current project structure
2. Check if it's using an old directory structure
   (e.g., .cursor/memory-bank/, memory-bank/, .memory-bank/)
3. Identify what changes would be needed
4. Report the migration status

Check for legacy formats:
- .cursor/memory-bank/ (old Cursor-centric format)
- memory-bank/ (root-level format)
- .memory-bank/ (old standardized format)

Current format should be:
- .cortex/memory-bank/ (new standardized format)
- .cursor/ containing symlinks to .cortex/

Expected output format (up to date):
{"status": "up_to_date", "message": "Project is already using the "
".cortex/ structure", "current_location": ".cortex/memory-bank/",
"files_count": 7}

Expected output format (migration needed):
{"status": "migration_needed", "message": "Legacy format detected",
"old_location": "<detected_location>", "new_location":
".cortex/memory-bank/", "files_to_migrate": 7}

Expected output format (not initialized):
{"status": "not_initialized", "message": "No Memory Bank found",
"suggestion": "Run initialize_memory_bank to create one"}"""

_MIGRATE_MEMORY_BANK_PROMPT = """Please migrate my Memory Bank to the
.cortex/ structure.

I need you to:
1. Create the new .cortex/memory-bank/ directory
2. Copy all files from the old location to .cortex/memory-bank/
3. Preserve all content and version history
4. Update the metadata index to .cortex/index.json
5. Create snapshots in .cortex/history/
6. Create .cursor/ symlinks for IDE compatibility
7. Validate the migration succeeded

Migration mappings:
- .cursor/memory-bank/ -> .cortex/memory-bank/ (+ symlink .cursor/memory-bank)
- memory-bank/ -> .cortex/memory-bank/ (+ symlink .cursor/memory-bank)
- .memory-bank/knowledge/ -> .cortex/memory-bank/

Safety requirements:
- Automatic rollback if migration fails
- Content validation after migration
- Version history preservation
- Atomic operation (succeeds completely or fails completely)

Expected output format:
{
  "status": "success",
  "message": "Memory Bank migrated successfully",
  "old_location": "<detected_location>",
  "new_location": ".cortex/memory-bank/",
  "files_migrated": 7,
  "versions_migrated": <count>,
  "symlinks_created": [".cursor/memory-bank"],
  "duration_ms": <time>
}"""

_MIGRATE_PROJECT_STRUCTURE_PROMPT = """Please migrate my project to the
.cortex/ structure.

I need you to:
1. Detect the current structure
2. Create the new .cortex/ directory structure
3. Move existing files to correct locations
4. Preserve all content and history
5. Update references and links
6. Create .cursor/ symlinks for IDE compatibility
7. Validate the migration

Migration mappings:
- .cursor/memory-bank/ -> .cortex/memory-bank/
- .cursor/synapse/ -> .cortex/synapse/
- .cursor/plans/ -> .cortex/plans/
- memory-bank/ -> .cortex/memory-bank/
- rules/ -> .cortex/synapse/ (if using Synapse)
- .plan/ -> .cortex/plans/
- docs/plans/ -> .cortex/plans/

Symlinks to create in .cursor/:
- .cursor/memory-bank -> ../.cortex/memory-bank
- .cursor/synapse -> ../.cortex/synapse
- .cursor/plans -> ../.cortex/plans

Safety requirements:
- Dry-run mode available
- Automatic rollback on error
- Content validation after migration
- Link updating for broken references
- Backup creation before migration

Expected output format:
{
  "status": "success",
  "message": "Project structure migrated successfully",
  "migrations": {
    "memory_bank": {"from": "<old_location>", "to": ".cortex/memory-bank/", "files": 7},
    "synapse": {"from": "<old_location>", "to": ".cortex/synapse/", "files": <count>},
    "plans": {"from": "<old_location>", "to": ".cortex/plans/", "files": <count>}
  },
  "symlinks_created": [".cursor/memory-bank", ".cursor/synapse", ".cursor/plans"],
  "links_updated": <count>,
  "duration_ms": <time>
}"""


if not _config_status.memory_bank_initialized:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["initialize_memory_bank"])])
    def initialize_memory_bank() -> str:
        """Initialize a new Memory Bank with all core files."""
        return _INIT_MEMORY_BANK_PROMPT


if not _config_status.structure_configured:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["setup_project_structure"])])
    def setup_project_structure() -> str:
        """Setup the standardized .cortex/ project structure."""
        return _SETUP_PROJECT_STRUCTURE_PROMPT


if not _config_status.cursor_integration_configured:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["setup_cursor_integration"])])
    def setup_cursor_integration() -> str:
        """Setup Cursor IDE integration with symlinks and MCP server configuration."""
        return _SETUP_CURSOR_INTEGRATION_PROMPT


if not _config_status.tiktoken_cache_available:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["populate_tiktoken_cache"])])
    def populate_tiktoken_cache() -> str:
        """Populate bundled tiktoken cache with encoding files for offline operation."""
        return _POPULATE_TIKTOKEN_CACHE_PROMPT


if _config_status.migration_needed:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["check_migration_status"])])
    def check_migration_status() -> str:
        """Check if project needs migration to the .cortex/ structure."""
        return _CHECK_MIGRATION_STATUS_PROMPT


if _config_status.migration_needed:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["migrate_memory_bank"])])
    def migrate_memory_bank() -> str:
        """Migrate Memory Bank to the .cortex/ structure."""
        return _MIGRATE_MEMORY_BANK_PROMPT


if _config_status.migration_needed:

    @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["migrate_project_structure"])])
    def migrate_project_structure() -> str:
        """Migrate project to the .cortex/ structure."""
        return _MIGRATE_PROJECT_STRUCTURE_PROMPT
