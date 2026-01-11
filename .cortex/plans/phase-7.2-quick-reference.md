# Phase 7.2: Test Infrastructure - Quick Reference

## Quick Start Guide for Test Development

---

## Running Tests

```bash
# Run all tests with coverage
uv run --native-tls pytest tests/

# Run specific test file
uv run --native-tls pytest tests/unit/test_exceptions.py -v

# Run specific test class
uv run --native-tls pytest tests/unit/test_exceptions.py::TestMemoryBankError -v

# Run specific test
uv run --native-tls pytest tests/unit/test_exceptions.py::TestMemoryBankError::test_memory_bank_error_is_exception -v

# Run without coverage (faster)
uv run --native-tls pytest tests/ --no-cov

# Run only unit tests
uv run --native-tls pytest tests/ -m unit

# Run only integration tests
uv run --native-tls pytest tests/ -m integration

# Skip slow tests
uv run --native-tls pytest tests/ -m "not slow"

# View coverage report
open htmlcov/index.html  # After running tests with coverage
```

---

## Test Structure Template

```python
"""
Unit tests for {module_name} module.

Tests {brief description of what the module does}.
"""

import pytest
from src.cortex.{module_name} import {ClassName}


class Test{ClassName}:
    """Tests for {ClassName} functionality."""

    def test_method_returns_expected_value_when_valid_input(self, fixture_name):
        """Test method with valid input returns expected result."""
        # Arrange
        instance = ClassName()
        valid_input = "test_value"

        # Act
        result = instance.method(valid_input)

        # Assert
        assert result == expected_value
        assert isinstance(result, ExpectedType)

    def test_method_raises_error_when_invalid_input(self):
        """Test method raises appropriate error for invalid input."""
        # Arrange
        instance = ClassName()
        invalid_input = None

        # Act & Assert
        with pytest.raises(ExpectedError) as exc_info:
            instance.method(invalid_input)

        assert "expected error message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_method_completes_successfully(self, temp_project_root):
        """Test async method completes without errors."""
        # Arrange
        instance = ClassName(temp_project_root)

        # Act
        result = await instance.async_method()

        # Assert
        assert result is not None
```

---

## Available Fixtures

### Project Directory Fixtures

```python
def test_something(temp_project_root):
    """temp_project_root: Temporary project root with memory-bank/ subdirectory"""
    pass

def test_something(memory_bank_dir):
    """memory_bank_dir: Path to memory-bank directory"""
    pass
```

### Memory Bank File Fixtures

```python
def test_something(sample_memory_bank_files):
    """sample_memory_bank_files: Dict of all 7 standard files with paths"""
    # Returns: {"memorybankinstructions.md": Path, "projectBrief.md": Path, ...}
    pass

def test_something(sample_file_with_links):
    """sample_file_with_links: File with markdown links and transclusions"""
    pass
```

### Rules and Configuration Fixtures

```python
def test_something(sample_rules_folder):
    """sample_rules_folder: .cursorrules directory with multiple rule files"""
    pass

def test_something(optimization_config_dict):
    """optimization_config_dict: Default optimization configuration dict"""
    pass

def test_something(validation_config_dict):
    """validation_config_dict: Default validation configuration dict"""
    pass

def test_something(adaptation_config_dict):
    """adaptation_config_dict: Default adaptation configuration dict"""
    pass
```

### Mock Manager Fixtures

```python
@pytest.mark.asyncio
async def test_something(mock_file_system):
    """mock_file_system: Real FileSystemManager instance with cleanup"""
    pass

@pytest.mark.asyncio
async def test_something(mock_metadata_index):
    """mock_metadata_index: Real MetadataIndex instance with cleanup"""
    pass
```

### Test Data Fixtures

```python
def test_something(sample_metadata_entry):
    """sample_metadata_entry: Example metadata entry dict"""
    pass

def test_something(sample_version_snapshot):
    """sample_version_snapshot: Example version snapshot dict"""
    pass
```

---

## Test Naming Conventions

### File Names

- Unit tests: `test_{module_name}.py`
- Integration tests: `test_{feature}_integration.py`
- Tool tests: `test_{phase}_tools.py`

### Class Names

- `Test{ClassName}` - Tests for a specific class
- `Test{ModuleName}` - Tests for module-level functions
- `Test{Feature}{Aspect}` - Tests for specific feature aspects

### Test Function Names

- `test_{behavior}_when_{condition}()`
- `test_{method}_returns_{result}_when_{condition}()`
- `test_{method}_raises_{error}_when_{condition}()`

### Examples

```python
# Good
def test_count_tokens_returns_zero_when_empty_string()
def test_validate_path_raises_error_when_path_traversal()
def test_parse_links_returns_empty_list_when_no_links()

# Bad
def test_count_tokens()  # Too vague
def test_validate()  # Missing behavior and condition
def test_edge_case()  # Not descriptive
```

---

## Test Markers

