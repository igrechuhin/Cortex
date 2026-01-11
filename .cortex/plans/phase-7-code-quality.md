# Phase 7: Code Quality Excellence

**Date Created:** December 20, 2025
**Status:** PLANNED
**Goal:** Achieve 9.5/10+ quality scores in ALL categories

---

## Executive Summary

Following a comprehensive code review, this phase addresses all identified issues to achieve excellence-level quality (9.5/10+) in every category. The primary focus is on resolving critical maintainability violations, establishing comprehensive test coverage, and ensuring consistent patterns throughout the codebase.

### Current vs Target Scores

| Category | Current | Target | Gap |
|----------|---------|--------|-----|
| Architecture | 6/10 | 9.5/10 | +3.5 |
| Test Coverage | 3/10 | 9.5/10 | +6.5 |
| Documentation | 5/10 | 9.5/10 | +4.5 |
| Code Style | 7/10 | 9.5/10 | +2.5 |
| Error Handling | 6/10 | 9.5/10 | +3.5 |
| Performance | 6/10 | 9.5/10 | +3.5 |
| Security | 7/10 | 9.5/10 | +2.5 |
| Maintainability | 3/10 | 9.5/10 | +6.5 |
| Rules Compliance | 4/10 | 9.5/10 | +5.5 |
| **Overall** | **5.2/10** | **9.5/10** | **+4.3** |

---

## Phase 7.1: Maintainability (Current: 3/10 → Target: 9.5/10)

### 7.1.1: Split main.py (3880 lines → <400 lines each)

**Priority:** CRITICAL
**Estimated Lines Changed:** ~4000 lines reorganized
**Files to Create:**

```text
src/cortex/
├── main.py                    (~100 lines) - Entry point only
├── server.py                  (~50 lines)  - MCP server instance
├── managers/
│   ├── __init__.py           (~20 lines)
│   └── initialization.py     (~250 lines) - get_managers(), initialization logic
├── tools/
│   ├── __init__.py           (~50 lines)  - Tool registration
│   ├── phase1_foundation.py  (~400 lines) - 10 Phase 1 tools
│   ├── phase2_linking.py     (~200 lines) - 4 Phase 2 tools
│   ├── phase3_validation.py  (~400 lines) - 5 Phase 3 tools
│   ├── phase4_optimization.py (~400 lines) - 7 Phase 4 tools
│   ├── phase5_analysis.py    (~350 lines) - 3 Phase 5.1 tools
│   ├── phase5_refactoring.py (~350 lines) - 4 Phase 5.2 tools
│   ├── phase5_execution.py   (~400 lines) - 6 Phase 5.3-5.4 tools
│   ├── phase6_shared_rules.py (~300 lines) - 4 Phase 6 tools
│   └── legacy.py             (~100 lines) - 3 legacy tools
└── resources/
    └── guides.py             (~50 lines)  - Resource definitions
```

**Implementation Steps:**

1. Create `src/cortex/server.py`:

   ```python
   from mcp.server.fastmcp import FastMCP
   mcp = FastMCP("memory-bank-helper")
   ```

2. Create `src/cortex/managers/initialization.py`:
   - Move `_managers` dict
   - Move `get_project_root()`
   - Move `get_managers()` (refactor into smaller functions)
   - Move `handle_file_change()`

3. Create tool modules (one per phase):
   - Each tool file imports `mcp` from `server.py`
   - Each tool file imports required managers/modules
   - Use `@mcp.tool()` decorator
   - Keep tools under 400 lines per file

4. Update `main.py`:

   ```python
   from cortex.server import mcp
   from cortex.tools import (
       phase1_foundation,
       phase2_linking,
       # ... all tool modules
   )

   def main():
       mcp.run(transport='stdio')

   if __name__ == "__main__":
       main()
   ```

### 7.1.2: Split Oversized Modules

**Files exceeding 400 lines:**

| File | Current Lines | Split Into |
|------|--------------|------------|
| learning_engine.py | 616 | learning_engine.py + learning_data.py |
| rules_manager.py | 596 | rules_manager.py + rules_indexer.py |
| split_recommender.py | 595 | split_recommender.py + split_analyzer.py |
| shared_rules_manager.py | 586 | shared_rules_manager.py + context_detector.py |
| context_optimizer.py | 511 | context_optimizer.py + optimization_strategies.py |
| refactoring_executor.py | ~500 | refactoring_executor.py + execution_validator.py |
| dependency_graph.py | ~500 | dependency_graph.py + graph_algorithms.py |

