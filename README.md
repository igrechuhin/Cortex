# Cortex - AI Memory & Context Management Server

Cortex is an MCP server that helps build structured documentation systems based on [Cline's Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank) for context preservation in AI assistant environments.

Powered by [Enlighter](https://enlightby.ai) and [Hyperskill](https://hyperskill.org).

Learn how to setup and use Memory Bank directly in Cursor: <http://enlightby.ai/projects/37>

[![smithery badge](https://smithery.ai/badge/@igrechuhin/cortex)](https://smithery.ai/server/@igrechuhin/cortex)

[![Cortex MCP server](https://glama.ai/mcp/servers/@igrechuhin/cortex/badge)](https://glama.ai/mcp/servers/@igrechuhin/cortex)

## Features

- **Memory Bank Management** - Create, validate, and maintain structured memory bank files
- **DRY Linking** - Transclusion engine for including content across files without duplication
- **Validation & Quality** - Schema validation, duplication detection, and quality metrics
- **Token Optimization** - Context optimization within token budgets, progressive loading, and summarization
- **Refactoring Support** - Pattern analysis, refactoring suggestions, safe execution, and rollback
- **Shared Rules** - Cross-project rule sharing and management
- **Project Structure** - Standardized project structure management with templates

## Running the Server

There are a few options to use this MCP server:

### With UVX

Add this to your mcp.json config file:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/igrechuhin/Cortex.git",
        "cortex"
      ]
    }
  }
}
```

### With [Smithery](https://smithery.ai/server/@igrechuhin/cortex)

Add this to your mcp.json config file:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@igrechuhin/cortex",
        "--key",
        "your_smithery_key"
      ]
    }
  }
}
```

### With Docker

Add this to your mcp.json config file:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "19283744/cortex:latest"
      ]
    }
  }
}
```

### Manually

Clone repository and run the following commands:

```bash
uv sync --dev
```

Then add this to your mcp.json config file:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uv",
      "args": ["run", "cortex"]
    }
  }
}
```

## Usage Example

Ask Cursor or any other AI code assistant with Cortex MCP:

```text
Initialize memory bank for my project and analyze its structure
```

Provide more context to get better results.

## Available Tools

### Foundation Tools

- **manage_file** - Read, write, and manage memory bank files
- **get_dependency_graph** - View file dependencies
- **get_version_history** - Track file version history
- **rollback_file_version** - Rollback to previous versions
- **get_memory_bank_stats** - Get memory bank statistics

### Linking Tools

- **parse_file_links** - Parse links in memory bank files
- **resolve_transclusions** - Resolve `{{include:path}}` references
- **validate_links** - Validate link integrity
- **get_link_graph** - Get transclusion dependency tree

### Validation & Analysis Tools

- **validate** - Run schema validation and duplication detection
- **analyze** - Analyze patterns and structure
- **suggest_refactoring** - Get refactoring suggestions
- **check_structure_health** - Validate project structure

### Optimization Tools

- **optimize_context** - Optimize context within token budget
- **load_progressive_context** - Load context incrementally
- **summarize_content** - Summarize content
- **get_relevance_scores** - Score files by relevance

### Refactoring Tools

- **apply_refactoring** - Execute refactoring safely
- **provide_feedback** - Submit feedback for learning

### Rules & Configuration Tools

- **rules** - Manage cursor rules
- **sync_shared_rules** - Sync shared rules repositories
- **update_shared_rule** - Update shared rules
- **get_rules_with_context** - Get context-aware rules
- **configure** - Configure server settings
- **get_structure_info** - Get project structure information

## Available Prompts

Cortex provides MCP prompts for one-time setup and migration operations. Use prompts when you need guided assistance for initial configuration or structural changes.

### Which Prompt Should I Use?

| Your Situation | Prompt to Use |
|----------------|---------------|
| Starting a new project, no Memory Bank exists | `initialize_memory_bank` |
| Want full project structure with rules and plans | `setup_project_structure` |
| Setting up Cursor IDE with MCP configuration | `setup_cursor_integration` |
| Want to share rules across multiple projects | `setup_shared_rules` |
| Not sure if your Memory Bank needs updating | `check_migration_status` |
| Have old `.cursor/memory-bank/` format | `migrate_memory_bank` |
| Have files scattered in old locations | `migrate_project_structure` |

