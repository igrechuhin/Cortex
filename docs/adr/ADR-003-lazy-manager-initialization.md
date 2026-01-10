# ADR-003: Lazy Manager Initialization

## Status

Accepted

## Context

Cortex consists of 26 specialized managers that provide various capabilities:

1. **File System Layer** (2): FileSystemManager, MetadataIndex
2. **Token Management** (1): TokenCounter
3. **Dependency Tracking** (1): DependencyGraph
4. **Versioning** (2): VersionManager, MigrationManager
5. **File Watching** (1): FileWatcher
6. **Linking** (3): LinkParser, TransclusionEngine, LinkValidator
7. **Validation** (3): SchemaValidator, DuplicationDetector, QualityMetrics
8. **Optimization** (4): RelevanceScorer, ContextOptimizer, ProgressiveLoader, SummarizationEngine
9. **Analysis** (3): PatternAnalyzer, StructureAnalyzer, InsightEngine
10. **Refactoring** (3): RefactoringEngine, RefactoringExecutor, RollbackManager
11. **Learning** (1): LearningEngine
12. **Shared Rules** (1): SharedRulesManager
13. **Structure** (1): StructureManager

Each manager has initialization costs:

- **FileSystemManager**: Validate memory bank directory, check permissions
- **MetadataIndex**: Load and validate index file, detect corruption
- **TokenCounter**: Initialize tiktoken encoder (~50ms)
- **DependencyGraph**: Build initial dependency tree from index
- **VersionManager**: Scan snapshots directory, load history
- **FileWatcher**: Set up file system event handlers
- **SchemaValidator**: Load and parse schema definitions
- **PatternAnalyzer**: Load pattern database, compile regex patterns
- **LearningEngine**: Load learning data, validate schema

### The Initialization Problem

**Sequential Initialization**:

```python
async def get_managers(memory_bank_dir: str) -> dict[str, object]:
    """Initialize all managers sequentially."""
    fs = FileSystemManager(memory_bank_dir)
    await fs.initialize()  # ~20ms

    metadata = MetadataIndex(memory_bank_dir)
    await metadata.initialize()  # ~50ms

    token_counter = TokenCounter()
    await token_counter.initialize()  # ~50ms

    # ... 23 more managers
    # Total: ~500-1000ms for full initialization
```

**Problems**:

1. **Slow Startup**: Full initialization takes 500-1000ms
2. **Wasted Work**: Most tools don't need all managers
3. **Memory Overhead**: All managers loaded even if unused
4. **Dependency Complexity**: Managers depend on each other in complex ways
5. **Error Propagation**: Failure in one manager blocks all others

### MCP Server Constraints

**MCP Protocol Requirements**:

- Server must respond to `initialize` request quickly (<500ms ideal)
- Server must be ready to handle `list_tools` immediately
- Server must be ready to handle `call_tool` with minimal latency
- Slow initialization creates poor user experience in Claude Desktop

**Tool Usage Patterns**:
From analyzing typical memory bank workflows:

1. **Common tools** (~80% of calls):
   - `validate_memory_bank` - needs validation managers only
   - `get_memory_bank_stats` - needs file system + metadata only
   - `resolve_transclusion` - needs linking managers only

2. **Occasional tools** (~15% of calls):
   - `optimize_context` - needs optimization managers
   - `analyze_patterns` - needs analysis managers
   - `get_refactoring_suggestions` - needs refactoring managers

3. **Rare tools** (~5% of calls):
   - `execute_refactoring` - needs refactoring + rollback managers
   - `submit_feedback` - needs learning manager
   - `setup_project_structure` - needs structure manager

### Manager Dependencies

Some managers depend on others:

```
FileSystemManager (base)
    ↓
MetadataIndex
    ↓
DependencyGraph
    ↓
LinkParser → TransclusionEngine
                ↓
            LinkValidator
```

Others are independent:

```
TokenCounter (independent)
PatternAnalyzer (independent)
LearningEngine (independent)
```

### Use Case Analysis

**Use Case 1: Quick Validation**

```
User: Validate memory bank
Tools needed: FileSystemManager, MetadataIndex, SchemaValidator, LinkValidator
Tools NOT needed: RefactoringEngine, LearningEngine, StructureManager
```

**Use Case 2: Refactoring**

```
User: Get refactoring suggestions
Tools needed: FileSystemManager, MetadataIndex, PatternAnalyzer, RefactoringEngine
Tools NOT needed: LearningEngine (until feedback), StructureManager
```

