# Contributing Guide

Welcome to the Cortex project! This guide will help you get started with contributing to our codebase. We appreciate your interest in improving this project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Coding Standards](#coding-standards)
5. [Type Hints](#type-hints)
6. [Code Constraints](#code-constraints)
7. [Error Handling](#error-handling)
8. [Testing Requirements](#testing-requirements)
9. [Pull Request Process](#pull-request-process)
10. [Code Review](#code-review)
11. [Common Pitfalls](#common-pitfalls)
12. [Getting Help](#getting-help)

## Getting Started

### Prerequisites

- Python 3.13+ (required for Python 3.13+ built-in features)
- Git
- macOS, Linux, or Windows with WSL2

### Fork and Clone

1. **Fork the repository** on GitHub
   - Click the "Fork" button in the top-right corner
   - This creates a copy under your GitHub account

2. **Clone your fork locally**

   ```bash
   git clone https://github.com/YOUR_USERNAME/cortex.git
   cd cortex
   ```

3. **Add upstream remote**

   ```bash
   git remote add upstream https://github.com/igrechuhin/cortex.git
   ```

4. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix-name
   ```

### Branch Naming Conventions

Follow these patterns for branch names:

- **Features**: `feature/description` (e.g., `feature/add-validation-rules`)
- **Bug fixes**: `fix/description` (e.g., `fix/memory-bank-validation`)
- **Documentation**: `docs/description` (e.g., `docs/update-setup-guide`)
- **Refactoring**: `refactor/description` (e.g., `refactor/optimize-token-counter`)
- **Tests**: `test/description` (e.g., `test/add-coverage-for-validator`)

## Development Setup

### Install Dependencies

The project uses `uv` for dependency management. If you don't have `uv` installed:

```bash
# Install uv (recommended approach)
pip install uv

# Or on macOS with Homebrew
brew install uv
```

### Set Up Development Environment

```bash
# Install dependencies and dev tools (creates .venv with Python 3.13.x)
bash scripts/bootstrap.sh
# Or: make bootstrap

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Bootstrap installs Python dependencies via `uv`. For offline or restricted environments, see [Getting Started — Offline or restricted environments](../getting-started.md#offline-or-restricted-environments).

> **Node.js**: The only Node.js dependency is `cspell` for spelling checks, which CI installs
> on-demand via `npm install -g cspell@8.6.1`. No `npm install` step is required locally.

### Python Version Management

If you have multiple Python versions installed:

```bash
# Check Python version
python --version

# Use specific Python version with uv
uv sync --python 3.13 --dev
```

### Configure IDE

Configure your IDE to use the correct Python interpreter:

- **Path**: `.venv/bin/python` (or `.venv\Scripts\python.exe` on Windows)
- **Cursor/VS Code**: Open `.venv/bin/python` in the Python interpreter selection dialog
- **Type checking**: Enable Pyright with strict mode

### Type checking strategy

- **Primary type checker**: Pyright (strict mode), used in CI via the `Code Quality` workflow and expected for local runs.
- **Recommended local command**:

  ```bash
  uv run pyright src/ tests/
  ```

- **Mypy**: A strict mypy configuration remains in `pyproject.toml` for optional local cross-checking, but Pyright is the **source of truth** for the quality gate and contributor expectations.

### Runtime dependency declarations

Runtime dependencies are listed in both `pyproject.toml` (`[project.dependencies]`) and the repo-root `requirements.txt` (for environments that install from that file). The **Code Quality** workflow runs `scripts/check_dep_parity.py` so these two sources cannot drift. Before pushing, you can run the same check locally:

```bash
make check-dep-parity
```

## Project Structure

### Directory Layout

```text
cortex/
├── src/cortex/          # Main package source
│   ├── __init__.py
│   ├── __main__.py               # Entry point
│   ├── main.py                   # Server initialization
│   ├── server.py                 # MCP server
│   ├── managers/                 # Manager modules
│   ├── templates/                # Template generators
│   ├── guides/                   # User guides
│   └── [other modules].py        # Individual feature modules
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── conftest.py              # Shared test configuration
├── docs/                         # Documentation
│   ├── development/              # Developer documentation
│   └── [other docs].md
├── .cursor/                      # Cursor IDE configuration
│   ├── memory-bank/              # Memory bank files
│   └── rules/                    # Coding rules
├── pyproject.toml               # Project configuration
├── README.md                    # Project overview
├── CLAUDE.md                    # Claude Code instructions
└── uv.lock                      # Dependency lock file
```

### Module Organization

**Key Principles:**

- **Flat structure**: Keep package structure reasonably flat
- **One public type per file**: Each file should expose one main public class/function
- **Clear naming**: Module names should describe their responsibility
- **Size limits**: Production files must stay within **400 logical lines** per file (see [Code Constraints](#code-constraints) and [Architecture guardrails](#architecture-guardrails)); raw `wc -l` can be much higher when docstrings dominate

### Core Modules

- **`server.py`**: MCP server instance and tool registration
- **`file_system.py`**: File I/O operations with async support
- **`metadata_index.py`**: Metadata indexing and corruption recovery
- **`token_counter.py`**: Token counting via tiktoken
- **`transclusion_engine.py`**: DRY linking with `{{include:}}` resolution
- **`validation_engine.py`**: Schema validation and quality metrics
- **`refactoring_engine.py`**: Pattern analysis and refactoring suggestions

See [CLAUDE.md](../../CLAUDE.md) for the complete services initialization order.

## Coding Standards

### Format Code (Mandatory)

Before every commit, format your code:

```bash
# Format with Black (88-char line length)
black .

# Sort imports with isort
isort .

# Both at once
black . && isort .
```

**Important**: Black and isort are MANDATORY. Never manually adjust formatted code.

### Python 3.13+ Features (Mandatory)

This project targets Python 3.13+ and requires using modern built-in features:

#### Python 3.13+ Type Hints

```python
# ✅ CORRECT - Use Python 3.13+ built-ins
from typing import Self

def process_items(items: list[str]) -> dict[str, int]:
    """Process items and return counts."""
    return {item: len(item) for item in items}

def copy_with(self, **changes) -> Self:
    """Create a copy with modified fields."""
    return replace(self, **changes)
```

```python
# ❌ PROHIBITED - Don't use typing module equivalents
from typing import List, Dict, Optional

def process_items(items: List[str]) -> Dict[str, int]:  # BLOCKED
    """Process items and return counts."""
    pass

# ❌ PROHIBITED - Don't use Optional or Union
def get_value(key: str) -> Optional[str]:  # Use str | None instead
    pass
```

#### Async Operations

```python
# ✅ CORRECT - Use asyncio.timeout()
import asyncio

async def fetch_data(url: str) -> dict:
    """Fetch data with timeout."""
    async with asyncio.timeout(5.0):  # Use asyncio.timeout()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.json()

async def process_items_concurrently(items: list[str]) -> list[str]:
    """Process items concurrently."""
    async with asyncio.TaskGroup() as tg:  # Use TaskGroup
        tasks = [tg.create_task(process_item(item)) for item in items]
    return [task.result() for task in tasks]
```

```python
# ❌ PROHIBITED - Don't use asyncio.wait_for()
import asyncio

async def fetch_data(url: str) -> dict:
    # BLOCKED: Use asyncio.timeout() instead
    response = await asyncio.wait_for(fetch_url(url), timeout=5.0)
    return response
```

#### Other Python 3.13+ Features

```python
# ✅ Use itertools.batched() for chunking
from itertools import batched

for batch in batched(items, batch_size=10):
    process_batch(batch)

# ✅ Use contextlib.chdir() for temporary directory changes
from contextlib import chdir

with chdir(some_directory):
    # Operations in some_directory
    pass

# ✅ Use @cache for unbounded caching
from functools import cache

@cache
def expensive_computation(x: int) -> int:
    return x ** 2

# ✅ Use except* for ExceptionGroup handling
try:
    process_data()
except* ValidationError as eg:
    for exc in eg.exceptions:
        logger.error(f"Validation error: {exc}")
except* DatabaseError as eg:
    for exc in eg.exceptions:
        logger.error(f"Database error: {exc}")
```

### Import Organization

Organize imports in this order with blank lines between groups:

```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import aiofiles
from watchdog import Observer

# Local imports
from .file_system import FileSystemManager
from .metadata_index import MetadataIndex
```

## Type Hints

### 100% Coverage (Mandatory)

All functions, methods, and classes MUST have complete type hints. This is enforced by Pyright in strict mode.

```python
# ✅ CORRECT - Full type hints
async def validate_file(
    file_path: Path,
    schema: dict[str, object],
) -> tuple[bool, list[str]]:
    """Validate file against schema.

    Args:
        file_path: Path to file to validate
        schema: Validation schema

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors: list[str] = []

    if not file_path.exists():
        errors.append(f"File not found: {file_path}")

    return len(errors) == 0, errors
```

```python
# ❌ PROHIBITED - Missing type hints
def validate_file(file_path, schema):  # BLOCKED: No type hints
    """Validate file against schema."""
    pass

# ❌ PROHIBITED - Using Any type
def process_data(data: Any) -> Any:  # BLOCKED: Use concrete types
    """Process data."""
    pass
```

### Concrete Types (Mandatory)

Use concrete types instead of `object` whenever possible. Investigate actual types and use them.

```python
# ✅ CORRECT - Concrete types
def format_context(context: dict[str, str | None]) -> str:
    """Format context with specific type."""
    return json.dumps(context)

def get_suggestions(
    pattern: str,
    limit: int = 10,
) -> list[RefactoringSuggestion]:
    """Get refactoring suggestions with concrete return type."""
    suggestions: list[RefactoringSuggestion] = []
    # ... implementation
    return suggestions
```

```python
# ❌ PROHIBITED - Using object when concrete types available
def format_context(context: dict[str, object]) -> str:  # BLOCKED
    """Format context. Use dict[str, str | None] instead."""
    pass

def get_suggestions(...) -> object:  # BLOCKED: Use list[RefactoringSuggestion]
    """Get suggestions."""
    pass
```

### Type Specificity

Make types MORE specific, not less:

```python
# ✅ CORRECT - Specific types
def build_response(
    status: str,
    data: dict[str, str],
    metadata: dict[str, int] | None = None,
) -> dict[str, str | int | None]:
    """Build response with specific types."""
    response: dict[str, str | int | None] = {"status": status}
    response.update(data)
    if metadata:
        response.update(metadata)
    return response
```

```python
# ❌ PROHIBITED - Overly generic types
def build_response(
    status: str,
    data: dict[str, object],  # BLOCKED: Too generic
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:  # BLOCKED: Too generic
    """Build response."""
    pass
```

## Code Constraints

### File and function size limits (logical lines)

CI, pre-commit, and `make check` enforce **logical** line counts for Python under `src/`, not editor or `wc -l` **total** lines. A line counts toward the limit only when it is treated as code by the check scripts: **blank lines, full-line comments, and docstring lines are excluded**. Details: `.cortex/synapse/scripts/python/check_file_sizes.py` and `check_function_lengths.py`.

| Check | Limit | Source of truth |
| ----- | ----- | ---------------- |
| Per-file | **400** logical lines | `MAX_FILE_LINES` in [`src/cortex/core/constants.py`](../../src/cortex/core/constants.py) |
| Per-function | **30** logical lines | `MAX_FUNCTION_LINES` in the same module |

**Exclusions (must match CI):**

- **File size**: files named `models.py` (`FILE_SIZE_EXCLUDED_FILENAMES`) — Pydantic schema-heavy modules.
- **Function length**: paths listed in `FUNCTION_LENGTH_EXCLUDED_PATHS` (e.g. selected plan/roadmap dispatchers, `sequential_thinking.py`, `pre_commit_pipeline.py`).

**Check locally (same logic as GitHub Actions):**

```bash
uv run python .cortex/synapse/scripts/python/check_file_sizes.py
uv run python .cortex/synapse/scripts/python/check_function_lengths.py
```

**Why a file can look “huge” but still pass:** Heavy docstrings and comments do not count. Split or refactor when **logical** lines approach the cap, not only when totals cross 400.

> **Note:** Exceeding **logical** limits fails CI and will result in rejection in code review.

### Architecture guardrails

These limits exist to keep modules testable, reviewable, and aligned with **single responsibility**: separate I/O, validation, orchestration, and rendering where it helps readers and tests. The numbers above are the policy; the checks in CI are the enforcement.

**Exemptions (changing or adding them):**

- **Built-in lists** live in [`src/cortex/core/constants.py`](../../src/cortex/core/constants.py) (`FILE_SIZE_EXCLUDED_FILENAMES`, `FUNCTION_LENGTH_EXCLUDED_PATHS`). They must stay in sync with the Synapse scripts and the Code Quality workflow.
- **Prefer decomposition** (split by responsibility, preserve public APIs via re-exports) before expanding an exclusion list.
- **If you must add or widen an exemption**, do it in a dedicated pull request that updates `constants.py`, states why decomposition is not feasible yet or why the path is an intentional long-lived dispatcher, and points to a tracking issue or roadmap item when the exception is meant to be temporary.

**Quarterly review (cadence):**

- At least once per quarter, treat `FILE_SIZE_EXCLUDED_FILENAMES` and `FUNCTION_LENGTH_EXCLUDED_PATHS` as a **review backlog**: confirm each entry is still justified, identify candidates to remove after refactors, and align large files with the decomposition direction in [Project Structure — Module Organization](#module-organization).
- No separate calendar automation is required; this can coincide with roadmap or quality-gate maintenance work, as long as the exclusion lists and worst offenders are revisited on that schedule.

### Function size: examples (30 logical lines)

All functions MUST NOT exceed 30 logical lines unless the file is on `FUNCTION_LENGTH_EXCLUDED_PATHS`.

```python
# ✅ CORRECT - Concise function
def calculate_score(file: MemoryBankFile) -> float:
    """Calculate quality score for file.

    Args:
        file: Memory bank file to score

    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.0

    if file.has_valid_structure():
        score += 0.3

    if file.is_complete():
        score += 0.4

    if file.follows_standards():
        score += 0.3

    return min(score, 1.0)
```

```python
# ❌ PROHIBITED - Too many lines
def calculate_score(file):  # BLOCKED: >30 lines
    """Calculate quality score for file."""
    score = 0.0

    if file.has_valid_structure():
        score += 0.3

    if file.is_complete():
        score += 0.4

    if file.follows_standards():
        score += 0.3

    # ... many more lines ...

    return min(score, 1.0)
```

If you have a function exceeding 30 lines:

1. **Extract helper functions**: Break logic into smaller functions
2. **Use classes**: For complex stateful operations
3. **Refactor loops**: Consider list comprehensions or generators

### One Public Type Per File

Each file should expose ONE main public class or function:

```python
# ✅ CORRECT - One public type per file
# src/cortex/quality_scorer.py

class QualityScorer:
    """Score memory bank file quality."""

    def score(self, file: MemoryBankFile) -> QualityScore:
        """Calculate quality score."""
        # Implementation
        pass

# Private helpers inside the file
def _calculate_base_score(file: MemoryBankFile) -> float:
    """Private helper function."""
    pass
```

```python
# ❌ PROHIBITED - Multiple public types
# BLOCKED: Both classes exposed from one file
class QualityScorer:
    """Score quality."""
    pass

class DuplicationDetector:  # BLOCKED: Separate file needed
    """Detect duplications."""
    pass
```

### Dependency Injection (Mandatory)

All external dependencies MUST be injected via initializers:

```python
# ✅ CORRECT - Dependency injection
class MemoryBankValidator:
    """Validate memory bank files."""

    def __init__(
        self,
        schema_validator: SchemaValidator,
        duplication_detector: DuplicationDetector,
    ):
        """Initialize with injected dependencies."""
        self.schema_validator = schema_validator
        self.duplication_detector = duplication_detector
```

```python
# ❌ PROHIBITED - Global state or instantiation
import global_validator  # BLOCKED: No globals

class MemoryBankValidator:
    def __init__(self):
        self.validator = global_validator  # BLOCKED
        self.detector = DuplicationDetector()  # BLOCKED: Direct instantiation
```

## Error Handling

### Use Domain-Specific Exceptions

Create custom exception classes for your domain:

```python
# ✅ CORRECT - Domain-specific exceptions
class ValidationError(ValueError):
    """Raised when validation fails."""
    pass

class FileAccessError(IOError):
    """Raised when file access fails."""
    pass

class TransclusionError(Exception):
    """Raised when transclusion resolution fails."""
    pass

# Use them appropriately
def validate_schema(data: dict) -> None:
    """Validate data against schema."""
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
```

### Never Use Bare Except (Mandatory)

Always specify exception types:

```python
# ✅ CORRECT - Specific exception handling
try:
    process_file(file_path)
except FileNotFoundError as e:
    logger.error(f"File not found: {file_path}")
    raise ValidationError(f"File not found: {file_path}") from e
except IOError as e:
    logger.error(f"IO error: {e}")
    raise FileAccessError(f"Failed to access file: {file_path}") from e
```

```python
# ❌ PROHIBITED - Bare except
try:
    process_file(file_path)
except:  # BLOCKED: No exception type specified
    pass
```

### Log Before Raising

Log errors before re-raising or handling:

```python
# ✅ CORRECT - Log and raise
def validate_input(data: dict) -> None:
    """Validate input data."""
    try:
        if not data.get('name'):
            raise ValidationError("Name is required")
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        raise ValidationError(f"Missing field: {e}") from e
```

## Testing Requirements

### 90% Minimum Coverage

All new code MUST have at least 90% test coverage. Aim for 100%.

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Check coverage percentage
coverage report --fail-under=90
```

### Test Organization

Organize tests in a logical structure:

```text
tests/
├── unit/                           # Fast, isolated unit tests
│   ├── test_file_system.py
│   ├── test_validation_engine.py
│   └── test_token_counter.py
├── integration/                    # Slower, realistic tests
│   ├── test_memory_bank_workflow.py
│   └── test_transclusion_system.py
├── conftest.py                     # Shared fixtures
└── fixtures/                       # Test data files
    └── sample_memory_bank.json
```

### AAA Pattern (Mandatory)

All tests MUST follow Arrange-Act-Assert pattern:

```python
# ✅ CORRECT - Clear AAA pattern
def test_validate_memory_bank_when_valid_structure():
    """Test validation passes with valid structure."""
    # Arrange - Set up test data
    validator = MemoryBankValidator()
    valid_file = create_sample_memory_bank()

    # Act - Execute code under test
    result = validator.validate(valid_file)

    # Assert - Verify expected outcome
    assert result.is_valid is True
    assert len(result.errors) == 0
```

```python
# ❌ PROHIBITED - Unclear structure
def test_validate_memory_bank():  # BLOCKED: Vague name
    validator = MemoryBankValidator()
    valid_file = create_sample_memory_bank()
    result = validator.validate(valid_file)  # No clear AAA
    assert result  # Weak assertion
```

### Test Naming

Use descriptive names following this pattern:

```python
def test_<functionality>_when_<condition>():
    """Test description."""
    pass

# Examples:
def test_validate_memory_bank_when_valid_structure():
    pass

def test_validate_memory_bank_when_invalid_structure():
    pass

def test_calculate_score_when_file_is_empty():
    pass
```

### No Test Skipping (Mandatory)

Do not skip tests without explicit justification:

```python
# ✅ CORRECT - Fix or address flaky tests
def test_async_file_operation():
    """Test async file operations."""
    # Fix the underlying issue, don't skip
    pass

# ❌ PROHIBITED - Blanket skipping
@pytest.mark.skip  # BLOCKED: Why is this skipped?
def test_async_file_operation():
    pass

# If you must temporarily skip:
@pytest.mark.skip(
    reason="Issue #123 - Timeout on CI, investigating with team"
)
def test_async_file_operation():
    pass
```

### Async Tests

Use `pytest-asyncio` for async tests:

```python
# ✅ CORRECT - Async test
@pytest.mark.asyncio
async def test_load_file_async():
    """Test async file loading."""
    manager = FileSystemManager()
    content = await manager.load_file(Path("test.md"))
    assert content is not None
```

### Mock External Dependencies

Mock filesystem, network, and external services:

```python
# ✅ CORRECT - Mock external dependencies
def test_validate_with_mocked_schema_validator(mock_validator):
    """Test validation with mocked dependencies."""
    # Arrange
    mock_validator.validate.return_value = (True, [])
    validator = MemoryBankValidator(mock_validator)

    # Act
    result = validator.validate(test_data)

    # Assert
    assert result.is_valid is True
    mock_validator.validate.assert_called_once()
```

## Pull Request Process

### Before Creating a PR

1. **Ensure code is formatted**

   ```bash
   black .
   isort .
   ```

2. **Run all tests**

   ```bash
   pytest tests/ -v
   ```

3. **Check test coverage**

   ```bash
   pytest --cov=src --cov-report=term-missing --cov-fail-under=90
   ```

4. **Check file and function size limits**

   Use the same scripts as CI (logical lines, not `wc -l`):

   ```bash
   uv run python .cortex/synapse/scripts/python/check_file_sizes.py
   uv run python .cortex/synapse/scripts/python/check_function_lengths.py
   ```

5. **Verify type hints**
   - Run Pyright with strict mode
   - Fix all type errors

6. **Telemetry and usage caches**
   - If the diff touches `.cortex/synapse/.cache/usage/events/`, `.cortex/.session/context-usage-statistics.json`, or other aggregate telemetry JSON, confirm the change is intentional (shared analytics rollup, not accidental local noise). See [Tool usage tracking](../architecture/tool-usage-tracking.md).

### Create a Pull Request

1. **Push your branch**

   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create PR on GitHub**
   - Use a clear, descriptive title
   - Reference any related issues (#123)
   - Describe changes and rationale

3. **PR Title Format**

   ```text
   [Type] Description of changes

   # Types: feat, fix, docs, refactor, test, chore
   feat: Add validation for memory bank files
   fix: Resolve transclusion resolution bug
   docs: Update contributing guide
   ```

4. **PR Description Template**

   ```markdown
   ## Description

   Brief description of changes

   ## Related Issues

   Closes #123

   ## Type of Change

   - [ ] New feature
   - [ ] Bug fix
   - [ ] Documentation update
   - [ ] Refactoring

   ## Changes Made

   - Point 1
   - Point 2
   - Point 3

   ## Testing

   - Unit tests added/updated
   - Integration tests added/updated
   - Manual testing performed

   ## Checklist

   - [ ] Code is formatted (black, isort)
   - [ ] Tests pass (pytest)
   - [ ] Coverage >= 90%
   - [ ] Type hints complete (Pyright)
   - [ ] No test skips without justification
   - [ ] Documentation updated
   ```

### CI Requirements

All of these MUST pass:

- ✅ Code formatting (Black, isort)
- ✅ Type checking (Pyright strict mode)
- ✅ All tests pass
- ✅ Coverage >= 90%
- ✅ No security violations (Bandit)
- ✅ No dependency vulnerabilities

If any check fails, the PR will be automatically rejected.

## Code Review

### What Reviewers Look For

1. **Coding Standards**
   - Black/isort formatting
   - Python 3.13+ features
   - Type hints completeness
   - No bare `except:`

2. **Code Constraints**
   - File size within 400 **logical** lines (see [Code Constraints](#code-constraints))
   - Function size within 30 **logical** lines (unless path excluded in constants)
   - One public type per file
   - Dependency injection

3. **Testing**
   - 90%+ coverage
   - AAA pattern
   - No skipped tests
   - Meaningful assertions

4. **Error Handling**
   - Domain-specific exceptions
   - Proper logging
   - Error context

5. **Documentation**
   - Docstrings for public APIs
   - Type hints on all parameters/returns
   - Examples for complex behavior

### Responding to Review Comments

- Address all feedback before re-requesting review
- Ask clarifying questions if feedback is unclear
- Push additional commits addressing feedback
- Re-request review when ready

### Getting Approved

Your PR needs:

- ✅ At least 1 approval from a maintainer
- ✅ All CI checks passing
- ✅ All requested changes addressed
- ✅ No merge conflicts

## Common Pitfalls

### 1. Async/Await Issues

```python
# ❌ WRONG - Mixing async and sync
def process_files(files: list[Path]):
    for file in files:
        content = await load_file(file)  # BLOCKED: Not in async function

# ✅ CORRECT
async def process_files(files: list[Path]) -> list[str]:
    contents: list[str] = []
    for file in files:
        content = await load_file(file)
        contents.append(content)
    return contents
```

### 2. Missing Type Hints

```python
# ❌ WRONG - No type hints
def validate_data(data):
    pass

# ✅ CORRECT
def validate_data(data: dict[str, object]) -> bool:
    """Validate data structure."""
    pass
```

### 3. Global State

```python
# ❌ WRONG - Global mutable state
_cache = {}  # BLOCKED: No globals

class MyClass:
    def process(self, key: str):
        _cache[key] = result

# ✅ CORRECT - Injected dependencies
class MyClass:
    def __init__(self, cache: dict[str, object]):
        self.cache = cache

    def process(self, key: str):
        self.cache[key] = result
```

### 4. Incorrect Test Structure

```python
# ❌ WRONG - No clear AAA
def test_something():
    obj = MyClass()
    obj.do_something()
    assert obj.state

# ✅ CORRECT - Clear AAA
def test_does_something_when_conditions_met():
    """Test that something works under conditions."""
    # Arrange
    obj = MyClass()
    expected_state = "success"

    # Act
    obj.do_something()

    # Assert
    assert obj.state == expected_state
```

### 5. Bare Except Clauses

```python
# ❌ WRONG - Bare except
try:
    dangerous_operation()
except:
    pass

# ✅ CORRECT - Specific exception
try:
    dangerous_operation()
except IOError as e:
    logger.error(f"IO error: {e}")
    raise CustomError("Operation failed") from e
```

### 6. Using typing Module Types

```python
# ❌ WRONG - typing module types
from typing import List, Dict, Optional

def process(items: List[str]) -> Dict[str, int]:
    pass

# ✅ CORRECT - Python 3.13+ built-ins
def process(items: list[str]) -> dict[str, int]:
    pass
```

### 7. Overly Generic Types

```python
# ❌ WRONG - Too generic
def build_response(data: dict[str, object]) -> dict[str, object]:
    pass

# ✅ CORRECT - Specific types
def build_response(data: dict[str, str]) -> dict[str, str | int]:
    pass
```

### 8. Synchronous File I/O in Async Code

```python
# ❌ WRONG - Synchronous I/O in async context
async def load_memory_bank(path: Path) -> dict:
    with open(path) as f:  # BLOCKED: Synchronous
        return json.load(f)

# ✅ CORRECT - Async file I/O
async def load_memory_bank(path: Path) -> dict:
    async with aiofiles.open(path) as f:
        content = await f.read()
        return json.loads(content)
```

### 9. Lines Exceeding Code Constraints

```bash
# ❌ WRONG - File exceeds 400 *logical* lines (check with check_file_sizes.py)
src/cortex/huge_module.py: fails CI file-size check

# ✅ CORRECT - Split into separate modules so each stays under the logical limit
src/cortex/validator.py: passes
src/cortex/formatter.py: passes
```

### 10. Not Using Concrete Types

```python
# ❌ WRONG - Returns object
def get_suggestions(...) -> object:
    suggestions = [RefactoringSuggestion(...)]
    return suggestions

# ✅ CORRECT - Returns concrete type
def get_suggestions(...) -> list[RefactoringSuggestion]:
    suggestions: list[RefactoringSuggestion] = [RefactoringSuggestion(...)]
    return suggestions
```

## Getting Help

### Documentation

- **[CLAUDE.md](../../CLAUDE.md)** - Project overview, architecture, and development instructions
- **[README.md](../../README.md)** - Project features and running the server
- **[CLAUDE.md](../../CLAUDE.md) and [AGENTS.md](../../AGENTS.md)** - Coding rules and standards (see also `.cursor/rules/` locally if present)
- **[PyProject.toml](../../pyproject.toml)** - Project configuration and dependencies

### Discussion and Questions

- **GitHub Issues**: Search existing issues or create a new one for bugs/features
- **GitHub Discussions**: Ask questions or discuss ideas
- **Code Comments**: Add comments in PRs if you need clarification

### Common Issues

#### "My code doesn't pass Black/isort"

```bash
# Simply run formatters
black . && isort .
```

#### "Type checking fails"

- Ensure all parameters and returns have type hints
- Use concrete types instead of `object`
- Check `python-coding-standards.mdc` (load via `rules(operation="get_relevant", task_description="python coding standards")`)

#### "Tests are failing"

- Run tests with verbose output: `pytest -v`
- Check coverage: `pytest --cov=src --cov-report=term-missing`
- Ensure mocks are set up correctly

#### "Function exceeds 30 lines"

- Extract helper functions
- Use list comprehensions instead of loops
- Move related logic to separate modules

#### "File exceeds 400 lines"

- Run `uv run python .cortex/synapse/scripts/python/check_file_sizes.py` — the failure is **logical** lines, not necessarily `wc -l`
- Identify logical groupings of code (not just comments/docstrings)
- Move code to separate modules; follow single responsibility principle

### Getting Started with Your First Contribution

1. **Read** CLAUDE.md and this guide
2. **Find** a good first issue (look for "good-first-issue" label)
3. **Create** a feature branch
4. **Make** your changes following the standards
5. **Test** thoroughly
6. **Format** your code
7. **Create** a pull request
8. **Respond** to review feedback

Welcome to the community! We're excited to work with you.