### 7.1.3: Extract Long Functions (>30 lines) 🚀 IN PROGRESS

**Status:** 3/10+ functions refactored (Initial progress)

**Completed Refactorings:**

1. ✅ **pattern_analyzer.py** - `_normalize_access_log()` (120 lines → 10 lines)
   - Extracted 4 helper functions: `_normalize_accesses()`, `_normalize_file_stats()`, `_normalize_co_access_patterns()`, `_normalize_task_patterns()`
   - All 35 tests passing ✅

2. ✅ **pattern_analyzer.py** - `record_access()` (100 lines → 21 lines)
   - Extracted 3 helper methods: `_update_file_stats()`, `_update_co_access_patterns()`, `_update_task_patterns()`
   - All 35 tests passing ✅

3. ✅ **split_recommender.py** - `_generate_split_points()` (160 lines → 12 lines)
   - Extracted 4 strategy methods: `_generate_split_by_topics()`, `_generate_split_by_sections()`, `_generate_split_by_size()`, `_create_chunk_split_point()`
   - All 43 tests passing ✅

**Remaining Functions to Refactor:**

1. `get_managers()` (193 lines → ~30 lines + helpers):

   ```python
   async def get_managers(project_root: Path) -> Dict[str, Any]:
       root_str = str(project_root)
       if root_str not in _managers:
           _managers[root_str] = await _initialize_all_managers(project_root)
       return _managers[root_str]

   async def _initialize_all_managers(root: Path) -> Dict[str, Any]:
       mgrs = {}
       mgrs.update(await _init_phase1_managers(root))
       mgrs.update(await _init_phase2_managers(root, mgrs))
       mgrs.update(await _init_phase4_managers(root, mgrs))
       mgrs.update(await _init_phase5_managers(root, mgrs))
       mgrs.update(await _init_phase6_managers(root, mgrs))
       await _post_init_setup(root, mgrs)
       return mgrs
   ```

2. All MCP tool functions (extract validation, response building):

   ```python
   # Before
   @mcp.tool()
   async def some_tool(...) -> str:
       try:
           # 100 lines of logic
           return json.dumps({...})
       except Exception as e:
           return json.dumps({"status": "error", ...})

   # After
   @mcp.tool()
   async def some_tool(...) -> str:
       return await _execute_tool(_some_tool_impl, ...)

   async def _some_tool_impl(...) -> dict:
       # 25 lines of core logic
       return {...}
   ```

---

## Phase 7.2: Test Coverage (Current: 3/10 → Target: 9.5/10)

### 7.2.1: Test Infrastructure Setup

**Create test structure:**

```text
tests/
├── conftest.py                    - Shared fixtures
├── fixtures/
│   ├── memory_bank/              - Sample memory bank files
│   ├── rules/                    - Sample rule files
│   └── shared_rules/             - Sample shared rules
├── unit/
│   ├── test_file_system.py
│   ├── test_metadata_index.py
│   ├── test_token_counter.py
│   ├── test_dependency_graph.py
│   ├── test_version_manager.py
│   ├── test_migration.py
│   ├── test_file_watcher.py
│   ├── test_link_parser.py
│   ├── test_transclusion_engine.py
│   ├── test_link_validator.py
│   ├── test_schema_validator.py
│   ├── test_duplication_detector.py
│   ├── test_quality_metrics.py
│   ├── test_validation_config.py
│   ├── test_relevance_scorer.py
│   ├── test_context_optimizer.py
│   ├── test_progressive_loader.py
│   ├── test_summarization_engine.py
│   ├── test_optimization_config.py
│   ├── test_rules_manager.py
│   ├── test_pattern_analyzer.py
│   ├── test_structure_analyzer.py
│   ├── test_insight_engine.py
│   ├── test_refactoring_engine.py
│   ├── test_consolidation_detector.py
│   ├── test_split_recommender.py
│   ├── test_reorganization_planner.py
│   ├── test_refactoring_executor.py
│   ├── test_approval_manager.py
│   ├── test_rollback_manager.py
│   ├── test_learning_engine.py
│   ├── test_adaptation_config.py
│   └── test_shared_rules_manager.py
├── integration/
│   ├── test_phase1_workflow.py
│   ├── test_phase2_workflow.py
│   ├── test_phase3_workflow.py
│   ├── test_phase4_workflow.py
│   ├── test_phase5_workflow.py
│   └── test_phase6_workflow.py
└── tools/
    ├── test_phase1_tools.py
    ├── test_phase2_tools.py
    ├── test_phase3_tools.py
    ├── test_phase4_tools.py
    ├── test_phase5_tools.py
    └── test_phase6_tools.py
```

