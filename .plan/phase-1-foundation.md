# Cortex - Phase 1 Implementation Status

## Overview

Phase 1 transforms the Cortex from a template-only system into a hybrid storage infrastructure with intelligent metadata tracking, version history, and migration capabilities.

## Implementation Progress

### ✅ Completed Modules (10/11 core modules)

#### 1. **pyproject.toml** - Dependencies Updated

- Added `watchdog>=4.0.0` for file monitoring
- Added `tiktoken>=0.5.0` for token counting
- Added `aiofiles>=23.0.0` for async file I/O
- Added dev dependencies: pytest, pytest-asyncio
- Version bumped to 0.2.0

#### 2. **exceptions.py** - Custom Exception Classes

- `MemoryBankError` - Base exception
- `FileConflictError` - External modifications detected
- `IndexCorruptedError` - Metadata corruption
- `MigrationFailedError` - Migration failures
- `GitConflictError` - Git conflict markers detected
- `FileLockTimeoutError` - File lock acquisition timeout

#### 3. **token_counter.py** - Token Counting

- Uses tiktoken (cl100k_base for GPT-4)
- Content hash-based caching
- Per-file and per-section counting
- Context size estimation with cost calculations
- Token budget warnings

#### 4. **file_system.py** - File I/O Manager

- Async file operations with aiofiles
- File locking with timeout (*.lock files)
- SHA-256 content hashing
- Markdown section parsing (heading detection)
- Path validation and sandboxing
- Git conflict marker detection

#### 5. **dependency_graph.py** - Dependency Management

- Static dependency hierarchy (7 files)
- Priority-based loading order
- Topological sort for dependencies
- Minimal context computation
- Mermaid diagram export
- Foundation for dynamic links (Phase 2)

#### 6. **version_manager.py** - Version History

- Full file snapshots (not diffs)
- Storage in `.memory-bank-history/`
- Automatic pruning (keep last 10 versions)
- Rollback capability
- Disk usage tracking
- Orphaned snapshot cleanup

#### 7. **metadata_index.py** - JSON Index Management

- Schema: v1.0.0
- Atomic writes (temp file + rename)
- Corruption recovery (rebuild from files)
- File metadata tracking
- Usage analytics
- Dependency graph storage

#### 8. **file_watcher.py** - External Change Detection

- Watchdog-based monitoring
- Debounced updates (1 second delay)
- Async callback support
- Handles create/modify/delete events
- Lifecycle management

#### 9. **migration.py** - Automatic Migration

- Detection of old format
- Timestamped backups
- Initial metadata generation
- Version snapshot creation
- Verification and rollback
- Backup management

#### 10. **test_core_modules.py** - Test Suite

- ✅ All core modules tested and passing
- Integration tests for file operations
- Metadata index verification
- Version management validation

### ⏳ Remaining Work

#### 11. **main.py** - MCP Server Integration (IN PROGRESS)

**Current State:**

- 3 existing tools: `get_memory_bank_structure()`, `generate_memory_bank_template()`, `analyze_project_summary()`
- 1 existing resource: `memory_bank_guide://{section}`
- Simple template provider (no file I/O)

**Needs Implementation:**

##### A. Server Initialization (Startup)

```python
# Global managers
fs_manager: FileSystemManager
metadata_index: MetadataIndex
token_counter: TokenCounter
dep_graph: DependencyGraph
version_manager: VersionManager
migration_manager: MigrationManager
file_watcher: FileWatcherManager

async def initialize_managers(project_root: Path):
    """Initialize all managers on server startup."""
    # 1. Check for migration need
    # 2. Initialize managers
    # 3. Start file watcher
    # 4. Clean up stale locks
```

##### B. Helper Functions

```python
async def get_project_root() -> Path:
    """Get project root (default: cwd)."""

async def ensure_initialized(project_root: Path):
    """Ensure managers are initialized for project."""

async def handle_file_change(file_path: Path, event_type: str):
    """Callback for file watcher."""
```

##### C. New MCP Tools (10 tools)

1. **`initialize_memory_bank(project_root: str = None)`**
   - Create memory-bank/ directory
   - Generate all 7 markdown files from templates
   - Create .memory-bank-index
   - Auto-migrate if old format detected
   - Return initialization status

2. **`read_memory_bank_file(file_name: str, project_root: str = None, include_metadata: bool = False)`**
   - Read file content
   - Optionally include metadata (tokens, versions, usage)
   - Increment read count
   - Check for Git conflicts

3. **`write_memory_bank_file(file_name: str, content: str, project_root: str = None, change_description: str = None)`**
   - Conflict detection (hash check)
   - Write with file locking
   - Create version snapshot
   - Update metadata (tokens, sections, hash)
   - Return write status + new metadata

4. **`get_file_metadata(file_name: str, project_root: str = None)`**
   - Return detailed metadata
   - Token counts, sections, version history
   - Usage statistics

