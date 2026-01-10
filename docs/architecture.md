# Architecture

This document describes the high-level architecture of Cortex.

## Overview

Cortex is structured as an MCP (Model Context Protocol) server that provides 52 tools for managing structured documentation (Memory Bank files). The system is built with a modular, layered architecture designed for:

- **Extensibility**: Easy to add new phases and features
- **Maintainability**: Each module has a single, well-defined responsibility
- **Performance**: Async I/O throughout, with caching and lazy initialization
- **Safety**: File locking, version history, and rollback capabilities
- **Quality**: Comprehensive testing, logging, and error handling

## System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         MCP Client                          │
│           (Claude Desktop, Cursor IDE, etc.)                │
└────────────────────────┬────────────────────────────────────┘
                         │ stdio (JSON-RPC)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (FastMCP)                     │
│                   52 Tools (10 phases)                      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│                    Manager Layer                           │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  File System   │  │   Dependency   │  │   Version    │  │
│  │    Manager     │  │      Graph     │  │   Manager    │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  Transclusion  │  │   Validation   │  │   Context    │  │
│  │     Engine     │  │     Engine     │  │  Optimizer   │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │   Learning     │  │  Refactoring   │  │   Shared     │  │
│  │    Engine      │  │     Engine     │  │    Rules     │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└────────────┬───────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Storage Layer                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Markdown Files (Git-tracked)              │    │
│  │  .memory-bank/knowledge/                            │    │
│  │  ├── projectBrief.md                                │    │
│  │  ├── productContext.md                              │    │
│  │  └── ... (7 core files)                             │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          Metadata (NOT Git-tracked)                 │    │
│  │  .memory-bank-index                                 │    │
│  │  .memory-bank-history/                              │    │
│  │  .memory-bank-access-log.json                       │    │
│  │  .memory-bank-learning.json                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Layered Architecture

### Layer 1: MCP Server (Entry Point)

**Files**: `main.py`, `server.py`

- Entry point for the MCP server
- Tool registration via `@mcp.tool()` decorators
- Communication over stdio using JSON-RPC
- Delegates all business logic to managers

### Layer 2: Tool Modules (10 modules)

**Files**: `tools/phase*.py`, `tools/legacy.py`

Each tool module focuses on a specific phase:

- **phase1_foundation.py** (10 tools) - Core Memory Bank operations
- **phase2_linking.py** (4 tools) - DRY linking and transclusion
- **phase3_validation.py** (5 tools) - Validation and quality checks
- **phase4_optimization.py** (7 tools) - Token optimization and rules
- **phase5_analysis.py** (3 tools) - Pattern analysis and insights
- **phase5_refactoring.py** (4 tools) - Refactoring suggestions
- **phase5_execution.py** (6 tools) - Safe execution and learning
- **phase6_shared_rules.py** (4 tools) - Shared rules management
- **phase8_structure.py** (6 tools) - Project structure management
- **legacy.py** (3 tools) - Deprecated legacy tools

### Layer 3: Manager Initialization

**Files**: `managers/initialization.py`, `container.py`

- Centralized manager lifecycle management
- Dependency injection pattern
- ManagerContainer dataclass for type-safe access
- Lazy initialization of all services

### Layer 4: Business Logic (41+ Modules)

Each manager/service module has a single responsibility:

#### Phase 1: Foundation (9 modules)

- `file_system.py` - File I/O, locking, hashing
- `metadata_index.py` - JSON index, corruption recovery
- `token_counter.py` - tiktoken integration
- `dependency_graph.py` - Dependency tracking
- `graph_algorithms.py` - Graph algorithms (BFS, DFS, cycles)
- `version_manager.py` - Snapshots, rollback
- `migration.py` - Auto-migration
- `file_watcher.py` - External change detection
- `exceptions.py` - Custom exception hierarchy

#### Phase 2: DRY Linking (3 modules)

- `link_parser.py` - Parse links & transclusions
- `transclusion_engine.py` - Resolve `{{include:}}`
- `link_validator.py` - Validate link integrity

#### Phase 3: Validation (4 modules)