### Setup Prompts

Use these when starting fresh or configuring a new project:

- **initialize_memory_bank** - Create a new Memory Bank with all 7 core files (projectBrief.md, productContext.md, activeContext.md, systemPatterns.md, techContext.md, progress.md, roadmap.md). Use this for new projects or projects without any Memory Bank.

- **setup_project_structure** - Create the full standardized `.cortex/` directory structure including memory-bank/, rules/, plans/, and config/. Creates `.cursor/` symlinks for IDE compatibility.

- **setup_cursor_integration** - Configure Cursor IDE to work with Cortex MCP server. Creates symlinks in `.cursor/` pointing to `.cortex/` subdirectories and `.cursor/mcp.json` for MCP configuration.

- **setup_shared_rules** - Add a shared rules repository (Synapse) as a Git submodule to `.cortex/synapse/`. Use this when you want to share coding standards, security rules, prompts, or other guidelines across multiple projects.

### Migration Prompts

Use these when updating an existing project to a newer format:

- **check_migration_status** - Check if your project needs migration to the `.cortex/` structure. Use this first if you're unsure whether your project uses an old format. Returns one of: `up_to_date`, `migration_needed`, or `not_initialized`.

- **migrate_memory_bank** - Move files from old locations (`.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/`) to the new `.cortex/memory-bank/` location. Preserves all content and version history, creates `.cursor/` symlinks for IDE compatibility. Use this when `check_migration_status` reports `migration_needed`.

- **migrate_project_structure** - Reorganize scattered files into the standardized `.cortex/` structure. Moves memory-bank/, rules/, and plan directories to their proper `.cortex/` locations and creates `.cursor/` symlinks. Use this for projects with files in non-standard locations.

### Prompts vs Tools

**Use Prompts for:**

- One-time setup operations (initialization, configuration)
- Migration from old formats
- Guided multi-step processes

**Use Tools for:**

- Regular file operations (read, write, validate)
- Analysis and optimization
- Ongoing maintenance tasks

## Memory Bank Structure

The Memory Bank consists of core files in Markdown format, stored in a portable location that works with any editor, LLM, or agent.

### Storage Location

Cortex stores all data in `.cortex/` directory:

**Primary format**: `.cortex/` - All Cortex-managed files organized into subdirectories

- `.cortex/memory-bank/` - Core memory bank files
- `.cortex/synapse/` - Synapse repository (shared rules, prompts, and configuration)
- `.cortex/plans/` - Development plans and roadmaps
- `.cortex/config/` - Configuration files
- `.cortex/history/` - Version history
- `.cortex/index.json` - Metadata index

**IDE Integration**: `.cursor/` - Contains symlinks for IDE compatibility

- `.cursor/memory-bank/` → `../.cortex/memory-bank/` (symlink)
- `.cursor/synapse/` → `../.cortex/synapse/` (symlink)
- `.cursor/plans/` → `../.cortex/plans/` (symlink)

This structure keeps the actual files in a portable location while allowing IDEs like Cursor to access them through familiar paths.

### Legacy Formats (Migrated Automatically)

If your project uses an old format, use the migration prompts to update:

- `memory-bank/` (root-level) → `.cortex/memory-bank/`
- `.cursor/memory-bank/` (Cursor-centric) → `.cortex/memory-bank/`
- `.memory-bank/knowledge/` (old standardized) → `.cortex/memory-bank/`

### Core Files (Required)

1. `projectBrief.md` - Foundation document that shapes all other files
2. `productContext.md` - Explains why the project exists, problems being solved
3. `activeContext.md` - Current work focus, recent changes, next steps
4. `systemPatterns.md` - System architecture, technical decisions, design patterns
5. `techContext.md` - Technologies used, development setup, constraints
6. `progress.md` - What works, what's left to build
7. `roadmap.md` - Development roadmap and milestones

### DRY Linking

Use transclusion to include content from other files without duplication:

```markdown
{{include:path/to/file.md}}
```