### 7.2.2: Core Test Fixtures (conftest.py)

```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_project_root():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "memory-bank").mkdir()
        yield root

@pytest.fixture
def sample_memory_bank(temp_project_root):
    """Create sample memory bank with all 7 files."""
    # Create all template files
    ...

@pytest.fixture
def mock_file_system():
    """Mock FileSystemManager for unit tests."""
    ...

@pytest.fixture
def mock_metadata_index():
    """Mock MetadataIndex for unit tests."""
    ...
```

### 7.2.3: Unit Test Requirements

**Each module must have:**

- Test class following naming: `Test{ModuleName}`
- Tests for all public methods
- Tests for edge cases
- Tests for error conditions
- AAA pattern (Arrange-Act-Assert)
- Descriptive names: `test_{behavior}_when_{condition}`

**Example test structure:**

```python
class TestFileSystemManager:
    """Tests for FileSystemManager."""

    def test_validate_path_returns_true_for_valid_path(self, temp_project_root):
        # Arrange
        fs = FileSystemManager(temp_project_root)
        valid_path = temp_project_root / "memory-bank" / "test.md"

        # Act
        result = fs.validate_path(valid_path)

        # Assert
        assert result is True

    def test_validate_path_returns_false_for_path_traversal(self, temp_project_root):
        # Arrange
        fs = FileSystemManager(temp_project_root)
        malicious_path = temp_project_root / ".." / "etc" / "passwd"

        # Act
        result = fs.validate_path(malicious_path)

        # Assert
        assert result is False

    async def test_read_file_raises_error_when_file_not_found(self, temp_project_root):
        # Arrange
        fs = FileSystemManager(temp_project_root)
        nonexistent = temp_project_root / "memory-bank" / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            await fs.read_file(nonexistent)
```

### 7.2.4: Coverage Goals

| Module Category | Target Coverage |
|-----------------|-----------------|
| Core modules (Phase 1) | 95%+ |
| Linking modules (Phase 2) | 95%+ |
| Validation modules (Phase 3) | 95%+ |
| Optimization modules (Phase 4) | 90%+ |
| Analysis modules (Phase 5.1) | 90%+ |
| Refactoring modules (Phase 5.2) | 90%+ |
| Execution modules (Phase 5.3-5.4) | 90%+ |
| Shared rules (Phase 6) | 90%+ |
| MCP Tools | 85%+ |
| **Overall** | **90%+** |

---

## Phase 7.3: Error Handling (Current: 6/10 → Target: 9.5/10)

### 7.3.1: Replace Silent Exception Handlers

**14 locations to fix:**

```python
# BEFORE (bad pattern)
except Exception:
    pass

# AFTER (proper handling)
except Exception as e:
    logger.warning(f"Operation failed: {e}", exc_info=True)
    # Or return error response if appropriate
```

**Files requiring changes:**

1. `main.py` (lines 296, 307, 357):

   ```python
   # Line 296-298 - metadata index load
   except Exception as e:
       logger.info(f"Metadata index load failed, will rebuild: {e}")

   # Line 307-309 - rules initialization
   except Exception as e:
       logger.warning(f"Rules initialization failed: {e}")

   # Line 357-359 - file change handler
   except Exception as e:
       logger.debug(f"File change handling failed: {e}")
   ```

2. `split_recommender.py` (lines 122, 212, 237)
3. `quality_metrics.py` (lines 262, 287)
4. `schema_validator.py` (line 232)
5. `dependency_graph.py` (line 419)
6. `shared_rules_manager.py` (lines 239, 418)
7. `consolidation_detector.py` (lines 113, 147)

