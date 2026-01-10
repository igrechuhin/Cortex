# Cortex Testing Guide

A comprehensive guide to writing, running, and maintaining tests for the Cortex project. This document covers test organization, execution, standards, patterns, and troubleshooting.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Organization](#test-organization)
3. [Running Tests](#running-tests)
4. [Writing Unit Tests](#writing-unit-tests)
5. [Writing Integration Tests](#writing-integration-tests)
6. [Test Fixtures](#test-fixtures)
7. [Async Testing](#async-testing)
8. [Mocking](#mocking)
9. [Test Coverage](#test-coverage)
10. [Test Skipping Policy](#test-skipping-policy)
11. [Common Testing Patterns](#common-testing-patterns)
12. [Debugging Failed Tests](#debugging-failed-tests)
13. [Performance Testing](#performance-testing)
14. [Test Naming Conventions](#test-naming-conventions)

---

## Testing Philosophy

### Why We Test

Testing is a first-class activity in Cortex. We test to:

- **Verify Correctness**: Ensure code behaves as intended
- **Prevent Regressions**: Catch breaking changes early
- **Enable Refactoring**: Refactor with confidence when tests exist
- **Document Behavior**: Tests serve as executable documentation
- **Catch Edge Cases**: Tests force us to think about boundary conditions
- **Improve Design**: Writing testable code leads to better architecture

### Coverage Requirements

**Minimum 90% coverage** is mandatory for all new code. We target:

- **100% coverage** on critical business logic
- **90% coverage minimum** on new/modified code
- **Branch coverage** for conditional logic
- **Path coverage** for error handling

Coverage is enforced in CI. All PRs must maintain or improve coverage.

### Test-Driven Development (Recommended)

While not strictly enforced, TDD is encouraged:

1. Write failing test first
2. Write minimal code to pass the test
3. Refactor to improve design
4. Repeat

This approach ensures tests are meaningful and code is testable by design.

---

## Test Organization

### Directory Structure

```text
tests/
├── __init__.py                          # Test package marker
├── conftest.py                          # Shared fixtures and configuration
├── unit/                                # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_file_system.py
│   ├── test_token_counter.py
│   ├── test_link_parser.py
│   └── ... (one per module in src/)
├── integration/                         # Integration tests (slower, realistic)
│   ├── __init__.py
│   ├── test_workflows.py
│   ├── test_manager_integration.py
│   ├── test_mcp_tools_integration.py
│   └── ... (multi-module workflows)
└── (root test files for phase testing)
    ├── test_phase2.py
    ├── test_phase3.py
    └── ...
```

### File Organization Rules

- **One test module per source module**: `src/foo/bar.py` → `tests/unit/test_bar.py`
- **Test file naming**: `test_<module_name>.py` (required by pytest)
- **Test class naming**: `Test<FunctionOrClass>` (required by pytest)
- **Test method naming**: `test_<functionality>_<scenario>` (see [Test Naming Conventions](#test-naming-conventions))

### Test Scope Levels

| Scope | Purpose | Speed | Isolation |
|-------|---------|-------|-----------|
| **Unit** | Single function/class in isolation | <100ms | Complete |
| **Integration** | Multiple modules working together | <1s | File system mocked |
| **E2E** | Full system end-to-end workflows | Variable | Real dependencies |

For Cortex:

- **Unit tests** (90% of tests): Fast, deterministic, use mocks
- **Integration tests** (10% of tests): Real file I/O, multi-manager workflows
- **No E2E tests yet**: Can be added if needed for server testing

---

## Running Tests

### Quick Test Commands

#### Run all tests

```bash
# Quick run with timeout (recommended)
gtimeout -k 5 300 python -m pytest -q

# Verbose output
pytest -v

# With coverage report
pytest --cov=src/cortex --cov-report=term-missing
```

#### Run specific test file

```bash
pytest tests/unit/test_file_system.py -v
```

#### Run specific test class

```bash
pytest tests/unit/test_file_system.py::TestFileSystemManagerInitialization -v
```

#### Run specific test method

```bash
pytest tests/unit/test_file_system.py::TestFileSystemManagerInitialization::test_initialization_with_valid_path -v
```

#### Run tests matching pattern

```bash
pytest -k "test_parse" -v      # All tests with "parse" in name
pytest -m "integration" -v     # All integration tests
pytest -m "not slow" -v        # All tests except marked as slow
```

### Understanding pytest.ini Configuration

```ini
[pytest]
# Test discovery
testpaths = tests                    # Where pytest looks for tests
python_files = test_*.py             # Test file pattern
python_classes = Test*               # Test class pattern
python_functions = test_*            # Test function pattern

# Output options
addopts =
    -v                               # Verbose output
    --strict-markers                 # Error on unknown markers
    --tb=short                       # Short traceback format
    --disable-warnings               # Hide warnings (unless needed)
    --cov=src/cortex        # Coverage target
    --cov-report=html                # HTML coverage report
    --cov-report=term-missing        # Terminal report with missing lines
    --cov-report=json                # JSON report for CI
    --cov-branch                     # Branch coverage

# Available markers
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    asyncio: marks tests as async tests

# Asyncio configuration
asyncio_mode = auto                  # Auto-detect async tests

# Minimum Python version
minversion = 3.8
```

### Running with Different Options

```bash
# Run with logging enabled
pytest -v --log-cli-level=INFO

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run and stop at first failure
pytest -x

# Run and show print statements
pytest -s

# Run with strict markers (fail on unknown markers)
pytest --strict-markers

# Run with timeout per test
pytest --timeout=300
```

### Running Tests in CI

Tests run automatically on:

- **Push to main/PRs**: Full test suite with coverage enforcement
- **Pre-commit**: Quick validation (if configured)
- **Manual workflow**: Full suite with all reports

The CI pipeline enforces:

- **All tests must pass**
- **Coverage must be ≥90%**
- **No test skips without justification**
- **Code formatting with Black/isort**

---

## Writing Unit Tests

Unit tests verify individual functions/classes in isolation with mocked dependencies.

### AAA Pattern (Arrange-Act-Assert)

All tests MUST follow the AAA pattern:

```python
def test_calculate_total_including_tax():
    """Test total calculation with tax applied."""
    # Arrange: Set up test data and dependencies
    service = PricingService()
    items = [
        {"name": "Widget", "price": 10.00, "quantity": 2},
        {"name": "Gadget", "price": 5.50, "quantity": 1}
    ]
    tax_rate = 0.08  # 8% tax

    # Act: Execute the code under test
    total = service.calculate_total(items, tax_rate)

    # Assert: Verify the expected outcome
    expected_total = (10.00 * 2 + 5.50 * 1) * 1.08  # 25.50 * 1.08 = 27.54
    assert total == pytest.approx(expected_total, abs=0.01)
```

Why AAA?

- **Clear test structure**: Easy to understand what's being tested
- **Reusable parts**: Can extract common arrange/assert patterns
- **Focused assertions**: Each test verifies one behavior
- **Debuggable**: Clear failure messages point to actual vs expected

### Basic Unit Test Example

```python
"""
Unit tests for file_system module.

Tests file system operations including locking, conflict detection,
and markdown parsing.
"""

from pathlib import Path
import pytest
from cortex.file_system import FileSystemManager
from cortex.exceptions import FileConflictError


class TestFileSystemManagerInitialization:
    """Tests for FileSystemManager initialization."""

    def test_initialization_with_valid_path(self, temp_project_root: Path):
        """Test FileSystemManager initializes with valid project root."""
        # Arrange & Act
        manager = FileSystemManager(temp_project_root)

        # Assert
        assert manager is not None
        assert manager.project_root == temp_project_root.resolve()
        assert manager.lock_timeout == 5.0

    def test_initialization_resolves_relative_paths(self, temp_project_root: Path):
        """Test FileSystemManager resolves relative paths correctly."""
        # Arrange
        relative_path = temp_project_root / "subdir" / ".."

        # Act
        manager = FileSystemManager(relative_path)

        # Assert
        assert manager.project_root == temp_project_root.resolve()


class TestPathValidation:
    """Tests for path validation and security."""

    def test_validate_path_within_project_succeeds(self, temp_project_root: Path):
        """Test validation succeeds for path within project."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        valid_path = temp_project_root / "memory-bank" / "test.md"

        # Act
        result = manager.validate_path(valid_path)

        # Assert
        assert result is True

    def test_validate_path_outside_project_fails(self, temp_project_root: Path):
        """Test validation fails for path outside project."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        invalid_path = temp_project_root.parent / "outside.md"

        # Act
        result = manager.validate_path(invalid_path)

        # Assert
        assert result is False

    def test_validate_path_blocks_directory_traversal(self, temp_project_root: Path):
        """Test validation blocks directory traversal attempts."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        # Try to traverse outside project using ../
        traversal_path = temp_project_root / "memory-bank" / ".." / ".." / "outside.md"

        # Act
        result = manager.validate_path(traversal_path)

        # Assert
        assert result is False


class TestContentHashing:
    """Tests for content hashing."""

    def test_compute_hash_for_simple_content(self, temp_project_root: Path):
        """Test computing hash for simple content."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "Hello, world!"

        # Act
        hash1 = manager.compute_hash(content)
        hash2 = manager.compute_hash(content)

        # Assert
        assert hash1 == hash2  # Same content = same hash
        assert isinstance(hash1, str)
        assert len(hash1) > 0

    def test_compute_hash_differs_for_different_content(self, temp_project_root: Path):
        """Test that different content produces different hashes."""
        # Arrange
        manager = FileSystemManager(temp_project_root)

        # Act
        hash1 = manager.compute_hash("content 1")
        hash2 = manager.compute_hash("content 2")

        # Assert
        assert hash1 != hash2


class TestExceptionHandling:
    """Tests for exception handling in file operations."""

    def test_read_nonexistent_file_raises_file_not_found(self, temp_project_root: Path):
        """Test reading nonexistent file raises appropriate exception."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        nonexistent = temp_project_root / "memory-bank" / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            manager.read_file(nonexistent)

    def test_write_to_invalid_path_raises_error(self, temp_project_root: Path):
        """Test writing to invalid path raises error."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        invalid_path = temp_project_root.parent / "outside" / "file.md"

        # Act & Assert
        with pytest.raises((FileConflictError, ValueError)):
            manager.write_file(invalid_path, "content")
```

### Testing Error Cases

Always test both success and failure paths:

```python
def test_data_validation_with_valid_input_succeeds(self):
    """Test validation succeeds with valid input."""
    # Arrange
    validator = InputValidator()
    valid_data = {"name": "John", "age": 30}

    # Act
    result = validator.validate(valid_data)

    # Assert
    assert result is True


def test_data_validation_with_invalid_email_fails(self):
    """Test validation fails with invalid email."""
    # Arrange
    validator = InputValidator()
    invalid_data = {"name": "John", "email": "not-an-email"}

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(invalid_data)

    # Verify error message
    assert "email" in str(exc_info.value).lower()


def test_data_validation_with_missing_required_field_fails(self):
    """Test validation fails with missing required field."""
    # Arrange
    validator = InputValidator()
    incomplete_data = {"age": 30}  # Missing 'name'

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(incomplete_data)

    assert "required" in str(exc_info.value).lower()
```

### Testing Edge Cases

Test boundary conditions and edge cases:

```python
def test_token_counter_with_empty_string(self):
    """Test token counting returns zero for empty string."""
    counter = TokenCounter()

    count = counter.count_tokens("")

    assert count == 0


def test_token_counter_with_very_long_text(self):
    """Test token counting handles very large documents."""
    counter = TokenCounter()
    large_text = "word " * 10000  # 50,000 characters

    count = counter.count_tokens(large_text)

    assert count > 0
    assert isinstance(count, int)


def test_token_counter_with_unicode_content(self):
    """Test token counting handles unicode characters."""
    counter = TokenCounter()
    unicode_text = "Hello 世界 مرحبا мир"

    count = counter.count_tokens(unicode_text)

    assert count > 0
```

---

## Writing Integration Tests

Integration tests verify multiple modules work together correctly. They use real file I/O but mock external services.

### Integration Test Example

```python
"""
Integration tests for cross-module workflows in Cortex.

These tests verify that multiple modules work together correctly
to provide end-to-end functionality across different phases.
"""

from pathlib import Path
import pytest
from cortex.file_system import FileSystemManager
from cortex.link_parser import LinkParser
from cortex.dependency_graph import DependencyGraph
from cortex.metadata_index import MetadataIndex


@pytest.mark.integration
class TestPhase1Phase2Integration:
    """Test integration between file operations and linking."""

    async def test_file_write_then_parse_links(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test writing a file and then parsing its links."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        link_parser = LinkParser()

        # Act: Write a file with links
        content_with_links = """# Test Document

See [Project Brief](projectBrief.md) for details.
Check [Active Context](activeContext.md#current-work) for status.
"""
        file_path = temp_project_root / "memory-bank" / "test.md"
        _ = await file_system.write_file(file_path, content_with_links)

        # Parse links from the file
        content, _ = await file_system.read_file(file_path)
        links = await link_parser.parse_file(content)

        # Assert
        all_links = links["markdown_links"] + links["transclusions"]
        assert len(all_links) >= 2
        assert any(link.get("target") == "projectBrief.md" for link in all_links)
        assert any(link.get("target") == "activeContext.md" for link in all_links)


@pytest.mark.integration
class TestManagerCoordination:
    """Test manager coordination and shared state."""

    async def test_managers_share_metadata_index(self, temp_project_root: Path):
        """Test that managers properly coordinate through metadata index."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        metadata_index = MetadataIndex(temp_project_root)
        dependency_graph = DependencyGraph()

        # Act: Create file through file_system
        file_path = temp_project_root / "memory-bank" / "test.md"
        content = "# Test\nContent."
        _ = await file_system.write_file(file_path, content)

        # Act: Update metadata and dependency graph
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content.encode("utf-8")),
            token_count=5,
            content_hash="abc123",
            sections=[],
        )
        dependency_graph.add_link_dependency("test.md", "test.md", "self")

        # Assert: Verify coordination
        metadata = await metadata_index.get_file_metadata("test.md")
        assert metadata is not None
        assert "test.md" in dependency_graph.get_all_files()
```

### When to Use Integration Tests

Use integration tests for:

- **Multi-manager workflows**: File operations + metadata updates
- **Complex scenarios**: Multiple interdependent operations
- **Real file I/O**: When real disk operations are critical
- **Phase testing**: Cross-phase integrations

**Don't use integration tests for:**

- Single module functionality (use unit tests)
- External service calls (mock them)
- Simple workflows (unit tests are faster)

---

## Test Fixtures

Fixtures provide reusable test data and setup. All fixtures are in `tests/conftest.py`.

### Understanding pytest Fixtures

Fixtures are functions that:

- Set up test data (Arrange phase)
- Provide common resources
- Handle cleanup automatically

```python
import pytest
from pathlib import Path

# Simple fixture
@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
    }

# Fixture with cleanup
@pytest.fixture
def temp_directory():
    """Create temporary directory and clean up after test."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
    # Cleanup happens automatically


# Fixture with dependencies
@pytest.fixture
async def service_with_mock_db(mock_database):
    """Create service with mocked database."""
    service = MyService(database=mock_database)
    await service.initialize()
    yield service
    await service.cleanup()
```

### Fixture Scopes

```python
# Function scope (default) - one per test
@pytest.fixture
def data():
    return {"value": 1}

# Class scope - one per test class
@pytest.fixture(scope="class")
def db_connection():
    return create_connection()

# Module scope - one per test module
@pytest.fixture(scope="module")
def large_data():
    return load_large_dataset()

# Session scope - one for entire test session
@pytest.fixture(scope="session")
def mock_tiktoken_globally():
    """Mock tiktoken to avoid network access."""
    # Set up once for all tests
```

### Available Fixtures in conftest.py

#### Project Setup Fixtures

```python
# temp_project_root: Path
# Temporary project directory with memory-bank subdirectory

# memory_bank_dir: Path
# Path to memory-bank directory
```

#### Memory Bank Content Fixtures

```python
# sample_memory_bank_files: dict[str, Path]
# Complete set of standard memory bank files:
# - memorybankinstructions.md
# - projectBrief.md
# - activeContext.md
# - systemPatterns.md
# - techContext.md
# - productContext.md
# - progress.md

# sample_file_with_links: Path
# File with markdown links and transclusions for testing

# sample_rules_folder: Path
# Folder with sample rules files (general, python, security)
```

#### Manager Fixtures

```python
# mock_file_system: FileSystemManager
# Real FileSystemManager instance for testing

# mock_metadata_index: MetadataIndex
# Real MetadataIndex instance

# mock_link_parser: LinkParser
# Real LinkParser instance

# mock_dependency_graph: DependencyGraph
# Real DependencyGraph instance

# mock_token_counter: Mock
# Mocked TokenCounter (avoids tiktoken network access)

# mock_relevance_scorer: RelevanceScorer
# Real RelevanceScorer instance

# mock_context_optimizer: ContextOptimizer
# ContextOptimizer with mocked strategies
```

#### Configuration Fixtures

```python
# optimization_config_dict: dict[str, object]
# Default optimization configuration

# validation_config_dict: dict[str, object]
# Default validation configuration

# adaptation_config_dict: dict[str, object]
# Default adaptation configuration
```

#### Test Data Fixtures

```python
# sample_metadata_entry: dict
# Sample metadata with sections and links

# sample_version_snapshot: dict
# Sample version snapshot data

# sample_files_content: dict[str, str]
# Sample file contents for testing

# sample_files_metadata: dict[str, dict]
# Sample file metadata for testing
```

### Using Fixtures in Tests

```python
class TestFileSystem:
    """Test file system with fixtures."""

    def test_with_temp_directory(self, temp_project_root: Path):
        """Test using temporary project root."""
        manager = FileSystemManager(temp_project_root)
        assert manager.project_root == temp_project_root.resolve()

    def test_with_sample_files(self, sample_memory_bank_files: dict[str, Path]):
        """Test with pre-created memory bank files."""
        assert len(sample_memory_bank_files) == 7
        assert "projectBrief.md" in sample_memory_bank_files

    def test_with_multiple_fixtures(
        self,
        temp_project_root: Path,
        sample_metadata_entry: dict,
        mock_token_counter
    ):
        """Test using multiple fixtures."""
        # All fixtures are injected and ready to use
        pass
```

### Creating Custom Fixtures

```python
# In tests/conftest.py or any test file

@pytest.fixture
def custom_file_content():
    """Create custom file content for specific tests."""
    return """# Custom Test File

## Section 1
Content here.

## Section 2
More content.
"""


@pytest.fixture
async def async_service():
    """Create async service for testing."""
    service = AsyncService()
    await service.setup()
    yield service
    await service.cleanup()


# Use in tests
def test_with_custom_fixture(custom_file_content):
    """Test with custom fixture."""
    assert "Section 1" in custom_file_content
    assert len(custom_file_content) > 0


@pytest.mark.asyncio
async def test_async_service(async_service):
    """Test async service."""
    result = await async_service.do_something()
    assert result is not None
```

---

## Async Testing

Async tests use `pytest-asyncio` for proper event loop management.

### Running Async Tests

```bash
# Async tests are automatically detected by @pytest.mark.asyncio
pytest tests/unit/test_link_parser.py -v
```

### Writing Async Tests

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_file_reading(mock_file_system):
    """Test async file reading operation."""
    # Arrange
    file_path = Path("test.md")
    expected_content = "# Test"

    # Act
    content, hash_value = await mock_file_system.read_file(file_path)

    # Assert
    assert content is not None
    assert isinstance(hash_value, str)


@pytest.mark.asyncio
async def test_async_operation_with_mock():
    """Test async operation with mocked dependency."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.fetch_data.return_value = [1, 2, 3]
    service = DataService(db=mock_db)

    # Act
    result = await service.get_all_data()

    # Assert
    assert result == [1, 2, 3]
    mock_db.fetch_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_timeout_handling():
    """Test async operation timeout."""
    import asyncio

    async def slow_operation():
        await asyncio.sleep(10)
        return "done"

    # Assert that operation times out
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(0.1):
            await slow_operation()
```

### Async Fixtures

```python
@pytest.fixture
async def async_database():
    """Create async database connection for testing."""
    db = AsyncDatabase()
    await db.connect()
    await db.setup_test_schema()

    yield db

    # Cleanup
    await db.cleanup_test_data()
    await db.disconnect()


@pytest.mark.asyncio
async def test_with_async_fixture(async_database):
    """Test using async fixture."""
    result = await async_database.query("SELECT * FROM test")
    assert result is not None
```

### Async Test Parametrization

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("input_data,expected", [
    ({"value": 1}, {"result": 2}),
    ({"value": 0}, {"result": 0}),
    ({"value": -1}, {"result": -2}),
])
async def test_async_transformation(input_data, expected):
    """Test async data transformation with multiple inputs."""
    transformer = AsyncDataTransformer()

    result = await transformer.transform(input_data)

    assert result == expected
```

---

## Mocking

Mocking replaces real implementations with test doubles to isolate code under test.

### When to Mock

| Situation | Mock? | Why |
|-----------|-------|-----|
| External API calls | Yes | Tests shouldn't depend on external services |
| Database operations | Yes (unit tests) | Isolation and speed |
| File I/O | Yes (unit tests) | Real files in integration tests |
| Internal functions | No | Test through public API instead |
| User input parsing | No | Parse real data to test behavior |

### Using unittest.mock

```python
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import pytest

# Create a mock object
def test_with_mock_object():
    """Test using a mock object."""
    # Arrange
    mock_repo = Mock()
    mock_repo.save.return_value = True
    service = UserService(mock_repo)

    # Act
    result = service.create_user({"name": "Test"})

    # Assert
    assert result is True
    mock_repo.save.assert_called_once()


# Mock with side effects (exceptions)
def test_with_side_effect():
    """Test handling of exceptions from mocked dependency."""
    # Arrange
    mock_repo = Mock()
    mock_repo.save.side_effect = DatabaseError("Connection failed")
    service = UserService(mock_repo)

    # Act & Assert
    with pytest.raises(DatabaseError):
        service.create_user({"name": "Test"})


# Patch external modules
def test_with_patch():
    """Test using patch to replace module import."""
    with patch('requests.get') as mock_get:
        # Arrange
        mock_get.return_value.json.return_value = {"status": "ok"}
        client = APIClient()

        # Act
        result = client.get_status()

        # Assert
        assert result == {"status": "ok"}
        mock_get.assert_called_once()


# Async mocking
@pytest.mark.asyncio
async def test_async_service_with_mock():
    """Test async service with mocked dependency."""
    # Arrange
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [{"id": 1}]
    service = AsyncDataService(mock_db)

    # Act
    result = await service.get_data()

    # Assert
    assert len(result) == 1
    mock_db.fetch.assert_called_once()
```

### Mock Configuration

```python
# Configure mock return values
mock = Mock()
mock.method.return_value = "result"
mock.property = "value"

# Configure multiple calls
mock.method.side_effect = ["first", "second", "third"]

# Verify mock was called
mock.method.assert_called_once()
mock.method.assert_called_with(arg1, arg2)
mock.method.assert_called_with(arg1=value)
mock.method.assert_not_called()
mock.method.call_count == 3

# Call details
assert mock.method.call_args == call(arg1, arg2)
assert mock.method.call_args_list == [call(...), call(...)]
```

### Avoid Over-Mocking

```python
# ❌ DON'T: Mock everything (hides test value)
def test_user_creation_over_mocked():
    with patch.object(service, '_validate') as mock_validate, \
         patch.object(service, '_save') as mock_save, \
         patch.object(service, '_notify') as mock_notify:
        mock_validate.return_value = True
        mock_save.return_value = 123
        result = service.create_user(data)
        assert result == 123  # Tests nothing meaningful

# ✅ DO: Mock only external dependencies
def test_user_creation_proper():
    # Arrange
    mock_repo = Mock()
    mock_repo.save.return_value = True
    service = UserService(mock_repo)

    # Act
    result = service.create_user({"name": "Test"})

    # Assert
    assert result is True
    mock_repo.save.assert_called_once()
```

---

## Test Coverage

Coverage measures what percentage of code is executed by tests.

### Running Tests with Coverage

```bash
# Generate coverage report
pytest --cov=src/cortex --cov-report=term-missing

# Generate HTML report
pytest --cov=src/cortex --cov-report=html
# Open htmlcov/index.html in browser

# Generate JSON report (for CI)
pytest --cov=src/cortex --cov-report=json

# Show coverage for specific file
pytest --cov=src/cortex/file_system.py --cov-report=term-missing
```

### Interpreting Coverage Reports

```text
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
file_system.py            150     10    93%    145, 150, 152-155
link_parser.py            200     15    92%    89-92, 145
token_counter.py           80      3    96%    45
------------------------------------------------------
TOTAL                     430     28    93%
```

- **Stmts**: Total statements
- **Miss**: Uncovered statements
- **Cover**: Percentage coverage
- **Missing**: Line numbers not covered

### Improving Coverage

1. **Identify missing lines**: Run coverage report
2. **Write tests for missing lines**: Add test cases
3. **Verify coverage increases**: Re-run coverage report
4. **Repeat until ≥90%**: Continue until target is met

```python
# Example: Improving coverage for error handling

# Before: 85% coverage
def parse_config(config_path):
    """Parse configuration file."""
    with open(config_path) as f:
        return json.load(f)

# Test covers happy path but misses error handling
def test_parse_config_with_valid_file():
    config = parse_config("config.json")
    assert config is not None

# After: 100% coverage
def test_parse_config_with_valid_file():
    """Test parsing valid configuration."""
    config = parse_config("config.json")
    assert config is not None

def test_parse_config_with_invalid_json():
    """Test parsing invalid JSON raises error."""
    with pytest.raises(json.JSONDecodeError):
        parse_config("invalid.json")

def test_parse_config_with_missing_file():
    """Test parsing missing file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_config("nonexistent.json")
```

### Coverage Best Practices

- **Focus on critical paths**: 100% coverage on business logic
- **Branch coverage matters**: Cover if/else conditions
- **Exclude test artifacts**: Don't count test files in coverage
- **Use coverage markers**: `# pragma: no cover` for unreachable code

```python
# Exclude unreachable code from coverage
def function_with_unreachable_code():
    return True
    # pragma: no cover
    print("This is unreachable")  # Excluded from coverage


# Exclude debug code
if __debug__:  # pragma: no cover
    print("Debug info")
```

---

## Test Skipping Policy

### The Rule: NO BLANKET SKIPS

Blanket skips hide problems and are NOT allowed. Every skip must be:

1. **Justified**: Include a clear reason
2. **Referenced**: Link to issue/ticket
3. **Temporary**: Include removal condition
4. **Reviewed**: Check regularly for removal

### Proper Skip Example

```python
import pytest
import platform

@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Unix-only test - see issue #123 for Windows support plan"
)
def test_unix_file_permissions():
    """Test Unix file permission handling."""
    # Test Unix-specific functionality
    pass


@pytest.mark.skipif(
    not pytest.config.getini("integration"),
    reason="Slow integration test - only run with --integration flag"
)
def test_slow_database_migration():
    """Test database migration performance."""
    pass
```

### When Skips Are Acceptable

✅ **Acceptable skips**:

- Platform-specific functionality (Windows vs Unix)
- Optional dependencies not installed
- External service unavailable (and truly unavoidable)
- Very slow tests that shouldn't run by default

❌ **NOT acceptable**:

- "TODO: fix this test"
- "This test is flaky"
- "Waiting for feature implementation"
- Entire test modules skipped

### The Correct Approach for "Flaky" Tests

Instead of skipping, fix the test:

```python
# ❌ WRONG: Flaky test that gets skipped
@pytest.mark.skipif(True, reason="Flaky test")
@pytest.mark.asyncio
async def test_external_api_call():
    result = await call_external_api()
    assert result is not None

# ✅ RIGHT: Mock external dependency to make test reliable
@pytest.mark.asyncio
async def test_external_api_call():
    # Arrange
    mock_api = AsyncMock()
    mock_api.call.return_value = {"status": "ok"}
    service = ExternalAPIClient(mock_api)

    # Act
    result = await service.call()

    # Assert
    assert result == {"status": "ok"}
```

### Xfail (Expected Failures)

Use `xfail` only with clear reason and removal plan:

```python
@pytest.mark.xfail(
    reason="Expected to fail until issue #456 is resolved",
    condition=True
)
def test_pending_feature():
    """Test feature not yet implemented."""
    # This test is expected to fail
    assert new_feature_implemented()  # Currently fails
```

---

## Common Testing Patterns

### Testing File I/O

```python
class TestFileOperations:
    """Tests for file operations."""

    async def test_write_and_read_file(self, temp_project_root: Path):
        """Test writing and reading file."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "memory-bank" / "test.md"
        content = "# Test\nContent"

        # Act: Write file
        await file_system.write_file(file_path, content)

        # Act: Read file
        read_content, hash_value = await file_system.read_file(file_path)

        # Assert
        assert read_content == content
        assert isinstance(hash_value, str)

    async def test_file_not_found_raises_error(self, temp_project_root: Path):
        """Test reading nonexistent file raises error."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        nonexistent = temp_project_root / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            await file_system.read_file(nonexistent)
```

### Parametrized Tests

Test multiple scenarios with one test function:

```python
@pytest.mark.parametrize("input_data,expected_output", [
    ({"value": 1}, 2),
    ({"value": 0}, 0),
    ({"value": -1}, -2),
    ({"value": 100}, 200),
])
def test_calculation_with_multiple_inputs(input_data, expected_output):
    """Test calculation with various inputs."""
    service = CalculationService()

    result = service.double(input_data["value"])

    assert result == expected_output


# Parametrize with fixture
@pytest.mark.parametrize("markdown_content,expected_links", [
    ("# Title", 0),
    ("[link](target.md)", 1),
    ("[link1](a.md) [link2](b.md)", 2),
])
def test_link_parsing_count(markdown_content, expected_links, mock_link_parser):
    """Test link count for various markdown."""
    result = mock_link_parser.parse(markdown_content)
    assert len(result["links"]) == expected_links
```

### Testing with Multiple Assertions

Use multiple assertions when they test related aspects:

```python
def test_user_creation_returns_valid_object():
    """Test created user has all required properties."""
    # Arrange
    service = UserService()
    user_data = {"name": "John", "email": "john@example.com"}

    # Act
    user = service.create_user(user_data)

    # Assert
    assert user.id is not None
    assert user.name == "John"
    assert user.email == "john@example.com"
    assert user.created_at is not None
    assert isinstance(user.created_at, datetime)
```

### Testing Collections

```python
def test_list_operations():
    """Test list manipulation."""
    # Arrange
    items = ["a", "b", "c"]
    processor = ListProcessor()

    # Act
    result = processor.unique(items + ["a"])

    # Assert
    assert len(result) == 3
    assert "a" in result
    assert "b" in result
    assert "c" in result


def test_dict_operations():
    """Test dictionary operations."""
    # Arrange
    data = {"x": 1, "y": 2, "z": 3}
    processor = DictProcessor()

    # Act
    result = processor.invert(data)

    # Assert
    assert result == {1: "x", 2: "y", 3: "z"}
    assert 1 in result
    assert "x" in result.values()
```

### Testing with Temporary Data

```python
def test_with_temporary_file(tmp_path: Path):
    """Test using pytest's built-in tmp_path fixture."""
    # Arrange
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Act
    content = test_file.read_text()

    # Assert
    assert content == "test content"


def test_with_temporary_directory(temp_project_root: Path):
    """Test using custom temporary directory fixture."""
    # Arrange (temp_project_root already has memory-bank subdirectory)
    test_file = temp_project_root / "memory-bank" / "test.md"

    # Act & Assert
    assert (temp_project_root / "memory-bank").exists()
```

---

## Debugging Failed Tests

### Understanding Test Output

```bash
# Run with verbose output
pytest tests/unit/test_file_system.py -v

# Output shows:
# tests/unit/test_file_system.py::TestClass::test_method PASSED [100%]
# tests/unit/test_file_system.py::TestClass::test_other FAILED  [200%]

# FAILED test shows:
# AssertionError: assert False
# > assert result == expected
# E  AssertionError: assert 10 == 20
```

### Debugging Strategies

#### 1. Use Print Statements

```bash
# Run with -s flag to show print output
pytest tests/unit/test_example.py::test_my_test -s

def test_with_debug_output():
    """Test with debug output."""
    value = calculate_something()
    print(f"DEBUG: value = {value}")  # Will show with pytest -s
    assert value > 0
```

#### 2. Use pytest's --pdb Flag

```bash
# Drop into debugger on failure
pytest tests/unit/test_example.py --pdb

# In debugger:
# (Pdb) p value              # Print variable
# (Pdb) n                    # Next line
# (Pdb) c                    # Continue
# (Pdb) q                    # Quit
```

#### 3. Run Single Test

```bash
# Run specific test with full output
pytest tests/unit/test_file_system.py::TestClass::test_method -vv

# -vv shows more detail including local variables
```

#### 4. Check Logs

```bash
# Enable logging output
pytest tests/unit/test_example.py --log-cli-level=DEBUG

# Or in test
import logging
logging.debug(f"Value: {value}")
```

### Common Failure Patterns

#### Async Test Not Awaited

```python
# ❌ WRONG: Function not awaited
@pytest.mark.asyncio
async def test_async_operation():
    result = file_system.read_file(path)  # Missing await
    assert result is not None

# ✅ RIGHT: Function awaited
@pytest.mark.asyncio
async def test_async_operation():
    result = await file_system.read_file(path)
    assert result is not None
```

#### Fixture Not Used

```python
# ❌ WRONG: Fixture parameter not used
def test_with_fixture(mock_database):
    # mock_database not used anywhere
    value = some_function()
    assert value > 0

# ✅ RIGHT: Fixture properly used
def test_with_fixture(mock_database):
    service = MyService(db=mock_database)
    value = service.get_value()
    assert value > 0
```

#### Mock Not Set Up

```python
# ❌ WRONG: Mock not configured with return value
def test_mock_operation():
    mock_api = Mock()
    service = APIClient(mock_api)

    # No return_value set!
    result = service.call_api()
    assert result == "expected"  # Fails: result is Mock object

# ✅ RIGHT: Mock properly configured
def test_mock_operation():
    mock_api = Mock()
    mock_api.call.return_value = "expected"
    service = APIClient(mock_api)

    result = service.call_api()
    assert result == "expected"
```

#### Timing Issues in Async Tests

```python
# ❌ WRONG: Race condition
@pytest.mark.asyncio
async def test_async_race_condition():
    service = AsyncService()
    service.start()  # Starts background task
    result = service.get_result()  # Might get stale result
    assert result is not None

# ✅ RIGHT: Wait for completion
@pytest.mark.asyncio
async def test_async_race_condition():
    service = AsyncService()
    result = await service.do_work()  # Wait for completion
    assert result is not None
```

---

## Performance Testing

### Token Counting Performance

```python
import time

def test_token_counter_performance():
    """Test token counter meets performance requirements."""
    # Arrange
    counter = TokenCounter()
    large_text = "word " * 10000  # ~50KB text

    # Act
    start = time.time()
    count = counter.count_tokens(large_text)
    duration = time.time() - start

    # Assert
    assert count > 0
    assert duration < 1.0  # Must complete in under 1 second


@pytest.mark.benchmark
def test_file_operation_performance(benchmark):
    """Benchmark file operation performance."""
    file_system = FileSystemManager(temp_project_root)
    path = Path("test.md")
    content = "# Test\n" + "content " * 1000

    def run_write():
        return file_system.write_file(path, content)

    # Measure performance
    result = benchmark(run_write)

    # File write should be fast (< 10ms for typical files)
```

### Load Testing

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_concurrent_file_operations():
    """Test handling concurrent file operations."""
    # Arrange
    file_system = FileSystemManager(temp_project_root)
    tasks = []

    # Act: Create 10 concurrent file operations
    for i in range(10):
        path = temp_project_root / "memory-bank" / f"file{i}.md"
        content = f"# File {i}\nContent"
        task = file_system.write_file(path, content)
        tasks.append(task)

    # Act: Wait for all to complete
    results = await asyncio.gather(*tasks)

    # Assert
    assert len(results) == 10
    assert all(r is not None for r in results)
```

---

## Test Naming Conventions

### Naming Pattern

All test names follow this pattern:

```text
test_<functionality>_<scenario>
test_<functionality>_when_<condition>
test_<functionality>_with_<condition>
```

### Examples

```python
# ✅ GOOD: Clear, descriptive names

# Format: test_<functionality>_<scenario>
def test_user_creation_with_valid_data():
    pass

def test_user_creation_with_invalid_email():
    pass

def test_user_creation_when_email_already_exists():
    pass

def test_user_creation_when_database_fails():
    pass

# Format: test_<class>_<method>_<scenario>
def test_file_system_read_file_returns_content():
    pass

def test_file_system_read_file_raises_error_for_missing_file():
    pass

def test_link_parser_parse_markdown_link():
    pass

def test_link_parser_parse_transclusion_directive():
    pass

# ❌ BAD: Unclear names

def test_user():  # What about user?
    pass

def test_1():  # What does this test?
    pass

def test_user_creation():  # Success or failure? Which case?
    pass

def test_parse():  # Parse what?
    pass
```

### Class-Based Tests

Group related tests in classes:

```python
class TestFileSystemManagerInitialization:
    """Tests for FileSystemManager initialization."""

    def test_initialization_with_valid_path(self):
        pass

    def test_initialization_resolves_relative_paths(self):
        pass


class TestFileSystemManagerPathValidation:
    """Tests for FileSystemManager path validation."""

    def test_validate_path_within_project_succeeds(self):
        pass

    def test_validate_path_outside_project_fails(self):
        pass

    def test_validate_path_blocks_traversal_attempts(self):
        pass


class TestFileSystemManagerErrorHandling:
    """Tests for FileSystemManager error handling."""

    def test_read_nonexistent_file_raises_error(self):
        pass

    def test_write_to_locked_file_raises_error(self):
        pass
```

---

## Summary: Testing Checklist

Before submitting a PR, verify:

- [ ] All tests pass: `pytest -q`
- [ ] Coverage ≥90%: `pytest --cov=src/cortex`
- [ ] Tests follow AAA pattern
- [ ] Test names are descriptive
- [ ] Async tests use `@pytest.mark.asyncio`
- [ ] No blanket skips
- [ ] Mock only external dependencies
- [ ] Error paths tested
- [ ] Edge cases covered
- [ ] No hardcoded test data (use fixtures)
- [ ] Integration tests marked with `@pytest.mark.integration`
- [ ] Code formatted: `black . && isort .`

---

## Additional Resources

- **pytest documentation**: <https://docs.pytest.org/>
- **pytest-asyncio**: <https://pytest-asyncio.readthedocs.io/>
- **unittest.mock**: <https://docs.python.org/3/library/unittest.mock.html>
- **Project CLAUDE.md**: See `.cursor/CLAUDE.md` for testing standards

---

## Getting Help

If tests fail or you're unsure how to test:

1. **Check existing tests**: Look at similar tests in `tests/unit/` or `tests/integration/`
2. **Review fixtures**: Check `tests/conftest.py` for available helpers
3. **Read error messages**: pytest provides clear failure details
4. **Use debugging**: Run with `-s` flag to see print output
5. **Ask for review**: Share test code in PR for feedback

Happy testing!