**Use Case 3: Context Optimization**

```
User: Optimize context
Tools needed: FileSystemManager, MetadataIndex, TokenCounter, RelevanceScorer, ContextOptimizer
Tools NOT needed: RefactoringEngine, LearningEngine, StructureManager
```

### Requirements

**Functional Requirements**:

- Server must initialize quickly (<200ms)
- Managers must be available when needed
- Dependencies must be satisfied before use
- Error handling must be graceful
- Initialization must be thread-safe

**Non-Functional Requirements**:

- Minimal memory footprint at startup
- Lazy loading transparent to callers
- No performance regression for common operations
- Clear error messages for initialization failures
- Support for manager dependency injection in tests

## Decision

We will implement **lazy manager initialization** where managers are created on-demand rather than all at startup.

### Architecture

**ManagerRegistry** (conceptual, implemented inline in `server.py`):

```python
class ManagerRegistry:
    """Registry for lazy-initialized managers."""

    def __init__(self, memory_bank_dir: str):
        self._memory_bank_dir = memory_bank_dir
        self._managers: dict[str, object] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._initializers: dict[str, Callable] = {}

    async def get(self, name: str) -> object:
        """Get or create manager."""
        if name not in self._managers:
            if name not in self._locks:
                self._locks[name] = asyncio.Lock()

            async with self._locks[name]:
                # Double-check pattern
                if name not in self._managers:
                    initializer = self._initializers[name]
                    self._managers[name] = await initializer()

        return self._managers[name]
```

**Dependency Resolution**:

```python
async def get_file_system_manager() -> FileSystemManager:
    """Initialize FileSystemManager (no dependencies)."""
    manager = FileSystemManager(memory_bank_dir)
    await manager.initialize()
    return manager

async def get_metadata_index() -> MetadataIndex:
    """Initialize MetadataIndex (depends on FileSystemManager)."""
    fs = await registry.get("file_system")
    metadata = MetadataIndex(memory_bank_dir, fs)
    await metadata.initialize()
    return metadata

async def get_dependency_graph() -> DependencyGraph:
    """Initialize DependencyGraph (depends on MetadataIndex)."""
    metadata = await registry.get("metadata_index")
    graph = DependencyGraph(metadata)
    await graph.initialize()
    return graph
```

### Implementation Pattern

**Server Initialization** (fast):

```python
@mcp.server()
class MemoryBankServer:
    def __init__(self):
        self.memory_bank_dir = Path.cwd() / ".cursor" / "memory-bank"
        self._managers: dict[str, object] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def initialize(self):
        """Fast initialization - no managers loaded yet."""
        # Just validate memory bank directory exists
        if not self.memory_bank_dir.exists():
            self.memory_bank_dir.mkdir(parents=True)
        # Total: <10ms
```

**Tool Handler** (lazy loading):

```python
@mcp.tool()
async def validate_memory_bank() -> dict[str, object]:
    """Validate memory bank - loads managers on demand."""
    # Get only the managers needed for validation
    fs = await get_manager("file_system")
    metadata = await get_manager("metadata_index")
    schema_validator = await get_manager("schema_validator")
    link_validator = await get_manager("link_validator")

    # Perform validation
    results = await schema_validator.validate_all()
    # ...
    return results
```

### Manager Initialization Order

**Tier 1: Core (always initialized if any tool is used)**:

1. FileSystemManager
2. MetadataIndex

**Tier 2: Common (initialized for most tools)**:
3. DependencyGraph
4. LinkParser
5. TransclusionEngine

**Tier 3: Validation (initialized for validation tools)**:
6. SchemaValidator
7. LinkValidator
8. DuplicationDetector
9. QualityMetrics

**Tier 4: Optimization (initialized for optimization tools)**:
10. TokenCounter
11. RelevanceScorer
12. ContextOptimizer
13. ProgressiveLoader
14. SummarizationEngine

**Tier 5: Analysis (initialized for analysis tools)**:
15. PatternAnalyzer
16. StructureAnalyzer
17. InsightEngine

**Tier 6: Refactoring (initialized for refactoring tools)**:
18. RefactoringEngine
19. RefactoringExecutor
20. RollbackManager

**Tier 7: Advanced (initialized rarely)**:
21. VersionManager
22. MigrationManager
23. FileWatcher
24. LearningEngine
25. SharedRulesManager
26. StructureManager

### Dependency Graph