### 7.3.2: Add Logging Infrastructure

**Create `src/cortex/logging_config.py`:**

```python
import logging
import sys

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging for Cortex."""
    logger = logging.getLogger("cortex")
    logger.setLevel(getattr(logging, level.upper()))

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(handler)

    return logger

logger = setup_logging()
```

### 7.3.3: Standardize Error Responses

**Create `src/cortex/responses.py`:**

```python
import json
from typing import Optional, Any

def success_response(data: dict) -> str:
    """Create standardized success response."""
    return json.dumps({"status": "success", **data}, indent=2)

def error_response(
    error: Exception,
    action_required: Optional[str] = None,
    context: Optional[dict] = None
) -> str:
    """Create standardized error response."""
    response = {
        "status": "error",
        "error": str(error),
        "error_type": type(error).__name__
    }
    if action_required:
        response["action_required"] = action_required
    if context:
        response["context"] = context
    return json.dumps(response, indent=2)
```

### 7.3.4: Add Domain-Specific Exceptions

**Enhance `exceptions.py`:**

```python
class RulesError(MemoryBankError):
    """Base exception for rules-related errors."""
    pass

class RulesIndexingError(RulesError):
    """Raised when rule indexing fails."""
    def __init__(self, folder: str, reason: str):
        self.folder = folder
        self.reason = reason
        super().__init__(f"Failed to index rules from {folder}: {reason}")

class SharedRulesError(RulesError):
    """Raised when shared rules operation fails."""
    pass

class RefactoringError(MemoryBankError):
    """Base exception for refactoring errors."""
    pass

class RefactoringValidationError(RefactoringError):
    """Raised when refactoring validation fails."""
    pass

class RollbackError(MemoryBankError):
    """Raised when rollback operation fails."""
    pass

class LearningError(MemoryBankError):
    """Raised when learning engine encounters an error."""
    pass
```

---

## Phase 7.4: Architecture (Current: 6/10 → Target: 9.5/10)

### 7.4.1: Define Protocol/Interface Abstractions

**Create `src/cortex/protocols.py`:**

```python
from typing import Protocol, Dict, List, Any, Optional
from pathlib import Path

class FileSystemProtocol(Protocol):
    """Protocol for file system operations."""

    async def read_file(self, path: Path) -> tuple[str, str]: ...
    async def write_file(self, path: Path, content: str, expected_hash: Optional[str] = None) -> str: ...
    def validate_path(self, path: Path) -> bool: ...
    def compute_hash(self, content: str) -> str: ...
    def parse_sections(self, content: str) -> List[Dict]: ...

class MetadataIndexProtocol(Protocol):
    """Protocol for metadata index operations."""

    async def load(self) -> None: ...
    async def save(self) -> None: ...
    async def get_file_metadata(self, file_name: str) -> Optional[Dict]: ...
    async def update_file_metadata(self, **kwargs) -> None: ...

class TokenCounterProtocol(Protocol):
    """Protocol for token counting."""

    def count_tokens(self, text: str) -> int: ...

class DependencyGraphProtocol(Protocol):
    """Protocol for dependency graph operations."""

    def add_file(self, name: str, priority: int, dependencies: List[str]) -> None: ...
    def get_loading_order(self) -> List[str]: ...
    def detect_cycles(self) -> List[List[str]]: ...
```

### 7.4.2: Introduce Dependency Injection Container

**Create `src/cortex/container.py`:**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ManagerContainer:
    """Container for all manager instances."""

    # Phase 1
    file_system: FileSystemProtocol
    metadata_index: MetadataIndexProtocol
    token_counter: TokenCounterProtocol
    dependency_graph: DependencyGraphProtocol
    version_manager: Any
    migration_manager: Any
    file_watcher: Any

    # Phase 2
    link_parser: Any
    transclusion_engine: Any
    link_validator: Any

    # ... etc for all phases

    @classmethod
    async def create(cls, project_root: Path) -> "ManagerContainer":
        """Factory method to create fully initialized container."""
        # Initialize all managers in proper order
        ...
