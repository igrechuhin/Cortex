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
- **Language-Agnostic Script Pattern** - All procedures use scripts from the Synapse scripts directory (path resolved via project structure or Cortex tools) instead of hardcoded commands
- **Semantic Names and Cortex Tools** - Prompts and procedures use semantic names ("plans directory", "memory bank", "Synapse agents directory") and resolve paths via Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`); hardcoding `.cortex/` or `.cursor/` paths is forbidden

## Synapse Architecture (CRITICAL)

Synapse is a git submodule (Synapse directory) providing shared resources with a strict separation of concerns.

### Directory Structure (Semantic Names)

- **Synapse prompts directory** – Language-AGNOSTIC workflow definitions
- **Synapse rules directory** – Coding standards (general + language-specific)
- **Synapse scripts directory** – Language-SPECIFIC implementations (`{language}/` e.g. python/, typescript/)

Resolve actual paths via `get_structure_info()` where available; do not hardcode `.cortex/synapse/` in prompts.

### Prompts: Language-AGNOSTIC (MANDATORY)

All prompts in the Synapse prompts directory MUST be language-agnostic:

- **DO NOT** hardcode language-specific commands (`ruff`, `black`, `prettier`, `eslint`)
- **DO NOT** hardcode structure paths (use semantic names and Cortex tools)
- **DO** use semantic names ("Synapse scripts directory", "plans directory", "memory bank") and Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) to resolve paths and access content

**Correct Pattern**:

- Use Cortex MCP tool `execute_pre_commit_checks(checks=["format"])` (or similar), or reference "Synapse scripts directory" and language-specific script name (path resolved by tool or project structure).

**Wrong Pattern**:

- Hardcoding paths like `.cortex/synapse/scripts/` or commands like `.venv/bin/black --check src/ tests/`

### Scripts: Language-SPECIFIC

Scripts in `scripts/{language}/` contain language-specific implementations:

- Each language has its own directory (`scripts/python/`, `scripts/typescript/`)
- Scripts auto-detect project structure and appropriate tools
- Scripts handle environment differences (.venv, uv, npm, etc.)
- Scripts return proper exit codes and clear output

### Available Python Scripts

| Script | Purpose |
|--------|---------|
| `check_formatting.py` | Verify formatting (black --check) |
| `fix_formatting.py` | Auto-fix formatting (black) |
| `check_linting.py` | Lint checking (ruff check) |
| `check_types.py` | Type checking (pyright) |
| `check_file_sizes.py` | Verify files ≤ 400 lines |
| `check_function_lengths.py` | Verify functions ≤ 30 lines |
| `run_tests.py` | Run tests with coverage |

### Violation Examples to Avoid

- Hardcoding `black`, `ruff`, `pyright`, `prettier`, `eslint` commands in prompts
- Using language-specific paths like `src/`, `tests/` without script abstraction
- Writing procedures that assume Python/TypeScript/etc.
- Including language-specific examples in general procedures

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
