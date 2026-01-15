# Memory Bank Prompt Templates

This directory contains prompt templates for one-time Memory Bank operations. These operations don't need dedicated MCP tools since they're typically performed once per project during setup.

## Available Prompts

### Setup & Initialization

1. **[Initialize Memory Bank](initialize-memory-bank.md)** - Create new Memory Bank with all core files
2. **[Setup Project Structure](setup-project-structure.md)** - Create standardized .cursor/ directory structure
3. **[Setup Cursor Integration](setup-cursor-integration.md)** - Configure Cursor IDE integration
4. **[Setup Shared Rules](setup-shared-rules.md)** - Add shared rules via Git submodule

### Migration

1. **[Check Migration Status](check-migration-status.md)** - Check if migration is needed
2. **[Migrate Memory Bank](migrate-memory-bank.md)** - Migrate old format to current
3. **[Migrate Project Structure](migrate-project-structure.md)** - Migrate to standardized structure

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
1. Read: docs/prompts/initialize-memory-bank.md
2. Send: "Please initialize a Memory Bank in my project at /path/to/project"
3. Verify: Check that memory-bank/ directory exists with 7 files
4. Customize: Fill in project-specific details in each file
```

### Migrating an Existing Project

```markdown
1. Read: docs/prompts/check-migration-status.md
2. Send: "Please check if my Memory Bank at /path/to/project needs migration"
3. If needed:
   a. Read: docs/prompts/migrate-memory-bank.md
   b. Send: "Please migrate my Memory Bank at /path/to/project"
4. Verify: Check migration output and validate structure
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

## Tool Count Impact

By converting 7 one-time operations to prompts, we reduce:

- **Total MCP tools**: 52 → 45 (13% reduction)
- **IDE tool budget**: More room for other MCP servers
- **User cognitive load**: Fewer tools to learn

This is part of Phase 7.10 consolidation effort to reduce from 52 → 25 tools (52% reduction).

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
