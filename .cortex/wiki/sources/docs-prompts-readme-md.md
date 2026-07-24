# Memory Bank Prompt Templates

This directory contains prompt templates for one-time Memory Bank operations. These operations don't need dedicated MCP tools since they're typically performed once per project during setup.

## When Prompts Appear

Prompts are **conditionally registered** based on project configuration:

- **initialize** appears only when project is not initialized and not configured (no memory bank, missing structure).
- **migrate** appears only when a legacy format is detected and migration is needed.
- **setup_synapse** is always available (optional feature).

If your project is fully configured, only active-development prompts (e.g. from Synapse) and `setup_synapse` will be listed.

## Prompt Icons

Cortex registers each prompt with an **emoji icon** (per MCP spec): setup prompts use icons like 🏗️ 🔄 💾 🔗, and Synapse prompts (commit, review, do, plan) use 💾 👀 ⚡ 📋. The server sends these in the `prompts/list` response (each prompt has an `icons` array with a data-URI SVG).

**Visibility in the UI** depends on your MCP client. Some clients may show only prompt names and descriptions and **not render prompt icons** yet. To confirm the server is sending icons, you can use an MCP inspector or call the prompts list endpoint; the response will include `icons` for each prompt.

## Available Prompts

### Setup & Initialization

1. **[initialize](initialize.md)** - Complete project initialization (structure + memory bank + MCP server configuration + optional Synapse)
2. **[setup_synapse](setup-synapse.md)** - Add shared rules repository via Git submodule (always available)

### Migration

1. **[migrate](migrate.md)** - Migrate legacy structure to new `.cortex/` structure (detects, initializes, migrates, validates, cleans up)

## Quality and pre-commit in prompts

When authoring or reviewing Synapse prompts (for example under `.cortex/synapse/prompts/`), prefer zero-arg **`autofix()`** and **`run_quality_gate()`** — some MCP client bridges may strip JSON tool parameters. Do not treat the legacy parameterized trio (names in the block below) as the primary path:

```text
execute_pre_commit_checks
start_quality_job
get_quality_job_status
```

See [Commit and quality pipeline (zero-arg MCP tools)](../api/tools.md#commit-and-quality-pipeline-zero-arg-mcp-tools).

## When to Use Prompts vs. MCP Tools

### Use Prompts For

- ✅ One-time setup operations
- ✅ Initial project configuration
- ✅ Migration from old formats
- ✅ Rare administrative tasks

### Use MCP Tools For

- ✅ Regular file operations (read, write, metadata)
- ✅ Content validation and quality checks
- ✅ Context optimization and loading
- ✅ Refactoring and analysis
- ✅ Version control and rollback

## How to Use These Prompts

1. **Open the prompt template** - Read the full template to understand what will happen
2. **Prepare prerequisites** - Ensure all required dependencies are met
3. **Customize the prompt** - Replace `[PROJECT_ROOT]` and other placeholders with your values
4. **Send to AI assistant** - Copy the prompt section and send it to your AI assistant
5. **Review the output** - Verify the operation completed successfully
6. **Follow post-setup steps** - Complete any additional configuration

## Example Usage

### Initializing a New Project

```markdown
1. Read: docs/prompts/initialize.md
2. Send: "Please initialize a Memory Bank in my project at /path/to/project"
3. Verify: Check that memory-bank/ directory exists with 7 files
4. Customize: Fill in project-specific details in each file
```

### Migrating an Existing Project

```markdown
1. Read: docs/prompts/migrate.md
2. Send: "Please migrate my Memory Bank at /path/to/project" (migrate detects and runs migration)
3. Verify: Check migration output and validate structure
```

## Benefits of Prompt-Based Approach

### For Users

- **Simpler API** - No need to discover rarely-used tools
- **Clear guidance** - Step-by-step instructions with context
- **Flexibility** - Easy to customize for specific needs
- **Better IDE experience** - More room for frequently-used tools

### For Development

- **Less maintenance** - Fewer tools to test and update
- **Better documentation** - Rich context in markdown format
- **Easier updates** - Change prompts without code changes
- **Clear purpose** - Prompts are self-documenting

## Simplified Prompt Structure

The setup prompt system has been simplified from 7 prompts to 3 unified prompts:

- **Before**: `initialize_memory_bank`, `setup_project_structure`, `setup_cursor_integration`, `check_migration_status`, `migrate_memory_bank`, `migrate_project_structure`, `setup_synapse`
- **After**: `initialize`, `migrate`, `setup_synapse`

This simplification:

- Reduces cognitive load (fewer prompts to understand)
- Better matches user workflows (initialize new project vs. migrate existing)
- Provides default synapse_repo_url for easier setup
- Maintains all functionality while improving usability

Legacy prompts (the 7 originals) are archived in [archive/](archive/) for reference.

## Contributing

To add new prompt templates:

1. Create a new `.md` file in this directory
2. Follow the template structure (see existing prompts)
3. Include: Prerequisites, Prompt, What Happens, Expected Output, Next Steps
4. Update this README with the new prompt
5. Test the prompt with actual use cases

## Support

For issues or questions:

- Check the [main documentation](../../README.md)
- Report issues at [GitHub Issues](https://github.com/igrechuhin/cortex/issues)
- Review [CLAUDE.md](../../CLAUDE.md) for development guidelines
