# Architecture

This document describes the high-level architecture of Cortex.

## Overview

Cortex is structured as an MCP (Model Context Protocol) server that provides 70+ tools for managing structured documentation (Memory Bank files). The system is built with a modular, layered architecture designed for:

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
                         │ stdio (default) or Bridge → HTTP/SSE
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (FastMCP)                     │
│                  70+ tools (multiple phases)                │
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
│  │  .cortex/memory-bank/                               │    │
│  │  ├── projectBrief.md                                │    │
│  │  ├── productContext.md                              │    │
│  │  └── ... (7 core files)                             │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          Metadata and Cache (NOT Git-tracked)       │    │
│  │  .cortex/index.json                                 │    │
│  │  .cortex/history/                                   │    │
│  │  .cortex/.cache/                                    │    │
│  │  .cortex/config/learning.json                       │    │
│  │  .cortex/approvals.json, rollbacks.json, etc.       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Layered Architecture

### Layer 1: MCP Server (Entry Point)

**Files**: `main.py`, `server.py`

- Entry point for the MCP server
- Tool registration via `@mcp.tool()` decorators
- Transport: stdio (default), SSE, or streamable-HTTP (see Bridge Transport)
- Delegates all business logic to managers

### Bridge Transport (stdio vs HTTP/SSE)

Cortex supports multiple MCP transports for different deployment scenarios.

**Configuration**: Environment variables `CORTEX_MCP_TRANSPORT`, `CORTEX_MCP_PORT`, `CORTEX_MCP_HOST` (see `transport_config.py`). When `CORTEX_MCP_PORT` is set, default transport is SSE unless overridden.

| Transport | Use case | Description |
|-----------|----------|-------------|
| **stdio** | Default, Cursor/IDE | JSON-RPC over stdin/stdout; one process per client session |
| **sse** | HTTP server | Server-Sent Events at `/sse`; client connects to port |
| **streamable-http** | Concurrent HTTP | Streamable HTTP transport; supports concurrent request handling |

**Bridge mode**: When the client (e.g. Cursor) only supports stdio, the **Bridge** (`bridge.py`) runs Cortex as a subprocess with `streamable-http` and proxies between Cursor's stdio and Cortex's HTTP endpoint. This keeps a single on/off switch in the client while Cortex handles requests over HTTP. Requires `uv sync --extra server`. URL and port are controlled by `CORTEX_BRIDGE_URL` and `CORTEX_MCP_PORT`.

### Layer 2: Tool Modules

**Files**: `tools/` (many modules; see [API tools](api/tools.md) for the full list)

Tool modules are grouped by phase and responsibility. Representative groups:

- **Phase 1** – Foundation: file operations, version, rollback, dependency, stats (split across `phase1_foundation_*`, `file_operations`, etc.)
- **Phase 2** – Linking and transclusion
- **Phase 3** – Validation and quality checks
- **Phase 4** – Context optimization and rules
- **Phase 5** – Analysis, refactoring, execution, evaluation (including evaluation dashboard helpers)
- **Phase 8** – Structure management, validation, operations, docs
- **Session and health** – `session_start_tools`, `connection_health`, `health_check_operations`, `compaction_operations`
- **Pre-commit and quality** – `pre_commit_tools`, `markdown_operations`
- **Plans and roadmap** – `plan_operations`, `plan_completion`, `roadmap_operations`
- **Synapse** – `synapse_tools`, Synapse prompts registration
- **Other** – `query_memory_bank_operations`, `query_usage_operations`, `cache_json_tools`, `script_capture_tools`, `sequential_thinking`, `task_locking`, and others

Total tool count is 71 (70+ tools, 7 prompts); exact count and parameters are in `docs/api/tools.md` and `src/cortex/tools/__init__.py`. Naming rules: [naming conventions](architecture/naming-conventions.md).

### Layer 3: Manager Initialization

**Files**: `managers/initialization.py`, `manager_initialization.py`, `core/manager_registry.py`

- Centralized manager lifecycle: `get_managers(project_root)` resolves root, then calls process-scoped `ManagerRegistry.get_managers()`; first call for a project root runs `initialize_managers()`.
- **Lazy loading**: Core managers (e.g. FileSystemManager, MetadataIndex, path resolver) are initialized eagerly; all other managers are wrapped in `LazyManager` and created on first access.
- Dependency injection: managers receive dependencies via constructors; built in `manager_initialization.py` (e.g. `add_linking_managers`, `add_optimization_managers`).
- Type-safe access via `ManagersDict` (Pydantic model).

