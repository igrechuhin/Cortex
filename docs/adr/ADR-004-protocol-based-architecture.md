# ADR-004: Protocol-Based Architecture

## Status

Accepted

## Context

Cortex consists of 26 managers that need to interact with each other. The challenge is defining these interactions in a way that is:

1. **Flexible**: Easy to swap implementations
2. **Testable**: Easy to mock dependencies
3. **Type-Safe**: Catch errors at type-check time
4. **Maintainable**: Clear contracts between components
5. **Evolvable**: Can add features without breaking existing code

### The Interface Problem

Traditional approaches to defining component interactions:

**Abstract Base Classes (ABC)**:

```python
from abc import ABC, abstractmethod

class FileSystemManagerInterface(ABC):
    @abstractmethod
    async def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        pass
```

**Duck Typing**:

```python
# No interface, just assume methods exist
class RefactoringEngine:
    def __init__(self, file_system):
        self.file_system = file_system  # Hope it has read_file!

    async def analyze(self):
        content = await self.file_system.read_file("file.md")
```

**Concrete Classes**:

```python
class RefactoringEngine:
    def __init__(self, file_system: FileSystemManager):
        self.file_system = file_system  # Tightly coupled
```

### Requirements

**Type Safety**:

- Catch missing methods at type-check time (Pyright, mypy)
- Detect incorrect method signatures early
- Support IDE autocomplete and refactoring
- No runtime surprises from missing attributes

**Testability**:

- Easy to create test doubles (mocks, stubs, fakes)
- No need for complex mocking frameworks
- Minimal boilerplate for test setup
- Clear expectations in tests

**Flexibility**:

- Easy to swap implementations (prod vs test)
- Support multiple implementations of same interface
- Allow gradual migration to new implementations
- Enable dependency inversion

**Python Best Practices**:

- Leverage Python 3.13+ type system features
- Follow PEP 544 (Structural Subtyping)
- Avoid unnecessary inheritance
- Minimize boilerplate

### Problem Space

**Challenge 1: Manager Dependencies**

Many managers depend on other managers:

```
RefactoringEngine
    ↓ depends on
PatternAnalyzer
    ↓ depends on
MetadataIndex
    ↓ depends on
FileSystemManager
```

Without clear interfaces:

- Type hints use concrete classes (tight coupling)
- Testing requires real implementations
- Circular dependencies possible
- Hard to reason about dependencies

**Challenge 2: Testing Complexity**

With concrete class dependencies:

```python
# Hard to test - requires full dependency tree
async def test_refactoring_engine():
    fs = FileSystemManager("/tmp/test")
    await fs.initialize()

    metadata = MetadataIndex("/tmp/test", fs)
    await metadata.initialize()

    analyzer = PatternAnalyzer(metadata)
    await analyzer.initialize()

    engine = RefactoringEngine(analyzer)
    await engine.initialize()

    # Finally can test!
    result = await engine.analyze()
```

**Challenge 3: Implementation Flexibility**

Want to support different implementations:

- **Production**: Full-featured FileSystemManager
- **Testing**: In-memory fake
- **Mock**: Simple test stub
- **Cloud**: S3-backed storage

Without interfaces, must modify all dependent code.

**Challenge 4: Type System Evolution**

Python's type system has evolved:

- Python 3.5: Type hints added (PEP 484)
- Python 3.8: Protocol support (PEP 544)
- Python 3.10: Union syntax `|`
- Python 3.13: Improved Protocol support

Modern Python enables better patterns than older code.

### Analysis: ABC vs Protocol

**Abstract Base Classes** (Python 3.4+):

```python
from abc import ABC, abstractmethod

class FileSystemInterface(ABC):
    @abstractmethod
    async def read_file(self, path: str) -> str:
        pass

class FileSystemManager(FileSystemInterface):
    async def read_file(self, path: str) -> str:
        # Implementation
```

**Pros**:

- Explicit inheritance
- Runtime enforcement
- Clear intent
- IDE support

**Cons**:

- Requires inheritance (nominal typing)
- Can't use existing classes without modification
- Tight coupling to interface
- More boilerplate

**Protocols** (PEP 544, Python 3.8+):