```

### 7.4.3: Reduce Circular Dependencies

**Refactor circular imports:**

1. Move shared types to `types.py`
2. Use `TYPE_CHECKING` for type hints only
3. Use protocols instead of concrete imports
4. Lazy imports where necessary

---

## Phase 7.5: Code Style (Current: 7/10 → Target: 9.5/10)

### 7.5.1: Enforce Consistent Formatting

**Update `pyproject.toml`:**

```toml
[tool.black]
line-length = 88
target-version = ['py310']

[tool.isort]
profile = "black"
line_length = 88

[tool.ruff]
line-length = 88
select = ["E", "F", "W", "I", "N", "D", "UP", "B", "C4", "SIM"]
```

### 7.5.2: Run Formatters on All Files

```bash
# Format all Python files
black src/cortex/
isort src/cortex/

# Verify with ruff
ruff check src/cortex/
```

### 7.5.3: Standardize Patterns

**Dict key access:**

```python
# Always use .get() with defaults for optional keys
value = data.get("key", default_value)

# Use [] only when key is guaranteed to exist
value = required_data["key"]
```

**String quotes:**

```python
# Use double quotes for strings (Black default)
message = "This is a message"
```

**Import organization:**

```python
# stdlib
import json
from pathlib import Path

# third-party
from mcp.server.fastmcp import FastMCP

# local
from .file_system import FileSystemManager
```

---

## Phase 7.6: Documentation (Current: 5/10 → Target: 9.5/10)

### 7.6.1: API Documentation

**Create `docs/` directory:**

```text
docs/
├── index.md                 - Overview
├── getting-started.md       - Quick start guide
├── architecture.md          - System architecture
├── api/
│   ├── tools.md            - MCP tools reference
│   ├── modules.md          - Module documentation
│   └── exceptions.md       - Exception reference
├── guides/
│   ├── configuration.md    - Configuration guide
│   ├── migration.md        - Migration guide
│   └── troubleshooting.md  - Common issues
└── development/
    ├── contributing.md     - Contributing guide
    ├── testing.md          - Testing guide
    └── releasing.md        - Release process
```

### 7.6.2: Docstring Standards

**All public functions must have:**

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """Short description of what the function does.

    Longer description if needed, explaining behavior,
    edge cases, and important details.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ExceptionType: When this exception is raised.

    Example:
        >>> result = function_name(value1, value2)
        >>> print(result)
    """
```

### 7.6.3: Type Hints Completion

**Ensure all functions have complete type hints:**

```python
# Before (incomplete)
def process_data(data, options=None):
    ...

# After (complete)
def process_data(
    data: Dict[str, Any],
    options: Optional[ProcessOptions] = None
) -> ProcessResult:
    ...
```

---

## Phase 7.7: Performance (Current: 6/10 → Target: 9.5/10)

### 7.7.1: Fix O(n²) Algorithms

**Duplication detection optimization:**

```python
# Before: O(n²) pairwise comparison
for i, file1 in enumerate(files):
    for j, file2 in enumerate(files):
        if i < j:
            compare(file1, file2)

# After: Use hash-based grouping
content_hashes = {}
for file in files:
    hash_key = compute_content_signature(file)
    content_hashes.setdefault(hash_key, []).append(file)

# Only compare within same hash groups
for similar_files in content_hashes.values():
    if len(similar_files) > 1:
        compare_group(similar_files)
```

### 7.7.2: Consistent Async I/O

**Replace all sync file operations:**

```python
# Before (sync)
with open(self.learning_file, 'r') as f:
    data = json.load(f)

# After (async)
async with aiofiles.open(self.learning_file, 'r') as f:
    content = await f.read()
    data = json.loads(content)
```

### 7.7.3: Add Caching Layer

**Create `src/cortex/cache.py`:**

```python
from functools import lru_cache
from typing import Dict, Any, Optional
import time

class TTLCache:
    """Time-based cache with configurable TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: Dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time(), value)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
```

### 7.7.4: Optimize Manager Initialization

**Lazy initialization pattern:**

```python
class LazyManager:
    """Lazy initialization wrapper for managers."""

    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    async def get(self):
        if self._instance is None:
            self._instance = await self._factory()
        return self._instance
```

---

## Phase 7.8: Security (Current: 7/10 → Target: 9.5/10)

### 7.8.1: Input Validation

**Add comprehensive input validation:**

