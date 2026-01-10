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

## Memory Bank Structure

The Memory Bank consists of core files in Markdown format, stored in a portable location that works with any editor, LLM, or agent.

### Storage Location

Cortex supports two storage formats, both portable and editor-agnostic:

**Simple format** (legacy): `memory-bank/` - Files stored directly in this directory

- Used by core file operations
- Simple flat structure
- Fully portable across all editors and tools

**Structured format** (recommended): `.memory-bank/` - Organized into subdirectories

- `.memory-bank/knowledge/` - Core memory bank files
- `.memory-bank/rules/` - Project rules and configuration
- `.memory-bank/plans/` - Development plans and roadmaps
- Better organization for larger projects
- Configurable via structure configuration

Both formats work with any MCP-compatible client (Cursor, VS Code, CLI tools, etc.).

### Optional Cursor Integration

If you're using Cursor IDE with the structured format, the system can optionally create symlinks in `.cursor/` for seamless integration:

- `.cursor/knowledge/` → `.memory-bank/knowledge/` (symlink)
- `.cursor/rules/` → `.memory-bank/rules/` (symlink)
- `.cursor/plans/` → `.memory-bank/plans/` (symlink)
- `.cursorrules` → `.memory-bank/rules/local/main.cursorrules` (symlink)

This allows Cursor to access the Memory Bank while keeping the actual files in a portable location. The symlinks are optional and can be disabled in the structure configuration.

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