```python
from typing import Protocol

class FileSystemProtocol(Protocol):
    async def read_file(self, path: str) -> str: ...

class FileSystemManager:
    async def read_file(self, path: str) -> str:
        # Implementation
        # No inheritance needed!
```

**Pros**:

- Structural typing (like Go interfaces)
- No inheritance required
- Works with existing classes
- More flexible
- Type checker support

**Cons**:

- No runtime enforcement (unless `@runtime_checkable`)
- Less explicit
- Newer feature (Python 3.8+)
- Less familiar to some developers

### Use Case Analysis

**Use Case 1: Testing with Fakes**

Want to test RefactoringEngine without real file system:

```python
class FakeFileSystem:
    """In-memory fake for testing."""
    def __init__(self):
        self.files = {}

    async def read_file(self, path: str) -> str:
        return self.files.get(path, "")

    async def write_file(self, path: str, content: str) -> None:
        self.files[path] = content

# Works with Protocol, not with ABC
engine = RefactoringEngine(FakeFileSystem())
```

**Use Case 2: Multiple Implementations**

Want to support different storage backends:

```python
# Local file system
class LocalFileSystem:
    async def read_file(self, path: str) -> str: ...

# Cloud storage
class S3FileSystem:
    async def read_file(self, path: str) -> str: ...

# Both satisfy FileSystemProtocol automatically
```

**Use Case 3: Gradual Migration**

Want to add new methods without breaking existing code:

```python
# Old protocol
class FileSystemProtocol(Protocol):
    async def read_file(self, path: str) -> str: ...

# New protocol extends old
class ExtendedFileSystemProtocol(FileSystemProtocol, Protocol):
    async def read_file(self, path: str) -> str: ...
    async def list_files(self, dir: str) -> list[str]: ...  # New!

# Old implementations still work with old protocol
```

## Decision

We will use **Python Protocols (PEP 544)** for all manager interfaces.

### Protocol Design

**Core Principles**:

1. Define protocols in separate files from implementations
2. Use `typing.Protocol` for structural typing
3. Mark runtime-checkable protocols with `@runtime_checkable` decorator
4. Keep protocols focused (ISP: Interface Segregation Principle)
5. Use composition over inheritance

**Protocol Location**:

- Core protocols: `src/cortex/core/protocols.py`
- Manager-specific protocols: Near the manager implementation
- Test protocols: In test files

### Protocol Examples

**FileSystemProtocol** (`src/cortex/core/protocols.py`):

```python
from typing import Protocol

class FileSystemProtocol(Protocol):
    """Protocol for file system operations."""

    async def read_file(self, path: str) -> str:
        """Read file contents."""
        ...

    async def write_file(
        self,
        path: str,
        content: str
    ) -> None:
        """Write content to file."""
        ...

    async def list_files(self, directory: str) -> list[str]:
        """List files in directory."""
        ...

    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        ...

    async def get_file_hash(self, path: str) -> str:
        """Calculate file hash."""
        ...
```

**MetadataProtocol**:

```python
class MetadataProtocol(Protocol):
    """Protocol for metadata operations."""

    async def get_metadata(self, path: str) -> dict[str, object]:
        """Get file metadata."""
        ...

    async def update_metadata(
        self,
        path: str,
        metadata: dict[str, object]
    ) -> None:
        """Update file metadata."""
        ...

    async def list_all_files(self) -> list[str]:
        """List all tracked files."""
        ...
```

**ValidationProtocol**:

```python
class ValidationProtocol(Protocol):
    """Protocol for validation operations."""

    async def validate_file(self, path: str) -> list[ValidationError]:
        """Validate single file."""
        ...

    async def validate_all(self) -> dict[str, list[ValidationError]]:
        """Validate all files."""
        ...
```

### Usage Patterns

**Manager Implementation**:

```python
# FileSystemManager automatically satisfies protocol
class FileSystemManager:
    """Manages file system operations."""

    def __init__(self, memory_bank_dir: str):
        self.memory_bank_dir = memory_bank_dir

    async def read_file(self, path: str) -> str:
        """Read file contents."""
        # Implementation
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Write content to file."""
        # Implementation
        ...

    # ... other methods match FileSystemProtocol
```

**Dependency Injection with Protocols**:

```python
class RefactoringEngine:
    """Engine for refactoring suggestions."""

    def __init__(
        self,
        file_system: FileSystemProtocol,
        metadata: MetadataProtocol,
        pattern_analyzer: PatternAnalyzerProtocol
    ):
        self.file_system = file_system
        self.metadata = metadata
        self.pattern_analyzer = pattern_analyzer

    async def analyze(self) -> list[RefactoringSuggestion]:
        """Analyze files for refactoring opportunities."""
        files = await self.metadata.list_all_files()
        # Type checker knows file_system has read_file method
        contents = await asyncio.gather(*[
            self.file_system.read_file(f) for f in files
        ])
        # ...
```

**Test Doubles**:

```python
class FakeFileSystem:
    """In-memory fake for testing."""

    def __init__(self):
        self.files: dict[str, str] = {}

    async def read_file(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def write_file(self, path: str, content: str) -> None:
        self.files[path] = content

    # ... implement other protocol methods

# Use in tests - no inheritance needed!
async def test_refactoring_engine():
    fs = FakeFileSystem()
    fs.files["test.md"] = "# Test content"

    metadata = FakeMetadata()
    analyzer = FakePatternAnalyzer()

    engine = RefactoringEngine(fs, metadata, analyzer)
    result = await engine.analyze()

    assert len(result) > 0
```

### Protocol Hierarchy

**Simple Protocols** (single responsibility):

- `FileSystemProtocol`: Basic file operations
- `MetadataProtocol`: Metadata operations
- `ValidationProtocol`: Validation operations

**Composite Protocols** (multiple capabilities):

```python
class FullFileSystemProtocol(
    FileSystemProtocol,
    MetadataProtocol,
    Protocol
):
    """Combined file system + metadata operations."""
    pass
```

**Runtime Checkable Protocols** (for isinstance checks):

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class FileSystemProtocol(Protocol):
    """Protocol with runtime type checking."""

    async def read_file(self, path: str) -> str: ...

# Can use isinstance()
if isinstance(obj, FileSystemProtocol):
    content = await obj.read_file("file.md")
```

### Type Checking Integration

**Pyright Configuration** (`pyrightconfig.json`):

```json
{
  "typeCheckingMode": "strict",
  "pythonVersion": "3.13",
  "strictParameterNoneValue": true,
  "reportMissingProtocol": "error",
  "reportIncompatibleMethodOverride": "error"
}
```

**IDE Support**:

- VSCode/Cursor: Full Protocol support with Pylance
- PyCharm: Protocol support since 2021.2
- Vim/Neovim: Via Pyright LSP

## Consequences

### Positive

**1. Flexibility**:

- Easy to swap implementations (prod, test, mock)
- No inheritance required
- Can use third-party classes if they match protocol
- Structural typing enables gradual migration

**2. Testability**:

- Simple test doubles (no mocking framework needed)
- Minimal boilerplate in tests
- Fast test execution (no real dependencies)
- Clear test expectations

**3. Type Safety**:

- Type checker validates protocol conformance
- Catch missing methods at check time
- IDE autocomplete works
- Refactoring tools understand dependencies

**4. Maintainability**:

- Clear contracts between components
- Loose coupling
- Easy to understand dependencies
- Self-documenting interfaces

**5. Python Best Practices**:

- Leverages modern Python features (PEP 544)
- Idiomatic structural typing
- No unnecessary inheritance
- Minimal boilerplate

**6. Evolution**:

- Can extend protocols without breaking existing code
- New methods added gradually
- Backwards compatibility easier
- Incremental adoption

### Negative

**1. Learning Curve**:

- Protocols are newer feature (unfamiliar to some)
- Structural typing differs from nominal typing
- Less explicit than ABC inheritance
- Requires understanding of type system

**2. Runtime Behavior**:

- No automatic runtime enforcement (unless `@runtime_checkable`)
- Duck typing can lead to runtime errors
- Must be careful with dynamic usage
- Testing becomes more important

**3. Discoverability**:

- Harder to find all implementations of protocol
- No explicit "implements" relationship
- IDE navigation less precise
- Documentation must be explicit

**4. Debugging**:

- Type errors can be cryptic
- Protocol violations found at check time, not runtime
- Stack traces don't show protocol layer
- Must understand type checker output

**5. Tool Support**:

- Requires modern type checker (Pyright, mypy 0.9+)
- Some tools don't understand protocols
- Documentation generation may be limited
- CI must run type checker

**6. Over-Engineering Risk**:

- Easy to create too many protocols
- Can lead to interface explosion
- Need discipline to keep protocols focused
- Balance between flexibility and simplicity

### Neutral

**1. Protocol Granularity**:

- Must decide protocol size (fine vs coarse-grained)
- Trade-off: flexibility vs simplicity
- Context-dependent decision
- Requires design judgment

**2. Runtime Checks**:

- `@runtime_checkable` adds overhead
- Only use when isinstance checks needed
- Most protocols don't need runtime checking
- Type checker is primary validation

**3. Protocol Evolution**:

- Adding methods is non-breaking (structural typing)
- Removing methods breaks compatibility
- Renaming methods breaks compatibility
- Version protocols if breaking changes needed

## Alternatives Considered

### Alternative 1: Abstract Base Classes

**Approach**: Use ABC for all interfaces.

```python
from abc import ABC, abstractmethod