- `schema_validator.py` - File schema validation
- `duplication_detector.py` - Find duplicate content
- `quality_metrics.py` - Calculate quality scores
- `validation_config.py` - User configuration

#### Phase 4: Optimization (6 modules)

- `relevance_scorer.py` - Score files by relevance
- `context_optimizer.py` - Optimize context within budget
- `optimization_strategies.py` - Strategy implementations
- `progressive_loader.py` - Load context incrementally
- `summarization_engine.py` - Summarize content
- `optimization_config.py` - Configuration management

#### Phase 4 Enhancement (2 modules)

- `rules_manager.py` - Manage custom rules
- `rules_indexer.py` - File scanning and indexing

#### Phase 5: Self-Evolution (10 modules)

- `pattern_analyzer.py` - Track usage patterns
- `structure_analyzer.py` - Analyze organization
- `insight_engine.py` - Generate AI insights
- `refactoring_engine.py` - Generate suggestions
- `consolidation_detector.py` - Detect duplicates
- `split_recommender.py` - Recommend splits
- `split_analyzer.py` - File structure analysis
- `reorganization_planner.py` - Plan reorganization
- `refactoring_executor.py` - Execute refactorings
- `execution_validator.py` - Validate operations

#### Phase 5 Execution & Learning (5 modules)

- `approval_manager.py` - Manage user approvals
- `rollback_manager.py` - Handle rollbacks
- `learning_engine.py` - Learn from feedback
- `learning_data_manager.py` - Data persistence
- `adaptation_config.py` - Configuration

#### Phase 6: Shared Rules (2 modules)

- `shared_rules_manager.py` - Git submodule integration
- `context_detector.py` - Intelligent context detection

#### Phase 8: Project Structure (2 modules)

- `structure_manager.py` - Structure lifecycle, migration, health
- `template_manager.py` - Plan & rule templates, interactive setup

#### Supporting Modules (4 modules)

- `protocols.py` - Protocol definitions (PEP 544)
- `logging_config.py` - Structured logging
- `responses.py` - Standardized responses
- `resources.py` - Template and guide exports

### Layer 5: Storage

#### Git-Tracked Files

- Markdown files in `.memory-bank/knowledge/`
- Rules in `.memory-bank/rules/`
- Plans in `.memory-bank/plans/`

#### Not Git-Tracked

- `.memory-bank-index` - Metadata JSON
- `.memory-bank-history/` - Version snapshots
- `.memory-bank-access-log.json` - Usage patterns
- `.memory-bank-learning.json` - Learning data
- `.memory-bank-approvals.json` - Approval records
- `.memory-bank-refactoring-history.json` - Execution history
- `.memory-bank-rollbacks.json` - Rollback history

## Design Patterns

### Dependency Injection

All managers receive dependencies via constructor:

```python
class FileSystemManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
```

Managers are initialized in `managers/initialization.py` and stored in `ManagerContainer`.

### Protocol-Based Abstractions

PEP 544 structural subtyping for loose coupling:

```python
# protocols.py
class FileSystemProtocol(Protocol):
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str) -> None: ...

# Consumers depend on protocol, not concrete class
class TransclusionEngine:
    def __init__(self, fs: FileSystemProtocol): ...
```

### Async Throughout

All I/O operations are async using `aiofiles`:

```python
async with aiofiles.open(file_path, "r") as f:
    content = await f.read()
```

### Lazy Initialization

Managers are only initialized when first requested:

```python
async def get_managers(project_root: Path) -> ManagerContainer:
    if project_root not in _managers:
        _managers[project_root] = await _initialize_all_managers(project_root)
    return _managers[project_root]
```

### Event-Driven File Watching

Watchdog library monitors file changes:

```python
class FileWatcher:
    def __init__(self, callback: Callable[[str, str], Awaitable[None]]):
        self.callback = callback  # Called on file change
```

### Caching

Multiple caching layers for performance:

- Token counts cached by content hash
- Transclusion results cached
- File content cached with TTL
- Relevance scores cached

## Data Flow

### Read Flow

