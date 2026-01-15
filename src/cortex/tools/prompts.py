"""
MCP Prompt Templates

This module exposes prompt templates via the MCP protocol for one-time
Memory Bank operations. These prompts guide users through setup, initialization,
and migration tasks.

Prompts provide better user experience than tools for:
- One-time setup operations
- Initial project configuration
- Migration from old formats
- Rare administrative tasks

Directory Structure:
    All Cortex data is stored in .cortex/ directory:
    .cortex/
    ├── memory-bank/     # Core memory bank files
    ├── rules/           # Project rules
    ├── plans/           # Development plans
    ├── config/          # Configuration files
    ├── history/         # Version history
    └── archived/        # Archived content

    .cursor/ contains symlinks for IDE compatibility:
    .cursor/
    ├── memory-bank -> ../.cortex/memory-bank
    ├── synapse -> ../.cortex/synapse
    └── plans -> ../.cortex/plans

Conditional Registration:
    Setup and migration prompts are only registered when needed:
    - initialize_memory_bank: Only if memory bank not initialized
    - setup_project_structure: Only if structure not configured
    - setup_cursor_integration: Only if Cursor integration not configured
    - check_migration_status: Only if migration needed
    - migrate_memory_bank: Only if migration needed
    - migrate_project_structure: Only if migration needed
    - setup_synapse: Always available (optional feature)
"""

from cortex.server import mcp
from cortex.tools.config_status import get_project_config_status

# Check project configuration status at import time
_config_status = get_project_config_status()

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

_SETUP_PROJECT_STRUCTURE_PROMPT = """Please setup the standardized Cortex project structure.

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


# Conditionally register initialize_memory_bank only if memory bank not initialized
if not _config_status["memory_bank_initialized"]:

    @mcp.prompt()
    def initialize_memory_bank() -> str:
        """Initialize a new Memory Bank with all core files.

        Creates the .cortex/memory-bank/ directory structure with 7 core files:
        - projectBrief.md - Foundation document
        - productContext.md - Product context and requirements
        - activeContext.md - Current active development context
        - systemPatterns.md - System architecture patterns
        - techContext.md - Technical context and decisions
        - progress.md - Development progress tracking
        - roadmap.md - Development roadmap and milestones

        Returns:
            Prompt message guiding the assistant to initialize Memory Bank
        """
        return _INIT_MEMORY_BANK_PROMPT


# Conditionally register setup_project_structure only if structure not configured
if not _config_status["structure_configured"]:

    @mcp.prompt()
    def setup_project_structure() -> str:
        """Setup the standardized .cortex/ project structure.

        Creates:
        - .cortex/memory-bank/ - Core memory bank files
        - .cortex/synapse/ - Synapse repository (shared rules, prompts, config)
        - .cortex/plans/ - Development plans
        - .cortex/config/ - Configuration files
        - .cursor/ symlinks for IDE compatibility

        Returns:
            Prompt message guiding the assistant to setup project structure
        """
        return _SETUP_PROJECT_STRUCTURE_PROMPT


# Conditionally register setup_cursor_integration only if Cursor integration not configured
if not _config_status["cursor_integration_configured"]:

    @mcp.prompt()
    def setup_cursor_integration() -> str:
        """Setup Cursor IDE integration with symlinks and MCP server configuration.

        Creates symlinks in .cursor/ pointing to .cortex/ subdirectories:
        - .cursor/memory-bank -> ../.cortex/memory-bank
        - .cursor/synapse -> ../.cortex/synapse
        - .cursor/plans -> ../.cortex/plans

        Also creates MCP server configuration at .cursor/mcp.json

        Returns:
            Prompt message guiding the assistant to setup Cursor integration
        """
        return _SETUP_CURSOR_INTEGRATION_PROMPT


_SETUP_SYNAPSE_PROMPT_TEMPLATE = """Please setup Synapse in my project.

I want to use Synapse from: {synapse_repo_url}

Synapse is a shared repository that contains both rules and prompts for cross-project sharing.