class FileSystemInterface(ABC):
    @abstractmethod
    async def read_file(self, path: str) -> str:
        pass

class FileSystemManager(FileSystemInterface):
    async def read_file(self, path: str) -> str:
        # Implementation
```

**Pros**:

- Explicit inheritance
- Runtime enforcement
- Familiar pattern
- Clear "implements" relationship

**Cons**:

- Requires inheritance (tight coupling)
- Can't use existing classes without modification
- More boilerplate
- Less flexible for testing

**Rejection Reason**: Protocols provide better flexibility and testability without inheritance overhead. ABC is overly restrictive.

### Alternative 2: Duck Typing (No Interfaces)

**Approach**: No interfaces, just assume methods exist.

```python
class RefactoringEngine:
    def __init__(self, file_system):
        self.file_system = file_system  # Any object

    async def analyze(self):
        content = await self.file_system.read_file("file.md")
```

**Pros**:

- Maximum flexibility
- No boilerplate
- Truly Pythonic
- No inheritance needed

**Cons**:

- No type safety
- Runtime errors
- No IDE support
- Hard to understand dependencies

**Rejection Reason**: Fails requirement for type safety. Runtime errors unacceptable. Project requires 100% type hint coverage.

### Alternative 3: Concrete Class Dependencies

**Approach**: Use concrete classes in type hints.

```python
class RefactoringEngine:
    def __init__(self, file_system: FileSystemManager):
        self.file_system = file_system
```

**Pros**:

- Simple
- Type safe
- Clear dependencies
- IDE support

**Cons**:

- Tight coupling
- Hard to test (need real implementations)
- No flexibility
- Dependency inversion violated

**Rejection Reason**: Makes testing difficult. Tight coupling to concrete implementations. Violates dependency inversion principle.

### Alternative 4: TypedDict for Configuration

**Approach**: Use TypedDict for capabilities.

```python
from typing import TypedDict, Callable, Awaitable

class FileSystemCapabilities(TypedDict):
    read_file: Callable[[str], Awaitable[str]]
    write_file: Callable[[str, str], Awaitable[None]]

class RefactoringEngine:
    def __init__(self, file_system: FileSystemCapabilities):
        self.file_system = file_system
```

**Pros**:

- Type safe
- Flexible
- No inheritance

**Cons**:

- Awkward syntax
- No method binding
- Loss of context (no `self`)
- Not idiomatic

**Rejection Reason**: TypedDict not designed for this use case. Protocols are the right tool.

### Alternative 5: Mixin Classes

**Approach**: Use multiple inheritance with mixins.

```python
class FileSystemMixin:
    async def read_file(self, path: str) -> str:
        raise NotImplementedError

class MetadataMixin:
    async def get_metadata(self, path: str) -> dict[str, object]:
        raise NotImplementedError

class FileSystemManager(FileSystemMixin, MetadataMixin):
    async def read_file(self, path: str) -> str:
        # Implementation
```

**Pros**:

- Composable
- Multiple capabilities
- Type safe

**Cons**:

- Complex inheritance hierarchy
- Diamond problem possible
- MRO (Method Resolution Order) confusion
- Not Pythonic for interfaces

**Rejection Reason**: Inheritance used for code reuse, not interfaces. Protocols are cleaner for interfaces.

### Alternative 6: Zope Interfaces

**Approach**: Use Zope's interface library.

```python
from zope.interface import Interface, implementer

