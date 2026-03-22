# Getting Started with Cortex

This guide will help you install and start using Cortex.

## Installation

### Prerequisites

- Python 3.13 or later
- `uv` package manager (recommended) or `pip`
- `rumdl` Markdown linter/formatter installed into the Python environment (typically via `uv sync --extra dev`, which adds the `rumdl` CLI to `.venv/bin/rumdl`)

### Install via uv (Recommended)

```bash
# Run from git repository (installs Python deps including rumdl when needed)
uvx --from git+https://github.com/igrechuhin/cortex.git cortex
```

### Install via pip

```bash
# Clone the repository
git clone https://github.com/igrechuhin/cortex.git
cd cortex

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

# Install with development dependencies (Python 3.13.x), including rumdl
bash scripts/bootstrap.sh

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

- Run **markdown lint** on all `.md` and `.mdc` files using `rumdl` (`uv run rumdl check --fix .`). Fixable issues are auto-fixed and re-staged; the commit is blocked if unfixable errors remain.
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

**Stable MCP by default** — Cortex **exits** when the connection drops (e.g. client disconnect). The client (e.g. Cursor) starts a new process when it next needs MCP, so the next session gets a **fresh Initialize handshake with no user action** (no reload needed). Run `uvx cortex` (or `uv run cortex`) as usual. Optional: set `CORTEX_AUTO_RESTART=1` to respawn the server in-process under the same pipe (then you may need to reload MCP after a disconnect to restore tools).

The same Cursor config as above (command `uvx`, args `["--from", "git+...", "cortex"]`) is enough.

### Stable MCP setup (recommended)

For the most stable MCP experience:

1. **Default: exit on disconnect** — The process exits when the connection drops. The client starts a new process when it next needs MCP, so you get a fresh session and no "0 tools" state without reloading. No user action required.
2. **Optional: use the bridge** for concurrent request handling (fewer timeouts when the client does many things at once). In Cursor, set the MCP server command to the bridge instead of Cortex directly:
   - **Command**: `uv run python -m cortex.bridge` (from a clone; requires `uv sync --extra server`).
   - The bridge runs Cortex over HTTP and proxies stdio ↔ HTTP; one switch in Cursor, same tools.
3. **Faster markdown lint** (reduces chance of client timeout during long tools): from project root run `make bootstrap` so `fix_markdown_lint` uses the local `rumdl` binary from the Python virtualenv instead of relying on external tooling.
4. **During long runs** (e.g. commit, pre-commit): avoid opening UI that triggers many MCP resource reads at once (e.g. MCP resources panel); prefer tool calls over `cortex://` resources.
5. **Automatic recovery (no manual reload)** — Install the [Cursor MCP Refresh](https://github.com/tankmurdock/cursor-mcp-refresh) extension and set **Auto-refresh interval** (e.g. 60–300 seconds). It periodically refreshes MCP servers, so after a disconnect or "0 tools" state the next refresh restores tools without you toggling. Install from the [releases `.vsix`](https://github.com/tankmurdock/cursor-mcp-refresh/releases) via **Extensions: Install from VSIX**.
6. **If you see "0 tools"** and don't use the extension: reload MCP manually or see [Troubleshooting: Found 0 tools](guides/troubleshooting.md#issue-mcp-0-tools).

Details and troubleshooting: [MCP disconnections and connection closed](guides/troubleshooting.md#issue-mcp-server-crashes-with-brokenresourceerror), [Found 0 tools](guides/troubleshooting.md#issue-mcp-0-tools).

### Offline or restricted environments

If you are behind a proxy or must work offline, pre-create the Python virtual environment (including `rumdl`) from a machine with network access:

1. From the project root, run `bash scripts/bootstrap.sh` (or `uv sync --extra dev`) on a machine with network to create `.venv` and install all dependencies, including `rumdl`.
2. Copy the `.venv` directory to the restricted machine (e.g. via USB or internal artifact store).
3. On the restricted machine, ensure the project uses that `.venv` (e.g. via `uv run cortex` or IDE interpreter selection). The quality gate and `fix_markdown_lint` use the local `rumdl` binary; no network is needed at run time.

## Quick Start

### 1. Initialize a Memory Bank

Use the **initialize** prompt to create a new Memory Bank and `.cortex/` structure. In Cursor (or any AI assistant with Cortex MCP), invoke the initialize prompt. It creates:

- `.cortex/memory-bank/` directory with core files
- `.cortex/index.json` for metadata
- All 7 core memory bank files (projectBrief.md, activeContext.md, progress.md, roadmap.md, and others)
- Cursor IDE integration (symlinks, mcp config)

Project root is resolved by the server; you do not need to pass it.

### 2. Set Up Project Structure (Optional)

The **initialize** prompt also creates the full project structure:

- `.cortex/memory-bank/` – Memory Bank files
- `.cortex/synapse/` – Shared rules (or `.cortex/rules/local/` for project-specific rules)
- `.cortex/plans/` – Planning system
- `.cortex/config/` – Configuration
- `.cursor/` – Cursor IDE symlinks

Use `get_structure_info()` to inspect paths and layout.

### 3. Write Your First Memory Bank File

Create or edit `.cortex/memory-bank/projectBrief.md`:

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

Use the `validate` tool with different check types:

```json
{
  "check_type": "schema"
}
```

This checks required sections and file structure. Other useful check types:

- `validate(check_type="schema")` – Required sections present, file structure
- `validate(check_type="duplications")` – Detect duplicate content
- `validate(check_type="quality")` – Quality score and health
- `validate(check_type="roadmap_sync")` – Roadmap and plans consistency

Project root is resolved by the server.

### 5. Load Context

Use the `load_context` tool to load relevant files for a task:

```json
{
  "task_description": "Implement user authentication",
  "token_budget": 10000
}
```

This returns:

- Selected files ranked by relevance
- Token usage information
- Optimization metadata

Project root is resolved by the server; you can omit it.

## Common Workflows

### Adding New Content

1. Write new markdown file in `.cortex/memory-bank/`
2. Use transclusion to include shared content: `{{include:shared.md#section}}`
3. Validate with `validate(check_type="schema")`
4. Check quality with `validate(check_type="quality")`

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

## systemPatterns.md

{{include:shared.md#Authentication}}

## techContext.md

{{include:shared.md#Authentication}}
```

### Migrating from Legacy Structure

If you have existing Memory Bank files in a legacy layout (under IDE `.cursor/` as `memory-bank/`, root `memory-bank/`, or `.memory-bank/`), use the **migrate** prompt. It:

- Detects legacy structure type
- Creates backup
- Migrates files to `.cortex/` structure
- Updates links and validates

### Setting Up Shared Rules

To share rules across projects, use the **setup_synapse** prompt. It sets up:

- Git submodule at `.cortex/synapse/`
- Automatic rule synchronization
- Context-aware rule loading

## Next Steps

- **[Configuration Guide](./guides/configuration.md)** - Learn about all configuration options
- **[API Reference](./api/tools.md)** - Published surface: 10 MCP tools and 6 resources
- **[Architecture](./architecture.md)** - Understand the system design
- **[Troubleshooting](./guides/troubleshooting.md)** - Common issues and solutions

## Tips

1. **Start Small**: Begin with just `projectBrief.md` and `activeContext.md`
2. **Use Templates**: Use the **initialize** prompt for guided setup
3. **Validate Often**: Run `validate(check_type="schema")` after changes
4. **Monitor Quality**: Track quality with `validate(check_type="quality")`
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
