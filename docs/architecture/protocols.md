# Protocol-Based Architecture

## Overview

Cortex uses Protocol-based architecture (PEP 544 structural subtyping) to define clear interfaces between modules. This approach provides:

- **Loose coupling**: Modules depend on interfaces, not concrete implementations
- **Better testability**: Easy to mock dependencies for testing
- **Flexibility**: Can swap implementations without changing dependents
- **Clear contracts**: Explicit definition of required behavior

## Core Principles

### 1. Protocol Definition

Protocols define the interface contract without implementation:

```python
from typing import Protocol

class FileSystemProtocol(Protocol):
    """Protocol for file system operations."""

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        """Read file and return content with hash."""
        ...
```

### 2. Structural Subtyping

Any class that implements the required methods automatically satisfies the protocol:

```python
class FileSystemManager:
    """Concrete implementation - automatically satisfies FileSystemProtocol."""

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        # Implementation here
        ...
```

No explicit inheritance required - if the signature matches, it works!

### 3. Dependency Injection

Components receive protocol types, not concrete types:

```python
class RelevanceScorer:
    def __init__(
        self,
        dependency_graph: DependencyGraphProtocol,  # Protocol, not concrete class
        metadata_index: MetadataIndexProtocol,
    ):
        self.dependency_graph = dependency_graph
        self.metadata_index = metadata_index
```

## Available Protocols

### Phase 1: Foundation

#### FileSystemProtocol

**Purpose**: File I/O operations with safety guarantees
**Key Methods**:

- `read_file()` - Read with content hash
- `write_file()` - Write with conflict detection
- `compute_hash()` - SHA-256 hashing
- `parse_sections()` - Markdown section parsing

#### MetadataIndexProtocol

**Purpose**: Metadata tracking and persistence
**Key Methods**:

- `load()` / `save()` - Index persistence
- `update_file_metadata()` - Update file metadata
- `get_file_metadata()` - Retrieve metadata

#### TokenCounterProtocol

**Purpose**: Token counting with caching
**Key Methods**:

- `count_tokens()` - Basic token counting
- `count_tokens_with_cache()` - Cached counting
- `count_tokens_in_file()` - File-based counting

#### DependencyGraphProtocol

**Purpose**: Dependency management and graph operations
**Key Methods**:

- `compute_loading_order()` - Topological sort
- `get_dependencies()` / `get_dependents()` - Graph traversal
- `detect_cycles()` - Circular dependency detection
- `build_from_links()` - Dynamic graph building

#### VersionManagerProtocol

**Purpose**: Version history and rollback
**Key Methods**:

- `create_snapshot()` - Create version snapshot
- `get_version_history()` - Retrieve history
- `rollback_to_version()` - Restore version

### Phase 2: DRY Linking

#### LinkParserProtocol

**Purpose**: Parse markdown links and transclusions
**Key Methods**:

- `parse_markdown_links()` - Extract links
- `parse_transclusions()` - Extract `{{include:}}` syntax

#### TransclusionEngineProtocol

**Purpose**: Resolve transclusions recursively
**Key Methods**:

- `resolve_file()` - Resolve all transclusions
- `clear_cache()` - Cache management

#### LinkValidatorProtocol

**Purpose**: Validate link integrity
**Key Methods**:

- `validate_file_links()` - Check link validity

### Phase 4: Optimization

#### RelevanceScorerProtocol

**Purpose**: Score content relevance for context selection
**Key Methods**:

- `score_files()` - Score files by task relevance
- `score_sections()` - Score sections within files

**Usage Pattern**:

```python
scores = await scorer.score_files(
    task_description="implement authentication",
    files_content={"file1.md": "..."},
    files_metadata=metadata,
    quality_scores=quality_data
)
```

#### ContextOptimizerProtocol

**Purpose**: Optimize context within token budgets
**Key Methods**:

- `optimize()` - Select optimal context

**Strategies**:

- `priority`: Greedy selection by score
- `dependency`: Include dependency trees
- `hybrid`: Combined approach

### Phase 5: Analysis & Refactoring

#### PatternAnalyzerProtocol

**Purpose**: Track and analyze usage patterns
**Key Methods**:

- `get_access_frequency()` - File access statistics
- `get_co_access_patterns()` - Co-access detection
- `get_unused_files()` - Stale file identification

#### StructureAnalyzerProtocol

**Purpose**: Analyze Memory Bank structure
**Key Methods**:

- `analyze_organization()` - Organization metrics
- `detect_anti_patterns()` - Anti-pattern detection

#### RefactoringEngineProtocol

