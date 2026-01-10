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
"""

from cortex.server import mcp


@mcp.prompt()
def initialize_memory_bank(project_root: str) -> str:
    """Initialize a new Memory Bank with all core files.

    Creates the memory-bank/ directory structure with 7 core files:
    - projectBrief.md - Foundation document
    - productContext.md - Product context and requirements
    - activeContext.md - Current active development context
    - systemPatterns.md - System architecture patterns
    - techContext.md - Technical context and decisions
    - progress.md - Development progress tracking
    - roadmap.md - Development roadmap and milestones

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to initialize Memory Bank
    """
    return f"""Please initialize a Memory Bank in my project at {project_root}.

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

Expected output format:
{{
  "status": "success",
  "message": "Memory Bank initialized successfully",
  "project_root": "{project_root}",
  "files_created": 7,
  "total_tokens": <token_count>
}}"""


@mcp.prompt()
def setup_project_structure(project_root: str) -> str:
    """Setup the standardized .cursor/ project structure.

    Creates:
    - .cursor/memory-bank/ - Core memory bank files
    - .cursor/rules/ - Project-specific rules
    - .cursor/plans/ - Development plans
    - .cursor/plans/archive/ - Archived plans
    - .cursor/integrations/ - IDE integration configs

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to setup project structure
    """
    return f"""Please setup the standardized project structure in my project at {project_root}.

I need you to:
1. Create the .cursor/ directory structure
2. Setup memory-bank/ with core files
3. Create rules/ directory for project rules
4. Setup plans/ directory for development plans
5. Generate all necessary template files
6. Initialize directory indexes

Expected directory structure:
.cursor/
├── memory-bank/     # Core memory bank files
├── rules/           # Project-specific rules
├── plans/           # Development plans
│   └── archive/     # Archived plans
└── integrations/    # IDE integration configs

Expected output format:
{{
  "status": "success",
  "message": "Project structure setup successfully",
  "directories_created": [...],
  "files_created": [...],
  "total_files": <count>
}}"""


@mcp.prompt()
def setup_cursor_integration(project_root: str) -> str:
    """Setup Cursor IDE integration with MCP server configuration.

    Creates configuration files for Cursor IDE:
    - .cursor/config.json - IDE settings
    - .cursor/mcp.json - MCP server config

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to setup Cursor integration
    """
    return f"""Please setup Cursor IDE integration in my project at {project_root}.

I need you to:
1. Create .cursor/ configuration directory
2. Generate Cursor-specific config files
3. Setup MCP server configuration
4. Configure memory bank integration
5. Setup rules and context loading
6. Test the integration

Configuration files to create:
- .cursor/config.json - IDE settings
- .cursor/mcp.json - MCP server config with Cortex server

MCP configuration should include:
{{
  "mcpServers": {{
    "cortex": {{
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
    }}
  }}
}}

Expected output format:
{{
  "status": "success",
  "message": "Cursor integration setup successfully",
  "config_files": [".cursor/config.json", ".cursor/mcp.json"],
  "mcp_server": {{
    "name": "cortex",
    "status": "configured"
  }}
}}"""


@mcp.prompt()
def setup_shared_rules(project_root: str, shared_rules_repo_url: str) -> str:
    """Setup shared rules via Git submodule.

    Adds a shared rules repository as a Git submodule to enable
    cross-project rule sharing.

    Args:
        project_root: Path to the project root directory
        shared_rules_repo_url: URL of the shared rules repository

    Returns:
        Prompt message guiding the assistant to setup shared rules
    """
    return f"""Please setup shared rules in my project at {project_root}.

I want to use shared rules from: {shared_rules_repo_url}

I need you to:
1. Add the shared rules repository as a Git submodule
2. Clone it to .cursor/rules/shared/
3. Create the rules index
4. Validate the rules structure
5. Merge shared rules with my local rules

Commands to run:
git submodule add {shared_rules_repo_url} .cursor/rules/shared/
git submodule update --init --recursive