**Manager initialization flow:**

```text
Tool call with project_root
        ↓
get_managers(project_root)
        ↓
ManagerRegistry.get_managers(project_root)
        ↓
  [cache miss?] → initialize_managers(project_root)
        ↓
  _init_core_managers() [eager]
        ↓
  add_*_managers() → LazyManager wrappers for non-core
        ↓
  cache result → return ManagersDict
        ↓
Tool accesses managers["fs"] or managers["context_optimizer"]
        ↓
  LazyManager: on first access → build real instance, replace in dict
```

### Layer 4: Business Logic (20+ Modules)

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
- `optimization/config.py` - Configuration management

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

- Markdown files in `.cortex/memory-bank/`
- Rules in `.cortex/synapse/rules/` (or `.cortex/rules/`)
- Plans in `.cortex/plans/`

#### Not Git-Tracked

- `.cortex/index.json` - Metadata JSON (includes usage analytics)
- `.cortex/history/` - Version snapshots
- `.cortex/.cache/` - Cache (summaries, markdown-lint, usage when writable)
- `.cortex/config/learning.json` - Learning data
- `.cortex/approvals.json` - Approval records
- `.cortex/refactoring-history.json` - Execution history
- `.cortex/rollbacks.json` - Rollback history

### Synapse Integration Architecture

**Synapse** is the shared rules-and-prompts repository integrated as a Git submodule under `.cortex/synapse/`. It provides prompts, rules, agents, and scripts used by the commit pipeline, implement workflow, and quality gates.

**Directory layout** (under `.cortex/synapse/`):

- **prompts/** – Prompt templates (e.g. commit, implement, analyze, create-plan); registered with the MCP server for Cursor/IDE.
- **rules/** – Rule files (`.mdc`): `general/`, `python/`, `markdown/`; loaded by the rules manager and `get_synapse_rules()`.
- **agents/** – Synapse agents (e.g. plan-archiver, quality-checker, memory-bank-updater); referenced by orchestration prompts.
- **scripts/** – Language-specific scripts (e.g. `python/check_formatting.py`, `run_tests.py`); used by `execute_pre_commit_checks` and CI.

**Rule loading**: The rules manager indexes `.mdc` files under the rules directory. Tools such as `rules(operation="get_relevant", task_description="...")` and `get_synapse_rules(task_description="...")` return relevant rules for a task. Paths are resolved via `get_structure_info()` (e.g. `structure_info.paths.rules`); the Synapse submodule is the canonical source for shared rules and prompts.

**Submodule pattern**: Projects add Synapse via `git submodule add <url> .cortex/synapse/`. The initialize and setup_synapse prompts configure the submodule; `synapse(operation="sync")` (or equivalent) keeps it updated. Cursor integration may symlink `.cursor/synapse` to `.cortex/synapse` for IDE discovery.

### Health Check and Monitoring Architecture

Health checks are split between **connection health** (MCP server), **structure health** (Memory Bank layout), and the **health_check** module (prompt/rule analysis).

**Connection health** (`tools/connection_health.py`, `core/mcp_stability.py`):

- `check_mcp_connection_health()` – Reports MCP connection status, concurrent operations, semaphore usage, and a simple healthy/unhealthy flag. Used by the commit pipeline and clients to verify the server is responsive before long operations.

**Structure health** (`structure/lifecycle/health.py`, `structure_manager.py`):

- `StructureHealthChecker` – Validates directories, symlinks, config, and memory bank files; returns a score (0–100), grade (A–F), and status (healthy/good/fair/warning/critical). Used by `check_structure_health` and structure lifecycle tools.

**Health check module** (`health_check/`):

- **tool_analyzer.py** – Analyzes tool usage and dependencies.
- **prompt_analyzer.py** – Scans `.cortex/synapse/prompts/` for overlap and duplication.
- **rule_analyzer.py**, **quality_validator.py**, **report_generator.py** – Rule quality and report generation.
- **similarity_engine.py**, **dependency_mapper.py** – Support analysis for prompts and rules.

These components support session optimization, context-effectiveness analysis, and commit-pipeline preflight (e.g. checking MCP health before Step 12).

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
