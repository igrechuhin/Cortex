# Getting Started with Cortex

This guide will help you install and start using Cortex.

## Installation

### Prerequisites

- Python 3.13 or later
- `uv` package manager (recommended) or `pip`
- Node.js and npm (for markdownlint-cli2, required by `fix_markdown_lint` MCP tool and commit pipeline; optional if you use the repo’s local install—see below)

### Install via uv (Recommended)

```bash
# Optional: install markdownlint-cli2 for fix_markdown_lint and commit pipeline.
# Option A (recommended): from a clone, run in repo root: npm install
# Option B: global install: npm install -g markdownlint-cli2

# Run from git repository
uvx --from git+https://github.com/igrechuhin/cortex.git cortex
```

### Install via pip

```bash
# Clone the repository
git clone https://github.com/igrechuhin/cortex.git
cd cortex

# Install markdownlint-cli2: run npm install (uses package.json), or npm install -g markdownlint-cli2
npm install

# Install dependencies
pip install -r requirements.txt

# Run the server
python -m cortex.main
```

### Install as Development Environment

```bash
# Clone the repository
git clone https://github.com/igrechuhin/cortex.git
cd cortex

# Install markdownlint-cli2: run npm install (uses package.json), or npm install -g markdownlint-cli2
npm install

# Install with development dependencies
uv sync --dev

# Run the server
uv run cortex
```

### Pre-commit hooks (recommended for development)

The project uses [pre-commit](https://pre-commit.com) for git hooks. When you **initialize** a project with Cortex (Initialize prompt), the setup can create a `.pre-commit-config.yaml` with a markdown lint hook and run `pre-commit install` for you. For this repo (or if you clone without running Initialize), after cloning and installing dependencies:

```bash
# Install pre-commit (if not already installed)
pip install pre-commit
# or: uv add --dev pre-commit

# Install the git hooks (run once per clone)
pre-commit install
```

When you run `git commit`, pre-commit will:

- Run **markdown lint** on staged `.md` and `.mdc` files (`markdownlint-cli2 --fix`). Fixable issues are auto-fixed and re-staged; the commit is blocked if unfixable errors remain.
- Run other configured checks (formatting, file sizes, function lengths, type check, etc.).

To run all hooks manually without committing: `pre-commit run --all-files`.

## Configuration

### MCP Client Configuration

To use Cortex with Claude Desktop or other MCP clients, add it to your MCP configuration:

**For Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "memory-bank": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
    }
  }
}
```

**For Cursor IDE** (`.cursor/mcp_config.json`):

```json
{
  "mcpServers": {
    "memory-bank": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"],
      "transport": "stdio"
    }
  }
}
```

## Quick Start

### 1. Initialize a Memory Bank

Use the `initialize_memory_bank` tool to create a new Memory Bank:

```json
{
  "project_root": "/path/to/your/project"
}
```

This creates:

- `.memory-bank/` directory with core files
- `.memory-bank-index` for metadata
- Initial memory bank structure

### 2. Set Up Project Structure (Optional)

For a standardized structure with Cursor IDE integration:

```json
{
  "project_root": "/path/to/your/project",
  "project_name": "My Project",
  "project_type": "software",
  "interactive": true
}
```

This creates:

- `.memory-bank/knowledge/` - Memory Bank files
- `.memory-bank/rules/local/` - Project-specific rules
- `.memory-bank/plans/` - Planning system
- `.cursor/` - Cursor IDE symlinks

### 3. Write Your First Memory Bank File

Create `projectBrief.md`:

```markdown
# Project Brief

## Project Overview

Brief description of your project.

## Goals

- Goal 1
- Goal 2
- Goal 3

## Scope

What's in scope and out of scope.
```

### 4. Validate Your Memory Bank

Use the `validate_memory_bank` tool:

```json
{
  "project_root": "/path/to/your/project"
}
```

This checks:

- Required sections are present
- No duplicate content
- Links are valid
- Quality score

### 5. Load Context

Use the `load_context` tool to load relevant files for a task:

```json
{
  "project_root": "/path/to/your/project",
  "task_description": "Implement user authentication",
  "token_budget": 100000
}
```

This returns:

- Selected files ranked by relevance
- Token usage information
- Optimization metadata

## Common Workflows

### Adding New Content

1. Write new markdown file in `.memory-bank/knowledge/`
2. Use transclusion to include shared content: `{{include:shared.md#section}}`
3. Validate with `validate_memory_bank`
4. Check quality with `get_quality_score`

### Using DRY Linking

Instead of duplicating content:

```markdown
# Before (Duplication)
## Authentication
Users authenticate via OAuth 2.0 using Google...

## API Security
Users authenticate via OAuth 2.0 using Google...
```

Use transclusion:

```markdown
# shared.md
## Authentication
Users authenticate via OAuth 2.0 using Google...

# systemPatterns.md
{{include:shared.md#Authentication}}

# techContext.md
{{include:shared.md#Authentication}}
```

### Migrating from Legacy Structure

If you have existing Memory Bank files:

```json
{
  "project_root": "/path/to/your/project",
  "backup": true
}
```

This automatically:

- Detects legacy structure type
- Creates backup
- Migrates files to standardized structure
- Updates links

### Setting Up Shared Rules

To share rules across projects:

```json
{
  "project_root": "/path/to/your/project",
  "repo_url": "https://github.com/your-org/shared-rules.git",
  "branch": "main"
}
```

This sets up:

- Git submodule at `.cortex/synapse/`
- Automatic rule synchronization
- Context-aware rule loading

## Next Steps

- **[Configuration Guide](./guides/configuration.md)** - Learn about all configuration options
- **[API Reference](./api/tools.md)** - Explore all 52 MCP tools
- **[Architecture](./architecture.md)** - Understand the system design
- **[Troubleshooting](./guides/troubleshooting.md)** - Common issues and solutions

## Tips

1. **Start Small**: Begin with just `projectBrief.md` and `activeContext.md`
2. **Use Templates**: Use `setup_project_structure` for guided setup
3. **Validate Often**: Run `validate_memory_bank` after changes
4. **Monitor Quality**: Track quality scores with `get_quality_score`
5. **Use Transclusion**: Avoid duplication with `{{include:}}` syntax
6. **Leverage Context Loading**: Use `load_context` for large projects

## Common Commands

```bash
# Run server locally
uv run cortex

# Run tests
pytest

# Format code (for contributors)
black .
isort .

# Check test coverage
pytest --cov=src/cortex
```

## Support

If you encounter issues:

1. Check [Troubleshooting Guide](./guides/troubleshooting.md)
2. Search [GitHub Issues](https://github.com/igrechuhin/cortex/issues)
3. Create a new issue with detailed information