5. **`get_dependency_graph(project_root: str = None, format: str = "json")`**
   - Return complete graph
   - Support "json" or "mermaid" format

6. **`get_version_history(file_name: str, project_root: str = None, limit: int = 10)`**
   - Return version list
   - Timestamps, change types, descriptions

7. **`rollback_file_version(file_name: str, version: int, project_root: str = None)`**
   - Read snapshot
   - Write as new version
   - Update metadata

8. **`check_migration_status(project_root: str = None)`**
   - Detect if migration needed
   - Return migration info

9. **`migrate_memory_bank(project_root: str = None, auto_backup: bool = True)`**
   - Run migration
   - Create backup
   - Return migration result

10. **`get_memory_bank_stats(project_root: str = None)`**
    - Total tokens, files, sizes
    - Usage analytics
    - Dependency graph summary

##### D. Update Existing Tools

- `generate_memory_bank_template()` - Add "[LEGACY]" note, recommend `initialize_memory_bank()`
- Keep other tools unchanged

---

## Implementation Roadmap

### Phase 1 Completion Checklist

#### Immediate (Next Session)

- [ ] Implement server initialization in main.py
- [ ] Add 10 new MCP tools
- [ ] Update legacy tool with deprecation notice
- [ ] Test with actual MCP client
- [ ] Create .plan/phase-1-foundation.md (this file)
- [ ] Create .plan/README.md (overview)

#### Documentation

- [ ] Update main README.md with Phase 1 features
- [ ] Document new MCP tools (API reference)
- [ ] Add migration guide
- [ ] Add example .gitignore rules
- [ ] Create ARCHITECTURE.md

#### Testing

- [ ] Integration test for full workflow
- [ ] Migration test (old format → new format)
- [ ] Test file watcher with real changes
- [ ] Test concurrent operations
- [ ] Test error scenarios

#### Polish

- [ ] Handle edge cases (missing directories, permissions, etc.)
- [ ] Improve error messages
- [ ] Add logging/debugging support
- [ ] Performance optimization
- [ ] Memory leak checks

---

## Critical Files

### Modified

- [src/cortex/main.py](../src/cortex/main.py) - **MAJOR UPDATE NEEDED**

### New Files Created

- [src/cortex/exceptions.py](../src/cortex/exceptions.py) ✅
- [src/cortex/token_counter.py](../src/cortex/token_counter.py) ✅
- [src/cortex/file_system.py](../src/cortex/file_system.py) ✅
- [src/cortex/dependency_graph.py](../src/cortex/dependency_graph.py) ✅
- [src/cortex/version_manager.py](../src/cortex/version_manager.py) ✅
- [src/cortex/metadata_index.py](../src/cortex/metadata_index.py) ✅
- [src/cortex/file_watcher.py](../src/cortex/file_watcher.py) ✅
- [src/cortex/migration.py](../src/cortex/migration.py) ✅
- [test_core_modules.py](../test_core_modules.py) ✅

---

## Technical Debt

### Known Issues

1. **Token Counter Warning**: test_token_counter() doesn't need to be async (minor)
2. **Native TLS Required**: uv needs --native-tls flag due to certificate issues
3. **Lock Cleanup**: Stale locks not cleaned on abnormal shutdown

### Future Improvements (Phase 2+)

1. Dynamic dependency parsing (markdown links)
2. Smart context selection algorithms
3. Automatic summarization triggers
4. Link integrity validation
5. Duplication detection
6. AI-driven refactoring suggestions

---

## Performance Targets

### Phase 1 Goals

- File read: <10ms ✅ (tested)
- File write: <50ms ⏳ (needs verification with versioning)
- Metadata update: <20ms ⏳ (needs verification)
- Token counting: <100ms per file ✅ (tested)
- Migration: <5 seconds for 7 files ⏳ (needs testing)

---

## Next Steps

1. **Complete main.py implementation**
   - Add server initialization
   - Implement 10 new MCP tools
   - Test with Claude Desktop or Cursor

2. **Create comprehensive documentation**
   - Update README.md
   - Write ARCHITECTURE.md
   - Document migration process

3. **Test end-to-end workflows**
   - Initialize new project
   - Migrate existing project
   - Read/write files
   - Rollback versions

4. **Prepare for Phase 2**
   - Document Phase 2 requirements
   - Create .plan/phase-2-dry-linking.md
   - Identify extension points

---

## Success Criteria

Phase 1 is complete when:

- ✅ All core modules implemented and tested
- ⏳ All 10 new MCP tools working
- ⏳ Migration works for existing projects
- ⏳ File watcher detects external changes
- ⏳ Version history and rollback functional
- ⏳ Documentation complete
- ⏳ Tests pass consistently

**Current Status: 80% Complete** (10/11 core modules done, main.py integration remaining)
