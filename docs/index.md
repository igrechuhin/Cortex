# Cortex Documentation

Welcome to the comprehensive documentation for Cortex - an MCP (Model Context Protocol) server that helps build structured documentation systems based on [Cline's Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank) for context preservation in AI assistant environments.

## Quick Links

- [Getting Started](./getting-started.md) - Installation and quick start guide
- [Architecture](./architecture.md) - System architecture and design
- [API Reference](./api/) - Complete API documentation
- [User Guides](./guides/) - Configuration, migration, and troubleshooting
- [Development](./development/) - Contributing and development guides

## Overview

Cortex provides a powerful set of tools for managing structured documentation (Memory Bank files) with features like:

- **Memory Bank Management**: Create, validate, and maintain structured memory bank files
- **DRY Linking**: Transclusion engine for including content across files without duplication
- **Validation & Quality**: Schema validation, duplication detection, and quality metrics
- **Token Optimization**: Context optimization within token budgets, progressive loading, and summarization
- **Refactoring Support**: Pattern analysis, refactoring suggestions, safe execution, and rollback capabilities
- **Shared Rules**: Git submodule integration for cross-project rule sharing
- **Project Structure**: Standardized project structure management with templates

## Key Features

### Phase 1: Foundation

- Hybrid storage architecture (files + metadata index)
- Token counting with tiktoken
- File I/O with locking and conflict detection
- Version history with snapshots
- Dependency graph management
- File watching for external changes
- Automatic migration system

### Phase 2: DRY Linking

- Link parser for markdown links: `[text](file.md#section)`
- Transclusion syntax: `{{include: file.md#section|options}}`
- Dynamic dependency graph from actual links
- Circular dependency detection
- Link validation with broken link detection

### Phase 3: Validation

- Schema validation with required sections enforcement
- Duplication detection with similarity scoring
- Quality metrics and health scoring (0-100)
- Token budget management with usage tracking
- Configurable validation rules

### Phase 4: Token Optimization

- Relevance scorer with TF-IDF and dependency-based scoring
- Context optimizer with multiple strategies
- Progressive loading (by priority, dependencies, relevance)
- Content summarization with multiple strategies
- Custom rules integration

### Phase 5: Self-Evolution

- Pattern analysis for tracking file access patterns
- Structure analysis for detecting anti-patterns
- AI-driven insight generation with recommendations
- Refactoring suggestions (consolidation, splitting, reorganization)
- Safe execution with rollback support
- Learning from user feedback

### Phase 6: Shared Rules

- Git submodule integration for shared rules
- Context detection (languages, frameworks, task types)
- Intelligent category selection and rule loading
- Rule merging strategies
- Automatic synchronization

### Phase 8: Project Structure

- Standardized `.memory-bank/` directory structure
- Cross-platform Cursor IDE integration via symlinks
- Automated migration from legacy structures
- Interactive project setup with guided configuration
- Structure health monitoring with scoring
- Automated housekeeping

## Getting Started

To get started with Cortex, see the [Getting Started Guide](./getting-started.md).

## API Documentation

For detailed API documentation, see:

- [MCP Tools Reference](./api/tools.md) - All 52 MCP tools
- [Module Documentation](./api/modules.md) - All 41+ modules
- [Exception Reference](./api/exceptions.md) - Exception hierarchy

## User Guides

For configuration and usage guides, see:

- [Configuration Guide](./guides/configuration.md) - All configuration options
- [Migration Guide](./guides/migration.md) - Migrating from old formats
- [Troubleshooting](./guides/troubleshooting.md) - Common issues and solutions

## Development

For development and contributing guides, see:

- [Contributing Guide](./development/contributing.md) - How to contribute
- [Testing Guide](./development/testing.md) - Testing standards and practices
- [Releasing Guide](./development/releasing.md) - Release process

## Support

- **GitHub**: [igrechuhin/cortex](https://github.com/igrechuhin/cortex)
- **Issues**: [GitHub Issues](https://github.com/igrechuhin/cortex/issues)

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
