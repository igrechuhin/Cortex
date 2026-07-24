# Initialize

This prompt template guides you through complete project initialization for new projects.

## Prerequisites

- Cortex server installed and configured
- Project directory exists
- Git repository initialized (optional, for Synapse setup)

## Prompt

```text
Please initialize Cortex in my project with complete setup.
```

## What Happens

The assistant will perform complete project initialization:

### Step 1: Create .cortex/ directory structure

- Creates `.cortex/` directory
- Creates `.cortex/memory-bank/` directory
- Creates `.cortex/plans/` directory
- Creates `.cortex/config/` directory

### Step 2: Initialize Memory Bank with 7 core files

- Generates all 7 core files from templates:
  - `projectBrief.md` - Foundation document
  - `productContext.md` - Product context and requirements
  - `activeContext.md` - Current active development context
  - `systemPatterns.md` - System architecture patterns
  - `techContext.md` - Technical context and decisions
  - `progress.md` - Development progress tracking
  - `roadmap.md` - Development roadmap and milestones
- Initializes the metadata index at `.cortex/index.json`
- Creates initial snapshots in `.cortex/history/`

### Step 3: Setup MCP server configuration

- Creates `.mcp.json` in the project root with the MCP server configuration
  (for Claude Code CLI and other MCP-aware clients)

### Step 4: Optionally setup Synapse (recommended)

- Adds Synapse repository as Git submodule to `.cortex/synapse/`
- Uses default URL: `https://github.com/igrechuhin/Synapse.git`
- Or skip this step if you don't need shared rules/prompts

### Step 5: Optional pre-commit hook for markdown lint

- If the project has a Git repository (`.git` exists):
  - **No existing pre-commit config**: Creates `.pre-commit-config.yaml` with a single hook that runs markdown lint on staged `.md`/`.mdc` files (`markdownlint-cli2 --fix`). Requires `markdownlint-cli2` (e.g. `npm install -g markdownlint-cli2`) and `pre-commit` (e.g. `pip install pre-commit`).
  - **Existing pre-commit config**: Adds the same markdownlint hook to the config so commits run markdown lint on staged markdown files.
  - Runs `pre-commit install` (or instructs the user to run it once) so the git hook is active.
- If the project is not a Git repository, this step is skipped.

## Expected Output

### Successful Initialization

```json
{
  "status": "success",
  "message": "Cortex initialized successfully",
  "directories_created": [
    ".cortex",
    ".cortex/memory-bank",
    ".cortex/plans",
    ".cortex/config"
  ],
  "files_created": 7,
  "config_files": [".mcp.json"],
  "synapse_setup": true,
  "pre_commit_installed": true,
  "total_tokens": 1234
}
```

### Already Initialized

```json
{
  "status": "already_initialized",
  "message": "Project is already initialized",
  "suggestion": "Use migrate prompt if you have legacy structure"
}
```

## When This Prompt Appears

This prompt is **conditionally registered** and only appears when:

- Project is not initialized (`memory_bank_initialized = false`)
- Project structure is not configured (`structure_configured = false`)

If your project is already initialized, this prompt will not appear.

## Migration Handling

If an old format is detected during initialization (e.g., a leftover `.cursor/memory-bank/` directory from a pre-removal Cortex version, root `memory-bank/`, or `.memory-bank/`), the assistant will automatically migrate it to the current `.cortex/memory-bank/` format while preserving all content and version history.

## Next Steps

After initialization:

1. **Review generated files** - Check that all 7 core files were created
2. **Customize content** - Fill in project-specific details in each file
3. **Setup Synapse** (if skipped) - Use `setup_synapse` prompt to add shared rules
4. **Pre-commit** (if Step 5 ran) - Run `pre-commit install` if the assistant could not; markdown lint will then run on staged `.md`/`.mdc` files at commit time
5. **Start using Memory Bank** - Begin using Memory Bank tools for validation and optimization

## Related Prompts

- **migrate** - Use this if you have a legacy structure that needs migration
- **setup_synapse** - Use this to add Synapse after initialization or to override the default URL