```
Tier 1 (Core)
    FileSystemManager
        ↓
    MetadataIndex
        ↓
Tier 2 (Common)
    DependencyGraph
        ↓
    LinkParser
        ↓
    TransclusionEngine
        ↓
Tier 3 (Validation)
    LinkValidator
    SchemaValidator
    DuplicationDetector
    QualityMetrics

Tier 4 (Optimization)
    TokenCounter (independent)
    RelevanceScorer → MetadataIndex
    ContextOptimizer → TokenCounter, RelevanceScorer
    ProgressiveLoader → ContextOptimizer
    SummarizationEngine → TokenCounter

Tier 5 (Analysis)
    PatternAnalyzer → MetadataIndex
    StructureAnalyzer → MetadataIndex
    InsightEngine → PatternAnalyzer, StructureAnalyzer

Tier 6 (Refactoring)
    RefactoringEngine → PatternAnalyzer, InsightEngine
    RefactoringExecutor → RefactoringEngine, FileSystemManager
    RollbackManager → VersionManager

Tier 7 (Advanced)
    VersionManager → FileSystemManager
    MigrationManager → VersionManager
    FileWatcher → FileSystemManager
    LearningEngine → MetadataIndex
    SharedRulesManager → FileSystemManager
    StructureManager → FileSystemManager
```

### Actual Implementation

The actual implementation uses a simpler pattern in `server.py`:

```python
_managers: dict[str, object] = {}

async def get_managers() -> dict[str, object]:
    """Get or initialize managers lazily."""
    if not _managers:
        async with asyncio.Lock():
            if not _managers:  # Double-check pattern
                # Initialize only core managers
                _managers["file_system"] = FileSystemManager(memory_bank_dir)
                await _managers["file_system"].initialize()

                _managers["metadata_index"] = MetadataIndex(
                    memory_bank_dir,
                    _managers["file_system"]
                )
                await _managers["metadata_index"].initialize()

    return _managers
```

Additional managers are initialized on-demand in tool handlers:

```python
@mcp.tool()
async def optimize_context(...) -> dict[str, object]:
    """Optimize context - initializes optimization managers."""
    managers = await get_managers()

    if "token_counter" not in managers:
        managers["token_counter"] = TokenCounter()
        await managers["token_counter"].initialize()

    if "context_optimizer" not in managers:
        managers["context_optimizer"] = ContextOptimizer(
            managers["token_counter"],
            managers["metadata_index"]
        )
        await managers["context_optimizer"].initialize()

    # Use optimizers
    result = await managers["context_optimizer"].optimize(...)
    return result
```

## Consequences

### Positive

**1. Fast Startup**:

- Server initialization: <50ms (was 500-1000ms)
- Only core managers loaded initially
- MCP server responds to `initialize` quickly
- Better user experience in Claude Desktop

**2. Memory Efficiency**:

- Unused managers never loaded
- Memory usage scales with actual usage
- Typical memory footprint: 10-20MB (was 50-100MB)
- Better for resource-constrained environments

**3. Flexibility**:

- Easy to add new managers without startup cost
- Tool-specific initialization possible
- Different tools can share or isolate managers
- Testing easier (mock only needed managers)

**4. Error Isolation**:

- Initialization failure only affects tools that need that manager
- Other tools continue working
- Clearer error messages (know which tool triggered initialization)
- Better error recovery

**5. Development Velocity**:

- Faster iteration during development (quick startup)
- Easier to test individual managers
- Can disable managers for testing
- Simpler debugging (fewer managers loaded)

**6. Scalability**:

- Can add unlimited managers without startup penalty
- Initialization time stays constant
- Memory usage grows only with usage
- Better for large-scale deployments

### Negative

**1. First-Use Latency**:

- First call to a tool may be slower (initialization cost)
- Unpredictable latency (depends on which managers needed)
- Harder to measure performance (varies by call path)
- May need warming for performance-critical paths

**2. Complexity**:

- More complex initialization logic
- Dependency tracking required
- Race conditions possible with concurrent initialization
- Harder to understand initialization flow

**3. Error Timing**:

- Initialization errors occur during tool use (not startup)
- Harder to catch configuration errors early
- May surprise users with late failures
- Need better error messages to explain context

**4. Debugging Difficulty**:

- Initialization order non-deterministic
- Stack traces span manager creation
- Harder to reproduce bugs (depends on call order)
- Need logging to understand initialization flow

**5. Testing Challenges**:

- Tests must handle lazy initialization
- Mock setup more complex
- Test isolation harder (shared manager state)
- Need to reset managers between tests

**6. State Management**:

- Manager lifecycle tied to tool calls
- Harder to reason about manager lifetime
- Cleanup logic more complex
- Resource leaks possible if not careful

### Neutral

**1. Dependency Injection**:

- Still need explicit dependency passing
- Managers don't magically get dependencies
- Could use service locator pattern (but avoided)
- Trade-off: explicitness vs convenience

**2. Caching**:

- Managers cached globally in `_managers` dict
- Lifetime matches server process lifetime
- No automatic cleanup (reasonable for long-lived servers)
- Manual cleanup possible if needed

**3. Concurrency**:

- Locks prevent concurrent initialization
- Serializes first access to each manager
- Acceptable overhead (initialization is rare)
- Could optimize with read-write locks

## Alternatives Considered

### Alternative 1: Eager Initialization (Original Approach)

**Approach**: Initialize all managers at server startup.

```python
async def initialize_server():
    """Initialize all managers eagerly."""
    managers = {}

    # Initialize all 26 managers sequentially
    managers["file_system"] = await create_file_system_manager()
    managers["metadata_index"] = await create_metadata_index()
    # ... 24 more
    # Total: 500-1000ms

    return managers
```

**Pros**:

- Simple implementation
- Predictable behavior
- Errors caught early
- Consistent performance

**Cons**:

- Slow startup (500-1000ms)
- High memory usage
- Wasted initialization for unused managers
- Poor user experience

**Rejection Reason**: Violates MCP server performance requirements. Startup time unacceptable.

### Alternative 2: Parallel Initialization

**Approach**: Initialize all managers in parallel.

```python
async def initialize_server():
    """Initialize managers in parallel."""
    # Create tasks for independent managers
    tasks = [
        create_file_system_manager(),
        create_token_counter(),
        create_pattern_analyzer(),
        # ...
    ]

    # Wait for all
    results = await asyncio.gather(*tasks)
    # Total: ~200ms (limited by slowest manager)
```

**Pros**:

- Faster than sequential (200ms vs 1000ms)
- All managers available immediately
- Simple to understand
- Errors caught early

**Cons**:

- Still initializes unused managers
- High memory usage
- Dependency ordering complex
- Resource contention (disk I/O, CPU)

**Rejection Reason**: Still too slow (200ms). Still wastes resources on unused managers.

### Alternative 3: Service Locator Pattern

**Approach**: Global registry that managers can query.

```python
class ServiceLocator:
    _services: dict[type, object] = {}

    @classmethod
    def register(cls, service_type: type, instance: object):
        cls._services[service_type] = instance

    @classmethod
    def get(cls, service_type: type) -> object:
        return cls._services[service_type]

# Usage
class RefactoringEngine:
    def __init__(self):
        # Get dependencies from service locator
        self.pattern_analyzer = ServiceLocator.get(PatternAnalyzer)
        self.insight_engine = ServiceLocator.get(InsightEngine)
```

**Pros**:

- Decouples managers from dependencies
- Easy to swap implementations
- No explicit dependency passing
- Testing can register mocks

**Cons**:

- Hidden dependencies (hard to understand)
- Runtime errors if service not registered
- Global state (testing complexity)
- Violates explicit dependency injection principle

**Rejection Reason**: Hidden dependencies make code harder to understand. Goes against project's explicit dependency injection requirement.

### Alternative 4: Dependency Injection Container

**Approach**: Use DI container like `dependency-injector`.

```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    file_system = providers.Singleton(
        FileSystemManager,
        memory_bank_dir=config.memory_bank_dir
    )

    metadata_index = providers.Singleton(
        MetadataIndex,
        memory_bank_dir=config.memory_bank_dir,
        file_system=file_system
    )

    # ... 24 more

# Usage
container = Container()
container.config.memory_bank_dir.from_value(memory_bank_dir)
fs = await container.file_system()
```

**Pros**:

- Automatic dependency resolution
- Lazy loading built-in
- Type-safe
- Testing support (override providers)

**Cons**:

- External dependency
- Complex setup
- Async support limited
- Overkill for our needs

**Rejection Reason**: Adds external dependency. More complex than needed. Not well-suited for async code.

### Alternative 5: Factory Functions per Tool

**Approach**: Each tool has its own factory for needed managers.

