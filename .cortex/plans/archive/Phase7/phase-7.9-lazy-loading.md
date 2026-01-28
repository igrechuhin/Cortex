# Phase 7.9: Lazy Manager Initialization

**Status:** Foundation Complete (Partial Implementation)
**Priority:** Medium
**Estimated Effort:** 3-4 hours (2 hours completed)
**Dependencies:** Phase 7.8 (Async I/O Conversion)

---

## Implementation Summary

### Completed (December 27, 2025)

✅ **Step 1: LazyManager Wrapper (Complete)**

- Created [lazy_manager.py](../src/cortex/lazy_manager.py) with full async support
- Thread-safe with asyncio.Lock for concurrent access
- Implements invalidation for cache clearing
- 100% test coverage (6 tests passing)

✅ **Step 2: Manager Organization (Complete)**

- Created [manager_groups.py](../src/cortex/manager_groups.py)
- Organized managers into 8 groups by priority (1=core, 2=frequent, 3=occasional, 4=rare)
- Ready for gradual lazy loading implementation

✅ **Step 3: Helper Utilities (Complete)**

- Created [manager_utils.py](../src/cortex/manager_utils.py)
- Implements `get_manager()` for type-safe unwrapping of LazyManager instances
- Ready for use in MCP tools

✅ **Testing Infrastructure (Complete)**

- Unit tests for LazyManager: [test_lazy_manager.py](../tests/unit/test_lazy_manager.py)
- 6 comprehensive tests covering initialization, concurrency, invalidation, exceptions
- All 1707 tests passing

✅ **Bug Fixes**