```python
def validate_file_name(name: str) -> str:
    """Validate and sanitize file name.

    Raises:
        ValueError: If file name is invalid.
    """
    if not name:
        raise ValueError("File name cannot be empty")

    # Check for path traversal
    if ".." in name or name.startswith("/"):
        raise ValueError(f"Invalid file name: {name}")

    # Check for invalid characters
    invalid_chars = set('<>:"|?*\0')
    if any(c in name for c in invalid_chars):
        raise ValueError(f"File name contains invalid characters: {name}")

    # Normalize the name
    return name.strip()
```

### 7.8.2: JSON File Integrity

**Add integrity checks for JSON files:**

```python
import hashlib

async def save_json_with_integrity(path: Path, data: dict) -> None:
    """Save JSON with integrity hash."""
    content = json.dumps(data, indent=2)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    wrapper = {
        "_integrity": content_hash,
        "_version": "1.0",
        "data": data
    }

    async with aiofiles.open(path, 'w') as f:
        await f.write(json.dumps(wrapper, indent=2))

async def load_json_with_integrity(path: Path) -> dict:
    """Load JSON and verify integrity."""
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()

    wrapper = json.loads(content)

    if "_integrity" in wrapper:
        data_content = json.dumps(wrapper["data"], indent=2)
        expected_hash = hashlib.sha256(data_content.encode()).hexdigest()

        if wrapper["_integrity"] != expected_hash:
            raise IndexCorruptedError("Integrity check failed")

        return wrapper["data"]

    return wrapper  # Legacy format
```

### 7.8.3: Rate Limiting

**Add rate limiting for file operations:**

```python
import asyncio
from collections import deque
import time

class RateLimiter:
    """Simple rate limiter for file operations."""

    def __init__(self, max_ops: int = 100, window_seconds: float = 1.0):
        self.max_ops = max_ops
        self.window = window_seconds
        self.operations: deque = deque()

    async def acquire(self) -> None:
        now = time.time()

        # Remove old operations outside window
        while self.operations and now - self.operations[0] > self.window:
            self.operations.popleft()

        # Wait if at limit
        if len(self.operations) >= self.max_ops:
            wait_time = self.operations[0] + self.window - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.operations.append(now)
```

---

## Phase 7.9: Rules Compliance (Current: 4/10 → Target: 9.5/10)

### 7.9.1: File Size Enforcement

**Add pre-commit hook:**

```python
#!/usr/bin/env python3
"""Pre-commit hook to enforce file size limits."""

import sys
from pathlib import Path

MAX_LINES = 400
SRC_DIR = Path("src/cortex")

def count_lines(path: Path) -> int:
    """Count non-blank, non-comment lines."""
    with open(path) as f:
        lines = f.readlines()

    count = 0
    in_docstring = False

    for line in lines:
        stripped = line.strip()

        # Track docstrings
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue

        if in_docstring:
            continue

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        count += 1

    return count

def main():
    violations = []

    for py_file in SRC_DIR.glob("**/*.py"):
        lines = count_lines(py_file)
        if lines > MAX_LINES:
            violations.append((py_file, lines))

    if violations:
        print("File size violations detected:")
        for path, lines in violations:
            print(f"  {path}: {lines} lines (max: {MAX_LINES})")
        sys.exit(1)

    print("All files within size limits.")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### 7.9.2: Function Length Enforcement

**Add to pre-commit:**

```python
import ast

MAX_FUNCTION_LINES = 30

def check_function_length(path: Path) -> list:
    """Check all functions in file for length violations."""
    with open(path) as f:
        tree = ast.parse(f.read())

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno
            if length > MAX_FUNCTION_LINES:
                violations.append((node.name, length, node.lineno))

    return violations
```

### 7.9.3: CI/CD Integration

**Create `.github/workflows/quality.yml`:**

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install black isort ruff pytest pytest-cov

      - name: Check formatting (Black)
        run: black --check src/

      - name: Check imports (isort)
        run: isort --check src/

      - name: Lint (Ruff)
        run: ruff check src/

      - name: Check file sizes
        run: python scripts/check_file_sizes.py

      - name: Check function lengths
        run: python scripts/check_function_lengths.py

      - name: Run tests
        run: pytest tests/ -v --cov=src/ --cov-report=xml

      - name: Check coverage
        run: |
          coverage report --fail-under=90
```

---

## Implementation Order