```text
1. MCP Client sends request
   ↓
2. Tool handler receives request
   ↓
3. Get managers for project
   ↓
4. Read file via FileSystemManager
   ↓
5. Resolve transclusions via TransclusionEngine
   ↓
6. Return content to client
```

### Write Flow

```text
1. MCP Client sends write request
   ↓
2. Tool handler validates request
   ↓
3. FileSystemManager acquires lock
   ↓
4. Create version snapshot
   ↓
5. Write file atomically
   ↓
6. Update metadata index
   ↓
7. Release lock
   ↓
8. Return success to client
```

### Validation Flow

```text
1. MCP Client requests validation
   ↓
2. SchemaValidator checks structure
   ↓
3. DuplicationDetector finds duplicates
   ↓
4. LinkValidator checks links
   ↓
5. QualityMetrics calculates score
   ↓
6. Return validation report
```

### Optimization Flow

```text
1. MCP Client requests context optimization
   ↓
2. RelevanceScorer scores all files
   ↓
3. ContextOptimizer selects files within budget
   ↓
4. ProgressiveLoader loads selected files
   ↓
5. SummarizationEngine summarizes if needed
   ↓
6. Return optimized context
```

## Error Handling

### Exception Hierarchy

```text
Exception
└── MemoryBankError (base)
    ├── FileSystemError
    │   ├── FileNotFoundError
    │   ├── FileLockError
    │   └── FileConflictError
    ├── ValidationError
    │   ├── SchemaValidationError
    │   ├── LinkValidationError
    │   └── DuplicationError
    ├── OptimizationError
    │   ├── TokenBudgetExceededError
    │   └── RelevanceScoringError
    ├── RefactoringError
    │   ├── RefactoringExecutionError
    │   └── RollbackError
    └── MigrationError
```

### Logging

Structured logging with context:

```python
logger.info("File written", extra={
    "file_path": str(file_path),
    "size_bytes": len(content),
    "operation": "write"
})
```

### Standardized Responses

All tools return consistent JSON:

```python
# Success
{
    "status": "success",
    "data": {...},
    "metadata": {...}
}

# Error
{
    "status": "error",
    "error": "Error message",
    "error_type": "FileSystemError"
}
```

## Performance Considerations

### Token Counting

- Lazy tiktoken initialization (10-30s first time)
- Content-based caching (SHA-256 hash)
- Cached after first use

### File Operations

- Atomic writes via temp files
- File locking to prevent conflicts
- Debounced file watching (300ms)

### Memory Management

- Stream large files with async generators
- Progressive loading with budget limits
- Summarization for token reduction

### Concurrency

- Async I/O throughout
- File locks for safe concurrent access
- Event loop integration for watcher

## Security

### Path Validation

All file paths validated against base directories:

```python
resolved = file_path.resolve()
if not resolved.is_relative_to(base_dir):
    raise SecurityError("Path traversal attempt")
```

### Input Validation

- Validate all external inputs
- Sanitize file paths
- Check file extensions

### File Locking

Prevent concurrent modifications:

```python
async with self._acquire_lock(file_path):
    # Critical section
    await self._write_file(file_path, content)
```

## Testing Strategy

### Unit Tests (1,554 tests)

- One test file per module
- AAA pattern (Arrange-Act-Assert)
- Mock external dependencies
- ~88% overall coverage

### Integration Tests

- Test cross-module workflows
- Real file system operations
- Async test support with pytest-asyncio

### Fixtures

- Shared fixtures in `conftest.py`
- Sample Memory Bank files
- Temporary directories

## Deployment

### Standalone Server

```bash
uv run cortex
```

### Integrated with MCP Client

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

## Future Architecture Improvements

1. **SQLite Backend** - Replace JSON index with SQLite for better performance
2. **Incremental Diffs** - Store diffs instead of full snapshots for version history
3. **Distributed Caching** - Redis for multi-user scenarios
4. **Background Workers** - Queue expensive operations (pattern analysis, refactoring)
5. **Plugin System** - Support third-party extensions

## References

- [MCP Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Cline Memory Bank Pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank)
