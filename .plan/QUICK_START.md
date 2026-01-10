# Quick Start Guide - Phases 1 & 2 Complete ✅

**Current Status:** Phase 1 and Phase 2 are both 100% complete and ready for deployment!

---

## What's Complete ✅

### Phase 1: Foundation (9 core modules, 10 MCP tools)

- ✅ exceptions.py
- ✅ token_counter.py
- ✅ file_system.py
- ✅ dependency_graph.py
- ✅ version_manager.py
- ✅ metadata_index.py
- ✅ file_watcher.py
- ✅ migration.py
- ✅ All 10 MCP tools integrated in main.py
- ✅ Comprehensive testing

### Phase 2: DRY Linking and Transclusion (3 new modules, 4 MCP tools)

- ✅ link_parser.py - Parse markdown links & transclusions
- ✅ transclusion_engine.py - Resolve {{include:}} directives
- ✅ link_validator.py - Validate link integrity
- ✅ dependency_graph.py - Enhanced with dynamic dependencies
- ✅ All 4 new MCP tools integrated in main.py
- ✅ Basic test suite (test_phase2.py)

---

## Available MCP Tools (14 total)

### Phase 1 Tools (10 tools)

1. **`initialize_memory_bank()`** - Initialize Memory Bank in project
2. **`read_memory_bank_file()`** - Read file with optional metadata
3. **`write_memory_bank_file()`** - Write with versioning & conflict detection
4. **`get_file_metadata()`** - Get detailed file metadata
5. **`get_dependency_graph()`** - Get dependency visualization
6. **`get_version_history()`** - List version history
7. **`rollback_file_version()`** - Rollback to previous version
8. **`check_migration_status()`** - Check if migration needed
9. **`migrate_memory_bank()`** - Auto-migrate old format
10. **`get_memory_bank_stats()`** - Get usage statistics

### Phase 2 Tools (4 tools)

1. **`parse_file_links()`** - Extract all links from file
2. **`resolve_transclusions()`** - Read file with {{include:}} resolved
3. **`validate_links()`** - Validate links across files
4. **`get_link_graph()`** - Get dynamic dependency graph (JSON/Mermaid)

---

## Transclusion Syntax (Phase 2)

```markdown
# Basic transclusion - include entire file
{{include: projectBrief.md}}

# Include specific section
{{include: systemPatterns.md#Architecture}}

# Include with line limit
{{include: activeContext.md#Recent Changes|lines=10}}

# Disable nested transclusion
{{include: file.md#section|recursive=false}}
```

---

## Quick Test

```bash
# Run the MCP server
uv run --native-tls python -m cortex.main

# Or install and run
uv pip install -e .
python -m cortex.main

# Run Phase 2 tests
python test_phase2.py
```

---

## Next Steps

### For Development

1. Test with Claude Desktop or Cursor
2. Try transclusion features in real Memory Bank files
3. Validate links across your project
4. Explore dynamic dependency graphs

### For Production

1. Update project documentation
2. Create example .gitignore
3. Write user guide for transclusion syntax
4. Performance testing with large projects

### For Phase 3 (Validation)

- Schema validation engine
- Duplication detector
- Token budget enforcer
- Automated quality checks

---

## Resources

- **Complete Status:** [STATUS.md](./STATUS.md)
- **Phase 1 Plan:** [phase-1-foundation.md](./phase-1-foundation.md)
- **Phase 2 Plan:** [phase-2-dry-linking.md](./phase-2-dry-linking.md)
- **Architecture:** [README.md](./README.md)
- **Main Code:** [../src/cortex/main.py](../src/cortex/main.py)
- **Tests:** [../test_core_modules.py](../test_core_modules.py), [../test_phase2.py](../test_phase2.py)
