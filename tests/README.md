# Cortex Test Suite

This directory contains comprehensive tests for all phases of the Cortex project.

## Test Organization

### Phase Tests

- `test_core_modules.py` - Phase 1: Core infrastructure tests
- `test_phase2.py` - Phase 2: DRY linking and transclusion tests
- `test_phase3.py` - Phase 3: Validation and quality tests
- `test_phase4.py` - Phase 4: Token optimization tests

### Component Tests

- `test_managers.py` - Individual manager tests
- `test_each_manager.py` - Detailed manager tests
- `test_token.py` - Token counting tests
- `test_integration.py` - Integration tests

### Quick Tests

- `test_minimal.py` - Minimal smoke tests
- `test_simple.py` - Simple functionality tests
- `test_quick.py` - Quick validation tests
- `test_ultra_simple.py` - Ultra-minimal tests
- `test_init.py` - Initialization tests

## Running Tests

### Run all tests

```bash
uv run --native-tls python -m pytest tests/ -v
```

### Run specific phase tests

```bash
# Phase 1
uv run --native-tls python -m pytest tests/test_core_modules.py -v

# Phase 2
uv run --native-tls python -m pytest tests/test_phase2.py -v

# Phase 3
uv run --native-tls python -m pytest tests/test_phase3.py -v

# Phase 4
uv run --native-tls python -m pytest tests/test_phase4.py -v
```

### Run quick tests

```bash
uv run --native-tls python -m pytest tests/test_minimal.py -v
```

### Run with coverage

```bash
uv run --native-tls python -m pytest tests/ --cov=src/cortex --cov-report=html
```

## Test Requirements

Tests require the following packages:

- pytest
- pytest-asyncio
- pytest-cov (optional, for coverage)

These are included in the project's dev dependencies.

## Test Structure

Each test file follows this structure:

```python
"""
Test description
"""
import pytest

class TestFeatureName:
    """Test suite for feature."""

    @pytest.fixture
    def setup(self):
        """Setup fixture."""
        pass

    def test_something(self, setup):
        """Test something."""
        assert True
```

## Writing New Tests

When adding new features:

1. Create tests in the appropriate phase test file
2. Use descriptive test names (`test_feature_does_something`)
3. Use fixtures for common setup
4. Add docstrings explaining what's being tested
5. Test both success and failure cases

## Continuous Integration

Tests are run automatically on:

- Pull requests
- Pushes to main branch
- Release tags

## Test Coverage

Current coverage targets:

- Phase 1: >90%
- Phase 2: >85%
- Phase 3: >85%
- Phase 4: >80%

---

Last Updated: December 19, 2025