- Fixed pre-existing async/await bug in [test_structure_manager.py:774](../tests/unit/test_structure_manager.py#L774)

### Remaining Work

The following steps are deferred for incremental implementation:

⏳ **Step 4: Refactor get_managers() (Deferred)**

- Full refactoring of [managers/initialization.py](../src/cortex/managers/initialization.py)
- Replace eager initialization with LazyManager wrappers for non-core managers
- Requires careful migration to avoid breaking existing code
- **Recommendation**: Implement incrementally, one manager group at a time

⏳ **Step 5: Update MCP Tools (Deferred)**

- Update ~82 MCP tools in `tools/` directory to use `get_manager()` helper
- Add LazyManager unwrapping logic
- **Recommendation**: Update as-needed when modifying tools, not all at once

⏳ **Step 6: Performance Benchmarks (Deferred)**

- Measure startup time improvements
- Measure memory footprint reduction
- Compare before/after metrics

---

## Overview

Implement lazy initialization for managers to improve startup time and reduce memory footprint. Currently, all managers are initialized eagerly in `get_managers()`, even if they're not immediately needed.

**Goal:** Reduce startup time by 50-70% and memory usage by 30-50% for typical workloads.

---

## Current State

### Eager Initialization in `get_managers()`

**File:** [managers/initialization.py](../src/cortex/managers/initialization.py)

**Current Behavior:**

- All 26+ managers initialized on first call
- Initialization time: ~50ms (acceptable but can be improved)
- Memory footprint: ~15-20MB before any operations
- Managers often not used in a single session

**Manager Categories:**

1. **Always Needed (Core):** ~5 managers
   - FileSystemManager
   - MetadataIndex
   - TokenCounter
   - VersionManager
   - FileWatcher

2. **Frequently Used:** ~8 managers
   - DependencyGraph
   - LinkParser
   - TransclusionEngine
   - LinkValidator
   - SchemaValidator
   - DuplicationDetector
   - QualityMetrics
   - ContextOptimizer

3. **Occasionally Used:** ~8 managers
   - RelevanceScorer
   - ProgressiveLoader
   - SummarizationEngine
   - PatternAnalyzer
   - StructureAnalyzer
   - InsightEngine
   - RulesManager
   - SharedRulesManager

4. **Rarely Used:** ~5 managers
   - RefactoringEngine
   - ConsolidationDetector
   - SplitRecommender
   - ReorganizationPlanner
   - RefactoringExecutor
   - ApprovalManager
   - RollbackManager
   - LearningEngine
   - StructureManager
   - TemplateManager

---

## Implementation Plan

### Step 1: Design Lazy Loading Architecture (1 hour)

#### LazyManager Wrapper

```python
"""Lazy initialization wrapper for managers."""

from typing import Callable, TypeVar, Generic
import asyncio

T = TypeVar('T')

class LazyManager(Generic[T]):
    """Lazy initialization wrapper for managers.

    Delays manager initialization until first access.
    Thread-safe with async locking.
    """

    def __init__(self, factory: Callable[[], T], name: str = ""):
        """
        Initialize lazy manager wrapper.

        Args:
            factory: Async function that creates the manager
            name: Manager name for debugging
        """
        self._factory = factory
        self._name = name
        self._instance: T | None = None
        self._lock = asyncio.Lock()
        self._initializing = False

    async def get(self) -> T:
        """
        Get manager instance, initializing if needed.

        Returns:
            Initialized manager instance
        """
        if self._instance is not None:
            return self._instance

        async with self._lock:
            # Double-check after acquiring lock
            if self._instance is not None:
                return self._instance

            # Initialize
            self._initializing = True
            try:
                self._instance = await self._factory()
                return self._instance
            finally:
                self._initializing = False

    @property
    def is_initialized(self) -> bool:
        """Check if manager has been initialized."""
        return self._instance is not None

    async def invalidate(self) -> None:
        """Invalidate cached instance, forcing re-initialization."""
        async with self._lock:
            self._instance = None
```

#### Manager Groups

```python
"""Manager initialization groups."""

from dataclasses import dataclass
from typing import Callable

@dataclass
class ManagerGroup:
    """Group of related managers that should be initialized together."""

    name: str
    managers: list[str]
    priority: int  # 1=always, 2=frequent, 3=occasional, 4=rare

    def __str__(self) -> str:
        return f"{self.name} ({len(self.managers)} managers, priority {self.priority})"


# Define manager groups
MANAGER_GROUPS = [
    ManagerGroup(
        name="core",
        managers=["file_system", "metadata_index", "token_counter", "version_manager", "file_watcher"],
        priority=1
    ),
    ManagerGroup(
        name="linking",
        managers=["link_parser", "transclusion_engine", "link_validator"],
        priority=2
    ),
    ManagerGroup(
        name="validation",
        managers=["schema_validator", "duplication_detector", "quality_metrics"],
        priority=2
    ),
    ManagerGroup(
        name="optimization",
        managers=["context_optimizer", "relevance_scorer", "progressive_loader", "summarization_engine"],
        priority=2
    ),
    ManagerGroup(
        name="analysis",
        managers=["pattern_analyzer", "structure_analyzer", "insight_engine"],
        priority=3
    ),
    ManagerGroup(
        name="refactoring",
        managers=["refactoring_engine", "consolidation_detector", "split_recommender", "reorganization_planner"],
        priority=3
    ),
    ManagerGroup(
        name="execution",
        managers=["refactoring_executor", "approval_manager", "rollback_manager", "learning_engine"],
        priority=4
    ),
    ManagerGroup(
        name="structure",
        managers=["structure_manager", "template_manager"],
        priority=4
    ),
]
```

### Step 2: Refactor `get_managers()` (1 hour)

**New Structure:**

```python
"""Manager initialization with lazy loading."""

from pathlib import Path
from typing import cast
from ..cache import TTLCache
from ..protocols import *

# Global cache for lazy managers
_manager_cache: dict[str, dict[str, LazyManager]] = {}
_core_managers: dict[str, object] = {}


async def get_managers(base_path: Path) -> dict[str, object]:
    """
    Get manager instances with lazy initialization.

    Core managers (priority 1) are initialized immediately.
    Other managers are wrapped in LazyManager for on-demand initialization.

    Args:
        base_path: Project base path

    Returns:
        Dict of manager names to instances (or LazyManager wrappers)
    """
    project_key = str(base_path)

    # Return cached if available
    if project_key in _manager_cache:
        return await _unwrap_managers(_manager_cache[project_key])

    # Initialize core managers immediately
    core = await _initialize_core_managers(base_path)
    _core_managers[project_key] = core

    # Wrap other managers in LazyManager
    managers: dict[str, LazyManager] = {}

    # Priority 2: Frequent
    managers["link_parser"] = LazyManager(
        lambda: _create_link_parser(core),
        name="link_parser"
    )
    # ... more managers

    # Cache and return
    _manager_cache[project_key] = managers
    return await _unwrap_managers(managers)


async def _initialize_core_managers(base_path: Path) -> dict[str, object]:
    """Initialize core managers that are always needed."""
    from ..file_system import FileSystemManager
    from ..metadata_index import MetadataIndex
    from ..token_counter import TokenCounter
    from ..version_manager import VersionManager
    from ..file_watcher import FileWatcher

    fs = FileSystemManager(base_path)
    metadata = MetadataIndex(base_path / ".memory-bank-index")
    await metadata.load()

    token_counter = TokenCounter()
    version_manager = VersionManager(base_path / ".memory-bank-history")

    file_watcher = FileWatcher(base_path / "memory-bank")
    # ... setup file watcher

    return {
        "file_system": fs,
        "metadata_index": metadata,
        "token_counter": token_counter,
        "version_manager": version_manager,
        "file_watcher": file_watcher,
    }


async def _unwrap_managers(lazy_managers: dict[str, LazyManager]) -> dict[str, object]:
    """
    Convert LazyManager wrappers to actual instances.

    For backward compatibility with existing code.
    """
    result = dict(_core_managers.get(str, {}))

    for name, lazy in lazy_managers.items():
        if lazy.is_initialized:
            result[name] = await lazy.get()
        else:
            # Keep as LazyManager for on-demand initialization
            result[name] = lazy

    return result
```

### Step 3: Update MCP Tools (1 hour)

**Pattern for Tool Updates:**

```python
# Before: Direct manager access
@mcp.tool()
async def my_tool(file_path: str) -> dict[str, object]:
    managers = await get_managers(get_project_root())
    validator = cast(SchemaValidator, managers["schema_validator"])
    result = await validator.validate(file_path)
    return result

# After: Check if lazy and unwrap
@mcp.tool()
async def my_tool(file_path: str) -> dict[str, object]:
    managers = await get_managers(get_project_root())
    validator_or_lazy = managers["schema_validator"]

    # Unwrap if lazy
    if isinstance(validator_or_lazy, LazyManager):
        validator = cast(SchemaValidator, await validator_or_lazy.get())
    else:
        validator = cast(SchemaValidator, validator_or_lazy)

    result = await validator.validate(file_path)
    return result
```

#### Better: Helper Function

```python
async def get_manager(managers: dict[str, object], name: str, type_: type[T]) -> T:
    """
    Get manager from dict, unwrapping LazyManager if needed.

    Args:
        managers: Manager dict from get_managers()
        name: Manager name
        type_: Expected manager type

    Returns:
        Manager instance of specified type
    """
    manager_or_lazy = managers[name]

    if isinstance(manager_or_lazy, LazyManager):
        manager = await manager_or_lazy.get()
    else:
        manager = manager_or_lazy

    return cast(type_, manager)

# Usage in tools
@mcp.tool()
async def my_tool(file_path: str) -> dict[str, object]:
    managers = await get_managers(get_project_root())
    validator = await get_manager(managers, "schema_validator", SchemaValidator)
    result = await validator.validate(file_path)
    return result
```

### Step 4: Testing & Validation (1 hour)

#### Unit Tests for LazyManager

```python
@pytest.mark.asyncio
async def test_lazy_manager_initialization():
    """Test lazy manager initializes on first access."""
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return "initialized"

    lazy = LazyManager(factory, name="test")

    # Not initialized yet
    assert not lazy.is_initialized
    assert call_count == 0

    # First access initializes
    result1 = await lazy.get()
    assert result1 == "initialized"
    assert lazy.is_initialized
    assert call_count == 1

    # Second access reuses instance
    result2 = await lazy.get()
    assert result2 == "initialized"
    assert call_count == 1  # Not called again


@pytest.mark.asyncio
async def test_lazy_manager_concurrent_access():
    """Test lazy manager handles concurrent initialization."""
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        return f"initialized-{call_count}"

    lazy = LazyManager(factory, name="test")

    # Multiple concurrent accesses
    results = await asyncio.gather(
        lazy.get(),
        lazy.get(),
        lazy.get(),
    )

    # Should only initialize once
    assert call_count == 1
    assert all(r == results[0] for r in results)
```

#### Integration Tests

```python
@pytest.mark.asyncio
async def test_get_managers_lazy_initialization():
    """Test get_managers returns lazy managers."""
    managers = await get_managers(Path("/tmp/test"))

    # Core managers should be initialized
    assert not isinstance(managers["file_system"], LazyManager)
    assert not isinstance(managers["metadata_index"], LazyManager)

    # Non-core managers may be lazy
    validator = managers["schema_validator"]
    if isinstance(validator, LazyManager):
        assert not validator.is_initialized
        # Access triggers initialization
        await validator.get()
        assert validator.is_initialized


@pytest.mark.asyncio
async def test_mcp_tools_work_with_lazy_managers():
    """Test MCP tools work with lazy managers."""
    # Test each tool to ensure lazy manager unwrapping works
    # ... tool tests
```

---

## Performance Benchmarks

### Startup Time

**Before:**

```text
Initialization: 50ms
Memory: 20MB
```

**After (Expected):**

```text
Core only: 15ms (70% faster)
Full lazy: 20ms (60% faster)
Memory: 8MB (60% reduction)
```

**Measurement:**

```python
import time
from pathlib import Path

async def benchmark_initialization():
    # Before
    start = time.perf_counter()
    managers_eager = await get_managers_eager(Path("/tmp/test"))
    eager_time = time.perf_counter() - start

    # After
    start = time.perf_counter()
    managers_lazy = await get_managers(Path("/tmp/test"))
    lazy_time = time.perf_counter() - start

    print(f"Eager: {eager_time*1000:.2f}ms")
    print(f"Lazy: {lazy_time*1000:.2f}ms")
    print(f"Improvement: {(1 - lazy_time/eager_time)*100:.1f}%")
```

---

## Risks & Mitigations

### Risk 1: Circular Dependencies

**Risk:** Manager A needs Manager B, but Manager B needs Manager A.

**Mitigation:**

- Review dependency graph before implementation
- Use dependency injection to break cycles
- Document manager dependencies clearly

### Risk 2: Type Checking Complexity

**Risk:** LazyManager wrappers complicate type checking.

**Mitigation:**

- Use helper function `get_manager()` for type-safe unwrapping
- Add type stubs for LazyManager
- Document pattern in contributing guide

### Risk 3: Debugging Difficulty

**Risk:** Lazy initialization makes it harder to debug initialization errors.

**Mitigation:**

- Add logging for manager initialization
- Include manager name in LazyManager
- Clear error messages for initialization failures

---

## Success Criteria

- ✅ Startup time reduced by 50%+ (50ms → 25ms)
- ✅ Memory footprint reduced by 30%+ (20MB → 14MB)
- ✅ All 1,554+ tests still passing
- ✅ No regressions in MCP tool functionality
- ✅ Type checking passes with mypy/pyright
- ✅ Documentation updated

---

## Rollback Plan

If issues arise:

1. Keep eager initialization as fallback
2. Add config flag to disable lazy loading
3. Revert to eager initialization if blocking issues

---

## Expected Outcomes

**Performance Score Impact:**

- Current: 8.5/10 (after Phase 7.8)
- After Phase 7.9: 9.0/10
- Contributing factors:
  - Faster startup
  - Lower memory usage
  - Better resource management

**Benefits:**

- Faster CLI startup
- Reduced memory footprint for simple operations
- More scalable for large projects

---

**Created:** December 26, 2025
**Phase:** 7.9
**Priority:** Medium
**Next Phase:** Phase 7.10 (Code Style Consistency)