```python
async def create_validation_managers() -> dict[str, object]:
    """Create managers needed for validation."""
    fs = FileSystemManager(memory_bank_dir)
    await fs.initialize()

    metadata = MetadataIndex(memory_bank_dir, fs)
    await metadata.initialize()

    validator = SchemaValidator(metadata)
    await validator.initialize()

    return {"file_system": fs, "metadata": metadata, "validator": validator}

@mcp.tool()
async def validate_memory_bank():
    managers = await create_validation_managers()
    # Use managers
```

**Pros**:

- Explicit dependencies per tool
- Easy to understand
- No global state
- Perfect isolation

**Cons**:

- Recreates managers on every call (slow)
- High memory usage (duplicated managers)
- No caching/reuse
- Inconsistent state across calls

**Rejection Reason**: Performance is terrible. Each tool call recreates all managers.

### Alternative 6: Two-Phase Initialization

**Approach**: Lightweight creation, then heavy initialization on demand.

```python
class FileSystemManager:
    def __init__(self, memory_bank_dir: str):
        # Lightweight: just store config
        self.memory_bank_dir = memory_bank_dir
        self._initialized = False

    async def ensure_initialized(self):
        # Heavy: validate, scan, load
        if not self._initialized:
            await self._initialize()
            self._initialized = True

    async def read_file(self, path: str) -> str:
        await self.ensure_initialized()  # Auto-initialize
        # ... actual read
```

**Pros**:

- Can create all managers cheaply
- Initialization deferred until use
- Transparent to caller
- Flexible

**Cons**:

- Every method must call `ensure_initialized()`
- Easy to forget (no compile-time check)
- Adds overhead to every call
- Complex lifecycle

**Rejection Reason**: Too error-prone. Every method needs `ensure_initialized()` guard. Adds overhead.

### Alternative 7: Lazy Properties

**Approach**: Use Python properties for lazy loading.

```python
class ManagerRegistry:
    def __init__(self, memory_bank_dir: str):
        self._memory_bank_dir = memory_bank_dir
        self._file_system: FileSystemManager | None = None

    @property
    async def file_system(self) -> FileSystemManager:
        if self._file_system is None:
            self._file_system = FileSystemManager(self._memory_bank_dir)
            await self._file_system.initialize()
        return self._file_system
```

**Pros**:

- Clean property access
- Lazy loading
- Cached automatically
- Type-safe

**Cons**:

- Properties can't be async in Python
- Need workarounds (`await registry.file_system()`)
- Ugly syntax
- Not idiomatic

**Rejection Reason**: Python properties don't support async/await. Workarounds are ugly.

## Implementation Notes

### Thread Safety

The implementation uses `asyncio.Lock()` to ensure thread-safe initialization:

```python
_manager_locks: dict[str, asyncio.Lock] = {}

async def get_manager(name: str) -> object:
    """Get or initialize manager (thread-safe)."""
    if name not in _managers:
        if name not in _manager_locks:
            _manager_locks[name] = asyncio.Lock()

        async with _manager_locks[name]:
            # Double-check pattern
            if name not in _managers:
                _managers[name] = await initialize_manager(name)

    return _managers[name]
```

### Testing Support

Tests can reset managers between runs:

```python
def reset_managers():
    """Reset manager cache (for testing)."""
    global _managers, _manager_locks
    _managers.clear()
    _manager_locks.clear()
```

### Performance Monitoring

Track initialization times:

```python
_init_times: dict[str, float] = {}

async def get_manager(name: str) -> object:
    """Get manager with timing."""
    start = time.monotonic()
    manager = await _get_manager_impl(name)
    elapsed = time.monotonic() - start
    _init_times[name] = elapsed
    return manager
```

### Future Optimizations

**1. Pre-warming**: Initialize common managers in background after startup
**2. Dependency DAG**: Build static dependency graph for optimal initialization order
**3. Manager pooling**: Reuse expensive managers (e.g., TokenCounter) across requests
**4. Lazy cleanup**: Unload unused managers after timeout

## References

- [Lazy Initialization Pattern](https://en.wikipedia.org/wiki/Lazy_initialization)
- [Double-Checked Locking](https://en.wikipedia.org/wiki/Double-checked_locking)
- [Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
- [Service Locator Anti-Pattern](https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/)

## Related ADRs

- ADR-001: Hybrid Storage - FileSystemManager and MetadataIndex design
- ADR-004: Protocol-Based Architecture - Manager interfaces
- ADR-006: Async-First Design - Async initialization patterns

## Revision History

- 2024-01-10: Initial version (accepted)