Expected output format:
{{
  "status": "success",
  "message": "Shared rules setup successfully",
  "shared_rules_path": ".cursor/rules/shared/",
  "rules_count": <count>,
  "submodule_url": "{shared_rules_repo_url}",
  "commit": "<commit_hash>"
}}"""


@mcp.prompt()
def check_migration_status(project_root: str) -> str:
    """Check if Memory Bank needs migration to the latest format.

    Detects old format at .cursor/memory-bank/ and checks if migration
    to memory-bank/ is needed.

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to check migration status
    """
    return f"""Please check if my Memory Bank at {project_root} needs migration.

I need you to:
1. Detect the current Memory Bank format
2. Check if it's using an old directory structure
3. Identify what changes would be needed
4. Report the migration status

Check for:
- Old format at .cursor/memory-bank/
- New format at memory-bank/
- File structure and metadata validity

Expected output format (up to date):
{{
  "status": "up_to_date",
  "message": "Memory Bank is already using the latest format",
  "current_location": "memory-bank/",
  "files_count": 7
}}

Expected output format (migration needed):
{{
  "status": "migration_needed",
  "message": "Old format detected at .cursor/memory-bank/",
  "old_location": ".cursor/memory-bank/",
  "new_location": "memory-bank/",
  "files_to_migrate": 7
}}

Expected output format (not initialized):
{{
  "status": "not_initialized",
  "message": "No Memory Bank found",
  "suggestion": "Run initialize_memory_bank to create one"
}}"""


@mcp.prompt()
def migrate_memory_bank(project_root: str) -> str:
    """Migrate Memory Bank to the latest format.

    Moves files from .cursor/memory-bank/ to memory-bank/ while
    preserving all content and version history.

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to migrate Memory Bank
    """
    return f"""Please migrate my Memory Bank at {project_root} to the latest format.

I need you to:
1. Create the new memory-bank/ directory
2. Copy all files from .cursor/memory-bank/ to memory-bank/
3. Preserve all content and version history
4. Update the metadata index
5. Create snapshots in the new location
6. Validate the migration succeeded

Safety requirements:
- Automatic rollback if migration fails
- Content validation after migration
- Version history preservation
- Atomic operation (succeeds completely or fails completely)

Expected output format:
{{
  "status": "success",
  "message": "Memory Bank migrated successfully",
  "old_location": ".cursor/memory-bank/",
  "new_location": "memory-bank/",
  "files_migrated": 7,
  "versions_migrated": <count>,
  "duration_ms": <time>
}}"""


@mcp.prompt()
def migrate_project_structure(project_root: str) -> str:
    """Migrate project to the standardized structure.

    Moves files to standardized locations:
    - memory-bank/ -> .cursor/memory-bank/
    - rules/ -> .cursor/rules/
    - .plan/ -> .cursor/plans/

    Args:
        project_root: Path to the project root directory

    Returns:
        Prompt message guiding the assistant to migrate project structure
    """
    return f"""Please migrate my project structure at {project_root} to the standardized format.

I need you to:
1. Detect the current structure
2. Create the new .cursor/ directory structure
3. Move existing files to correct locations
4. Preserve all content and history
5. Update references and links
6. Validate the migration

Migration mappings:
- memory-bank/ -> .cursor/memory-bank/
- rules/ -> .cursor/rules/
- .plan/ -> .cursor/plans/
- docs/plans/ -> .cursor/plans/

Safety requirements:
- Dry-run mode available
- Automatic rollback on error
- Content validation after migration
- Link updating for broken references
- Backup creation before migration

Expected output format:
{{
  "status": "success",
  "message": "Project structure migrated successfully",
  "migrations": {{
    "memory_bank": {{"from": "memory-bank/", "to": ".cursor/memory-bank/", "files": 7}},
    "rules": {{"from": "rules/", "to": ".cursor/rules/", "files": <count>}},
    "plans": {{"from": ".plan/", "to": ".cursor/plans/", "files": <count>}}
  }},
  "links_updated": <count>,
  "duration_ms": <time>
}}"""