I need you to:
1. Add the Synapse repository as a Git submodule
2. Clone it to .cortex/synapse/
3. Create the rules index
4. Validate the structure (should have rules/ and prompts/ subdirectories)
5. Load the rules and prompts manifests

Commands to run:
git submodule add {synapse_repo_url} .cortex/synapse/
git submodule update --init --recursive

Expected structure:
.cortex/synapse/
├── LICENSE
├── rules/
│   ├── rules-manifest.json
│   ├── general/
│   ├── python/
│   └── ...
└── prompts/
    ├── prompts-manifest.json
    ├── general/
    ├── python/
    └── ...

Expected output format:
{{
  "status": "success",
  "message": "Synapse setup successfully",
  "synapse_path": ".cortex/synapse/",
  "rules_count": <count>,
  "prompts_count": <count>,
  "submodule_url": "{synapse_repo_url}",
  "commit": "<commit_hash>"
}}"""


@mcp.prompt()
def setup_synapse(synapse_repo_url: str) -> str:
    """Setup Synapse via Git submodule.

    Adds a Synapse repository as a Git submodule to enable
    cross-project sharing of rules and prompts at .cortex/synapse/.

    Args:
        synapse_repo_url: URL of the Synapse repository

    Returns:
        Prompt message guiding the assistant to setup Synapse
    """
    return _SETUP_SYNAPSE_PROMPT_TEMPLATE.format(synapse_repo_url=synapse_repo_url)


_CHECK_MIGRATION_STATUS_PROMPT = """Please check if my project needs migration to the .cortex/ structure.

I need you to:
1. Detect the current project structure
2. Check if it's using an old directory structure (e.g., .cursor/memory-bank/, memory-bank/, .memory-bank/)
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
{"status": "up_to_date", "message": "Project is already using the .cortex/ structure", "current_location": ".cortex/memory-bank/", "files_count": 7}

Expected output format (migration needed):
{"status": "migration_needed", "message": "Legacy format detected", "old_location": "<detected_location>", "new_location": ".cortex/memory-bank/", "files_to_migrate": 7}

Expected output format (not initialized):
{"status": "not_initialized", "message": "No Memory Bank found", "suggestion": "Run initialize_memory_bank to create one"}"""


# Conditionally register migration prompts only if migration needed
if _config_status["migration_needed"]:

    @mcp.prompt()
    def check_migration_status() -> str:
        """Check if project needs migration to the .cortex/ structure.

        Detects legacy formats and checks if migration to .cortex/ is needed.
        Legacy formats include .cursor/memory-bank/, memory-bank/, .memory-bank/.

        Returns:
            Prompt message guiding the assistant to check migration status
        """
        return _CHECK_MIGRATION_STATUS_PROMPT


_MIGRATE_MEMORY_BANK_PROMPT = """Please migrate my Memory Bank to the .cortex/ structure.

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


# Conditionally register migrate_memory_bank only if migration needed
if _config_status["migration_needed"]:

    @mcp.prompt()
    def migrate_memory_bank() -> str:
        """Migrate Memory Bank to the .cortex/ structure.

        Moves files from legacy locations to .cortex/memory-bank/ while
        preserving all content and version history. Creates .cursor/ symlinks
        for IDE compatibility.

        Returns:
            Prompt message guiding the assistant to migrate Memory Bank
        """
        return _MIGRATE_MEMORY_BANK_PROMPT


_MIGRATE_PROJECT_STRUCTURE_PROMPT = """Please migrate my project to the .cortex/ structure.

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


# Conditionally register migrate_project_structure only if migration needed
if _config_status["migration_needed"]:

    @mcp.prompt()
    def migrate_project_structure() -> str:
        """Migrate project to the .cortex/ structure.

        Moves files from legacy locations to .cortex/:
        - memory-bank -> .cortex/memory-bank/
        - synapse -> .cortex/synapse/
        - plans -> .cortex/plans/

        Creates .cursor/ symlinks for IDE compatibility.

        Returns:
            Prompt message guiding the assistant to migrate project structure
        """
        return _MIGRATE_PROJECT_STRUCTURE_PROMPT