```python
@pytest.mark.unit
def test_unit_test():
    """Mark as unit test"""
    pass

@pytest.mark.integration
def test_integration_test():
    """Mark as integration test"""
    pass

@pytest.mark.slow
def test_slow_test():
    """Mark as slow test (can be skipped with -m "not slow")"""
    pass

@pytest.mark.asyncio
async def test_async_test():
    """Mark as async test"""
    pass
```

---

## Common Patterns

### Testing Exceptions

```python
def test_method_raises_specific_error():
    # Arrange
    instance = MyClass()

    # Act & Assert
    with pytest.raises(SpecificError) as exc_info:
        instance.method()

    # Verify error details
    assert exc_info.value.attribute == expected_value
    assert "expected message" in str(exc_info.value)
```

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_method(temp_project_root):
    # Arrange
    instance = MyClass(temp_project_root)

    # Act
    result = await instance.async_method()

    # Assert
    assert result is not None
```

### Testing File Operations

```python
def test_file_operation(temp_project_root):
    # Arrange
    file_path = temp_project_root / "test.md"
    content = "test content"

    # Act
    file_path.write_text(content)

    # Assert
    assert file_path.exists()
    assert file_path.read_text() == content
```

### Testing with Mocks (pytest-mock)

```python
def test_with_mock(mocker):
    # Arrange
    mock_method = mocker.patch('module.Class.method')
    mock_method.return_value = "mocked"

    # Act
    result = instance.method()

    # Assert
    assert result == "mocked"
    mock_method.assert_called_once()
```

---

## Utility Functions

```python
from tests.conftest import assert_file_exists, assert_file_contains, assert_json_valid

def test_with_utilities(temp_project_root):
    file_path = temp_project_root / "test.md"

    # Assert file exists (raises AssertionError if not)
    assert_file_exists(file_path, "Custom error message")

    # Assert file contains text
    assert_file_contains(file_path, "expected text")

    # Assert file is valid JSON
    json_path = temp_project_root / "test.json"
    assert_json_valid(json_path)
```

---

## Coverage Tips

### Measure Coverage for Specific Module

```bash
uv run --native-tls pytest tests/unit/test_exceptions.py --cov=src/cortex/exceptions
```

### Identify Missing Coverage

```bash
# Run with coverage
uv run --native-tls pytest tests/

# Open HTML report
open htmlcov/index.html

# Look for red lines (not covered)
# Add tests for those lines
```

### Coverage Goals

- **Phase 1 modules:** 95%+ coverage
- **Phase 2-6 modules:** 85-90% coverage
- **MCP tools:** 80%+ coverage
- **Overall:** 90%+ coverage

---

## Common Issues and Solutions

### Issue: Async fixtures not working

```python
# Wrong
def mock_file_system():
    pass

# Correct
@pytest.fixture
async def mock_file_system():
    pass
```

### Issue: Tests depend on each other

```python
# Wrong - shares state
class TestClass:
    instance = MyClass()  # Shared across tests

    def test_one(self):
        self.instance.modify()

# Correct - isolated
class TestClass:
    def test_one(self):
        instance = MyClass()  # New instance per test
        instance.modify()
```

### Issue: File paths not found

```python
# Wrong - relative paths
file_path = Path("test.md")

# Correct - use fixtures
def test_something(temp_project_root):
    file_path = temp_project_root / "test.md"
```

---

## Quick Checklist for New Tests

- [ ] Test file named `test_{module_name}.py`
- [ ] Imports use `from src.cortex...`
- [ ] Test classes named `Test{ClassName}`
- [ ] All tests use AAA pattern (Arrange-Act-Assert)
- [ ] Test names describe behavior and condition
- [ ] All tests have docstrings
- [ ] Async tests marked with `@pytest.mark.asyncio`
- [ ] Tests are isolated (no shared state)
- [ ] Fixtures used instead of manual setup
- [ ] All tests pass before committing

---

## Next Steps for Test Development

### Phase 1 Modules (Priority)

1. test_file_system.py (~40 tests)
2. test_metadata_index.py (~35 tests)
3. test_dependency_graph.py (~30 tests)
4. test_version_manager.py (~25 tests)
5. test_file_watcher.py (~20 tests)
6. test_migration.py (~30 tests)
7. test_graph_algorithms.py (~20 tests)

### Use This Template

1. Copy [test_exceptions.py](../tests/unit/test_exceptions.py) as starting point
2. Update module imports
3. Create test class for each class in module
4. Follow AAA pattern for all tests
5. Use fixtures from conftest.py
6. Run tests frequently during development
7. Aim for 95%+ coverage on Phase 1 modules

---

## Resources

- **Main Progress:** [phase-7.2-test-progress.md](phase-7.2-test-progress.md)
- **Completion Summary:** [phase-7.2-completion-summary.md](phase-7.2-completion-summary.md)
- **Fixtures:** [tests/conftest.py](../../tests/conftest.py)
- **Example Tests:** [tests/unit/test_exceptions.py](../../tests/unit/test_exceptions.py)
- **Pytest Docs:** <https://docs.pytest.org/>
- **Coverage Docs:** <https://coverage.readthedocs.io/>

---

**Last Updated:** December 21, 2025
**Status:** Infrastructure Complete ✅ | Ready for Development 🚀