class IFileSystem(Interface):
    async def read_file(path):
        """Read file contents."""

@implementer(IFileSystem)
class FileSystemManager:
    async def read_file(self, path: str) -> str:
        # Implementation
```

**Pros**:

- Mature library
- Runtime verification
- Explicit contracts
- Adapter support

**Cons**:

- External dependency
- Not type checker compatible
- Not Pythonic
- Overly complex for needs

**Rejection Reason**: External dependency. Not compatible with type checkers. Python Protocols are standard library solution.

### Alternative 7: Go-style Interfaces (Manual)

**Approach**: Manually check structural compatibility.

```python
def requires_file_system(obj):
    """Verify obj has file system methods."""
    assert hasattr(obj, "read_file")
    assert hasattr(obj, "write_file")
    # ...

class RefactoringEngine:
    def __init__(self, file_system):
        requires_file_system(file_system)
        self.file_system = file_system
```

**Pros**:

- Explicit verification
- No inheritance
- Flexible

**Cons**:

- Runtime overhead
- Manual checking tedious
- No type checker support
- Easy to forget checks

**Rejection Reason**: Runtime checks inefficient. Type checker should catch errors. Protocols provide compile-time checking.

## Implementation Notes

### Protocol Design Guidelines

**1. Single Responsibility**:

- Each protocol should have one clear purpose
- Avoid "god protocols" with many methods
- Compose protocols when needed

**2. Minimal Interface**:

- Include only essential methods
- Don't anticipate future needs
- Can extend later if needed

**3. Async-First**:

- All I/O methods should be async
- Use `async def` in protocol definition
- Support concurrent operations

**4. Type Hints**:

- Full type hints required (100% coverage)
- Use specific types (`list[str]`, not `list`)
- Never use `Any` (use `object` if truly unknown)

**5. Documentation**:

- Document each protocol method
- Explain preconditions and postconditions
- Include usage examples

### Testing Patterns

**Fake Implementations**:

```python
class FakeFileSystem:
    """In-memory fake for testing."""

    def __init__(self):
        self.files: dict[str, str] = {}
        self.read_count: dict[str, int] = {}

    async def read_file(self, path: str) -> str:
        self.read_count[path] = self.read_count.get(path, 0) + 1
        return self.files.get(path, "")

    async def write_file(self, path: str, content: str) -> None:
        self.files[path] = content
```

**Protocol Conformance Tests**:

```python
async def test_file_system_protocol():
    """Verify FileSystemManager conforms to protocol."""
    manager = FileSystemManager("/tmp/test")

    # Type checker verifies this
    fs: FileSystemProtocol = manager

    # Runtime check if needed
    assert isinstance(manager, FileSystemProtocol)

    # Verify methods exist and work
    await fs.write_file("test.md", "content")
    content = await fs.read_file("test.md")
    assert content == "content"
```

### Migration Strategy

**Phase 1**: Define core protocols
**Phase 2**: Update type hints to use protocols
**Phase 3**: Create test fakes using protocols
**Phase 4**: Run type checker to verify conformance
**Phase 5**: Add runtime checks where needed

### Type Checker Configuration

Enable strict protocol checking:

```json
{
  "reportMissingProtocol": "error",
  "reportIncompatibleMethodOverride": "error",
  "reportIncompatibleVariableOverride": "error"
}
```

## References

- [PEP 544: Protocols (Structural Subtyping)](https://peps.python.org/pep-0544/)
- [Typing Documentation: Protocols](https://docs.python.org/3/library/typing.html#typing.Protocol)
- [Pyright Protocol Support](https://github.com/microsoft/pyright/blob/main/docs/protocols.md)
- [Go Interfaces](https://go.dev/tour/methods/9) - Inspiration for structural typing
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID) - Interface Segregation Principle

## Related ADRs

- ADR-003: Lazy Manager Initialization - How protocols enable flexible initialization
- ADR-006: Async-First Design - Async protocols
- ADR-008: Security Model - Security protocol contracts

## Revision History

- 2024-01-10: Initial version (accepted)
