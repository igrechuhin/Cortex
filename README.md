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

## Prerequisites

- **Python 3.13+** - Required for running the MCP server
- **Node.js and npm** - Required for `markdownlint-cli2` (used by `fix_markdown_lint` MCP tool)
  - Install markdownlint-cli2: `npm install -g markdownlint-cli2`

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
# Install Node.js dependencies (required for markdownlint-cli2)
npm install -g markdownlint-cli2

# Install Python dependencies
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

- **load_context** - Load relevant context for a task within token budget
- **load_progressive_context** - Load context incrementally
- **summarize_content** - Summarize content
- **get_relevance_scores** - Score files by relevance

### Refactoring Tools

- **apply_refactoring** - Execute refactoring safely
- **provide_feedback** - Submit feedback for learning

### Planning & Reasoning Tools

- **sequentialthinking** - Stepwise reasoning and planning (thought history, branches; compatible with MCP sequential thinking contract)

### Rules & Configuration Tools

- **rules** - Manage cursor rules (index and get relevant rules)
- **sync_synapse** - Sync Synapse repository with remote
- **update_synapse_rule** - Update a rule in Synapse repository
- **get_synapse_rules** - Get rules from Synapse repository
- **get_synapse_prompts** - Get prompts from Synapse repository
- **update_synapse_prompt** - Update a prompt in Synapse repository
- **configure** - Configure server settings
- **get_structure_info** - Get project structure information

## Available Prompts

Cortex provides MCP prompts for one-time setup and migration operations. Use prompts when you need guided assistance for initial configuration or structural changes.

**Conditional availability**: Setup and migration prompts are only shown when needed. If your project is already configured (memory bank initialized, structure in place, Cursor symlinks valid), you will not see `initialize` or `migrate` prompts. The `setup_synapse` prompt is always available as an optional feature.

**End-of-session analysis**: The single **Analyze** prompt (Synapse) runs at end of session and checks all: context effectiveness (`load_context` usage) and session optimization (mistake patterns, Synapse recommendations, report saved to `.cortex/reviews/`). Use this instead of the former separate "Analyze Context Effectiveness" and "Analyze Session Optimization" prompts.

### Which Prompt Should I Use?

| Your Situation | Prompt to Use |
|----------------|---------------|
| Starting a new project, no Memory Bank exists | `initialize` |
| Have old `.cursor/memory-bank/` or legacy format | `migrate` |
| Want to share rules across multiple projects | `setup_synapse` |
| End of session: analyze context + session optimization | `analyze` (Synapse) |

### Setup Prompts

Use these when starting fresh or configuring a new project:

- **initialize** - Complete project initialization for new projects. Creates:
  - `.cortex/` directory structure (memory-bank, plans, config)
  - Memory Bank with all 7 core files (projectBrief.md, productContext.md, activeContext.md, systemPatterns.md, techContext.md, progress.md, roadmap.md)
  - Cursor IDE integration (symlinks + mcp.json)
  - Optionally sets up Synapse with default URL (`https://github.com/igrechuhin/Synapse.git`)
  
  Only shown when project is not initialized and not configured.

- **migrate** - Migrate legacy structure to new `.cortex/` structure. Performs:
  1. Detects legacy structure (`.cursor/memory-bank/`, `memory-bank/`, `.memory-bank/`)
  2. Initializes new `.cortex/` structure (via initialize steps)
  3. Migrates all legacy files to new structure
  4. Validates migration
  5. Removes legacy directories after successful migration
  
  Only shown when migration is needed.

- **setup_synapse** - Add a shared rules repository (Synapse) as a Git submodule to `.cortex/synapse/`. Use this when you want to share coding standards, security rules, prompts, or other guidelines across multiple projects. Always available. Example: `setup_synapse()` (uses default URL) or `setup_synapse(synapse_repo_url="https://github.com/your-org/Synapse.git")`

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
  - `.cortex/synapse/scripts/{language}/` - Canonical location for quality/check scripts (e.g. `check_formatting.py`, `check_types.py`). Root `scripts/` is restricted legacy (project-specific utilities only).
- `.cortex/plans/` - Development plans and roadmaps
- `.cortex/config/` - Configuration files (e.g. `validation.json`, `optimization.json`)
- `.cortex/history/` - Version history
- `.cortex/.cache/` - Unified cache directory for all Cortex tools (use only in repo root; sibling dirs like `schema/` or `optimization/` are ignored)
  - `.cortex/.cache/summaries/` - Summary cache files
  - `.cortex/.cache/usage/` - Usage events and analytics
  - `.cortex/.cache/learning.json` - Learning data
  - `.cortex/.cache/relevance/` - Future: Relevance scoring cache
  - `.cortex/.cache/patterns/` - Future: Pattern analysis cache
  - `.cortex/.cache/refactoring/` - Future: Refactoring suggestions cache
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