### Sprint 1: Critical Maintainability (7.1)

**Duration:** 2-3 days
**Priority:** CRITICAL

1. Create new directory structure
2. Split main.py into tool modules
3. Refactor get_managers() function
4. Split oversized modules
5. Verify all imports work

### Sprint 2: Error Handling (7.3)

**Duration:** 1 day
**Priority:** HIGH

1. Add logging infrastructure
2. Replace all silent exception handlers
3. Add domain-specific exceptions
4. Standardize error responses

### Sprint 3: Test Infrastructure (7.2 part 1)

**Duration:** 2 days
**Priority:** HIGH

1. Create test directory structure
2. Add conftest.py with fixtures
3. Write tests for Phase 1 modules
4. Write tests for Phase 2 modules

### Sprint 4: Test Coverage (7.2 part 2)

**Duration:** 2 days
**Priority:** HIGH

1. Write tests for Phase 3-4 modules
2. Write tests for Phase 5 modules
3. Write tests for Phase 6 modules
4. Write MCP tool tests

### Sprint 5: Code Style & Documentation (7.5, 7.6)

**Duration:** 1-2 days
**Priority:** MEDIUM

1. Run formatters on all files
2. Complete docstrings
3. Add type hints
4. Create API documentation

### Sprint 6: Architecture & Performance (7.4, 7.7)

**Duration:** 1-2 days
**Priority:** MEDIUM

1. Add protocol definitions
2. Fix O(n²) algorithms
3. Add caching layer
4. Make all I/O async

### Sprint 7: Security & Rules Compliance (7.8, 7.9)

**Duration:** 1 day
**Priority:** MEDIUM

1. Add input validation
2. Add JSON integrity checks
3. Create pre-commit hooks
4. Set up CI/CD

---

## Success Criteria

### Maintainability: 9.5/10

- [ ] No file exceeds 400 lines
- [ ] No function exceeds 30 lines
- [ ] main.py is <100 lines
- [ ] Clear module organization

### Test Coverage: 9.5/10

- [ ] 90%+ overall coverage
- [ ] All modules have unit tests
- [ ] Integration tests for all phases
- [ ] AAA pattern followed

### Error Handling: 9.5/10

- [ ] Zero silent exception handlers
- [ ] Logging infrastructure in place
- [ ] Standardized error responses
- [ ] Domain-specific exceptions

### Architecture: 9.5/10

- [ ] Protocol abstractions defined
- [ ] Clear dependency injection
- [ ] No circular imports
- [ ] Clean module boundaries

### Code Style: 9.5/10

- [ ] Black/isort compliance
- [ ] Consistent patterns
- [ ] Complete type hints
- [ ] Organized imports

### Documentation: 9.5/10

- [ ] Complete docstrings
- [ ] API documentation
- [ ] Architecture docs
- [ ] Examples provided

### Performance: 9.5/10

- [ ] No O(n²) algorithms
- [ ] All I/O is async
- [ ] Caching implemented
- [ ] Lazy initialization

### Security: 9.5/10

- [ ] Input validation
- [ ] JSON integrity checks
- [ ] Rate limiting
- [ ] Path sanitization

### Rules Compliance: 9.5/10

- [ ] Pre-commit hooks active
- [ ] CI/CD enforces rules
- [ ] Zero violations
- [ ] Automated checks

---

## Estimated Total Effort

| Sprint | Duration | Focus |
|--------|----------|-------|
| Sprint 1 | 2-3 days | Maintainability |
| Sprint 2 | 1 day | Error Handling |
| Sprint 3 | 2 days | Test Infrastructure |
| Sprint 4 | 2 days | Test Coverage |
| Sprint 5 | 1-2 days | Style & Docs |
| Sprint 6 | 1-2 days | Architecture & Performance |
| Sprint 7 | 1 day | Security & Compliance |
| **Total** | **10-13 days** | **Full Excellence** |

---

## Verification Checklist

After implementation, verify:

```bash
# Run all checks
black --check src/
isort --check src/
ruff check src/
python scripts/check_file_sizes.py
python scripts/check_function_lengths.py
pytest tests/ -v --cov=src/ --cov-report=term-missing --cov-fail-under=90
```

Expected output: All checks pass, 90%+ coverage, zero violations.

---

## End of Phase 7 Plan