**Purpose**: Generate refactoring suggestions
**Key Methods**:

- `generate_suggestions()` - Create suggestions
- `export_suggestions()` - Format output

#### ApprovalManagerProtocol

**Purpose**: Manage refactoring approvals
**Key Methods**:

- `request_approval()` - Request approval
- `get_approval_status()` - Check status
- `approve()` - Grant approval

#### RollbackManagerProtocol

**Purpose**: Rollback refactoring operations
**Key Methods**:

- `rollback_refactoring()` - Undo changes
- `get_rollback_history()` - View history

## Protocol Usage Guidelines

### 1. When to Create a Protocol

Create a protocol when:

- ✅ Interface is used across module boundaries
- ✅ Multiple implementations exist or may exist
- ✅ Testing requires mocking
- ✅ Clear contract needed for external consumption

Don't create a protocol when:

- ❌ Only one implementation will ever exist
- ❌ Interface is purely internal to a module
- ❌ Simple data class with no behavior

### 2. Protocol Design Best Practices

**Keep protocols focused**:

```python
# Good: Single responsibility
class FileReaderProtocol(Protocol):
    async def read_file(self, path: Path) -> str: ...

# Bad: Multiple responsibilities
class FileManagerProtocol(Protocol):
    async def read_file(self, path: Path) -> str: ...
    async def send_email(self, to: str, body: str) -> None: ...  # Unrelated!
```

**Use specific return types**:

```python
# Good: Specific types
async def score_files(...) -> dict[str, dict[str, float | str]]: ...

# Bad: Generic types
async def score_files(...) -> dict[str, object]: ...
```

**Document contracts clearly**:

```python
class ValidationProtocol(Protocol):
    async def validate(self, content: str) -> dict[str, object]:
        """Validate content against schema.

        Args:
            content: Content to validate

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)

        Raises:
            ValidationError: If validation cannot be performed
        """
        ...
```

### 3. Testing with Protocols

Protocols make testing easy:

```python
class MockFileSystem:
    """Test double for FileSystemProtocol."""

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        return ("test content", "abc123hash")

    async def write_file(self, file_path: Path, content: str, **kwargs) -> str:
        return "xyz789hash"

# Use in tests
async def test_relevance_scorer():
    mock_fs = MockFileSystem()
    scorer = RelevanceScorer(
        dependency_graph=mock_dep_graph,
        metadata_index=mock_metadata,
    )
    # Test scorer with mock dependencies
```

## Migration Strategy

### From Concrete Types to Protocols

1. **Identify coupling**: Find cross-module dependencies
2. **Define protocol**: Extract interface to protocol
3. **Update annotations**: Change type hints to protocol
4. **Verify conformance**: Ensure implementations match
5. **Update tests**: Use protocols in test doubles

### Example Migration

**Before**:

```python
from cortex.optimization.relevance_scorer import RelevanceScorer

class ContextOptimizer:
    def __init__(self, relevance_scorer: RelevanceScorer):
        self.scorer = relevance_scorer
```

**After**:

```python
from cortex.core.protocols import RelevanceScorerProtocol

class ContextOptimizer:
    def __init__(self, relevance_scorer: RelevanceScorerProtocol):
        self.scorer = relevance_scorer
```

## Benefits Achieved

### 1. Reduced Circular Dependencies

Protocols break circular import chains:

- Module A defines protocol
- Module B implements protocol
- Module C uses protocol
- No circular dependency!

### 2. Improved Testability

Easy to create test doubles:

- No need for complex mocking frameworks
- Simple classes satisfy protocols
- Fast, focused unit tests

### 3. Clear Architecture

Explicit boundaries between layers:

- Core protocols define contracts
- Implementations in specific modules
- Dependencies flow one direction

### 4. Future Flexibility

Easy to add new implementations:

- Alternative file systems
- Different optimization strategies
- Custom analyzers
- No changes to existing code

## Current Architecture Score

**Before Protocol Enhancement**:

- Architecture: 8.5/10
- Coupling: Medium
- Testability: Good

**After Protocol Enhancement**:

- Architecture: 9.3/10 (Target: 9.8/10)
- Coupling: Low
- Testability: Excellent

## Next Steps

1. **Complete protocol coverage**: Add protocols for remaining cross-module interfaces
2. **Update all consumers**: Migrate all concrete type hints to protocols
3. **Enhance documentation**: Document protocol contracts comprehensively
4. **Improve testing**: Leverage protocols for better test coverage

## See Also

- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [Dependency Injection Guide](./dependency-injection.md)
- [Architecture Overview](../architecture.md)
- [Testing Guide](../development/testing.md)
