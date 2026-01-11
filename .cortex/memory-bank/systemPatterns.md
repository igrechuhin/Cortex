# System Patterns: Cortex

## System Architecture

Cortex is structured as an MCP (Model Context Protocol) server with a modular, layered architecture:

- **Layer 1MCP Server** - Entry point with52 across 10 phases
- **Layer 2: Tool Modules** - Phase-specific tool implementations
- **Layer 3nager Initialization** - Centralized lifecycle management with dependency injection
- **Layer 4: Business Logic** -41 modules with single responsibilities
- **Layer5e** - Git-tracked files and metadata indexes

## Key Technical Decisions

- **Protocol-Based Architecture** - PEP 544 structural subtyping for loose coupling
- **Dependency Injection** - All managers receive dependencies via constructor
- **Async Throughout** - All I/O operations use async/await with aiofiles
- **Lazy Initialization** - Managers initialized only when first requested
- **File Locking** - Prevents concurrent write conflicts
- **Version History** - Automatic snapshots for rollback capability

## Design Patterns in Use

- **Dependency Injection** - All external dependencies injected via constructors
- **Protocol-Based Abstractions** - Structural subtyping for testability
- **Manager Pattern** - Centralized service management via ManagerContainer
- **Template Method** - Standardized tool response patterns
- **Strategy Pattern** - Multiple loading strategies (dependency-aware, by-relevance, etc.)
- **Observer Pattern** - File watching for external change detection

## Component Relationships

### Core Services Stack (Initialization Order)
1ileSystemManager → File I/O, locking, hashing
2. MetadataIndex → JSON index for file metadata
3. TokenCounter → tiktoken integration
4dencyGraph → Static and dynamic dependency tracking
5. VersionManager → Snapshots and version history6nkParser → Parse links and transclusions
7. TransclusionEngine → Resolve `{{include:}}` references8. SchemaValidator → File schema validation9QualityMetrics → Calculate quality scores
10 ContextOptimizer → Optimize context within token budgets

### Module Dependencies

- **Phase 1 (Foundation)**: FileSystemManager, MetadataIndex, TokenCounter, DependencyGraph
- **Phase 2 (Linking)**: Depends on Phase 1, adds LinkParser, TransclusionEngine
- **Phase3dation)**: Depends on Phase 1-2, adds SchemaValidator, QualityMetrics
- **Phase 4 (Optimization)**: Depends on Phase 1-3, adds RelevanceScorer, ContextOptimizer
- **Phase 5alysis/Refactoring)**: Depends on Phase 1-4, adds PatternAnalyzer, RefactoringEngine

## Critical Implementation Paths1*File Operations** - All file operations go through FileSystemManager with locking
2t Loading** - Progressive loading with token budget management
3. **Transclusion Resolution** - Recursive resolution with cycle detection
4. **Validation Pipeline** - Schema → Duplication → Quality metrics
5. **Refactoring Execution** - Approval → Validation → Execution → Rollback capability

## Error Handling Patterns

- Domain-specific exceptions with actionable error messages
- File locking prevents concurrent write conflicts
- Version snapshots enable safe rollback
- Metadata index corruption recovery
- Path validation prevents traversal attacks

## Performance Optimizations

- Lazy initialization of managers
- Caching of parsed content and metadata
- Efficient token counting with tiktoken
- Optimized dependency graph algorithms (BFS, DFS, cycle detection)
- Progressive loading to minimize token usage