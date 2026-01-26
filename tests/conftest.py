"""
Pytest configuration and shared fixtures for MCP Memory Bank tests.

This module provides comprehensive fixtures for:
- Temporary project directories with proper cleanup
- Sample Memory Bank files with realistic content
- Mock managers and dependencies
- Configuration objects for all phases
- Test data for various scenarios
"""

import asyncio
import json
import tempfile
from collections.abc import Generator, ItemsView, KeysView, ValuesView
from datetime import datetime
from pathlib import Path

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.managers.types import ManagersDict
from cortex.optimization.relevance_scorer import RelevanceScorer
from tests.helpers.path_helpers import (
    ensure_test_cortex_structure,
    get_test_memory_bank_dir,
)

# ============================================================================
# Global Mocking for Integration Tests
# ============================================================================


@pytest.fixture(autouse=True, scope="session")
def make_pydantic_models_dict_like():
    """Make Pydantic models behave dict-like in tests.

    A large portion of the historical test suite treats return values as plain dicts.
    During the Phase 53 type-safety cleanup, many APIs were migrated to Pydantic
    models. To keep tests focused on semantics (not container type), we provide
    a thin dict-like shim for `pydantic.BaseModel` in the test runtime:
    - `model["key"]`
    - `"key" in model`
    - `model.get("key", default)`
    - `model.keys()/items()/values()`
    """
    from pydantic import BaseModel

    if not hasattr(BaseModel, "__getitem__"):

        def __getitem__(self: BaseModel, key: str) -> JsonValue:
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return data[key]

        def get(
            self: BaseModel, key: str, default: JsonValue | None = None
        ) -> JsonValue | None:
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return data.get(key, default)

        def __contains__(self: BaseModel, key: object) -> bool:
            if not isinstance(key, str):
                return False
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return key in data

        def keys(self: BaseModel) -> KeysView[str]:
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return data.keys()

        def items(self: BaseModel) -> ItemsView[str, JsonValue]:
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return data.items()

        def values(self: BaseModel) -> ValuesView[JsonValue]:
            data: ModelDict = self.model_dump(mode="python", by_alias=True)
            return data.values()

        BaseModel.__getitem__ = __getitem__  # type: ignore[method-assign]
        BaseModel.get = get  # type: ignore[method-assign]
        BaseModel.__contains__ = __contains__  # type: ignore[method-assign]
        BaseModel.keys = keys  # type: ignore[method-assign]
        BaseModel.items = items  # type: ignore[method-assign]
        BaseModel.values = values  # type: ignore[method-assign]

    yield


@pytest.fixture(autouse=True, scope="session")
def mock_tiktoken_globally():
    """
    Mock tiktoken.get_encoding to avoid network issues.

    This runs once at the start of the test session, before any tests.
    It prevents TokenCounter from trying to download encodings from the CDN.
    """
    from unittest.mock import Mock

    import tiktoken

    # Create a mock encoding that doesn't require network
    mock_encoding = Mock()
    mock_encoding.encode = lambda text: [1] * int(len(str(text).split()) * 1.3)  # type: ignore[misc]
    mock_encoding.n_vocab = 100000

    # Save original function
    original_get_encoding = tiktoken.get_encoding

    # Replace with mock that returns our mock encoding
    def mock_get_encoding(_name: str):
        return mock_encoding

    tiktoken.get_encoding = mock_get_encoding  # type: ignore[method-assign]

    yield

    # Restore original (though session ends after this)
    tiktoken.get_encoding = original_get_encoding  # type: ignore[method-assign]


# ============================================================================
# Project Directory Fixtures
# ============================================================================


@pytest.fixture
def temp_project_root() -> Generator[Path]:
    """
    Create a temporary project root directory for testing.

    Yields:
        Path: Temporary project root path with .cortex/memory-bank subdirectory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create .cortex directory structure using path resolver
        _ = ensure_test_cortex_structure(project_root)

        yield project_root


@pytest.fixture
def memory_bank_dir(temp_project_root: Path) -> Path:
    """
    Get the memory-bank directory path.

    Args:
        temp_project_root: Temporary project root fixture

    Returns:
        Path: memory-bank directory path
    """
    return get_test_memory_bank_dir(temp_project_root)


# ============================================================================
# Sample Memory Bank Files
# ============================================================================


@pytest.fixture
def sample_memory_bank_files(memory_bank_dir: Path) -> dict[str, Path]:
    """
    Create complete set of sample Memory Bank files.

    Creates all 7 standard memory bank files with realistic content.

    Args:
        memory_bank_dir: Memory bank directory fixture

    Returns:
        dict[str, Path]: Mapping of file names to paths
    """
    files = {
        "memorybankinstructions.md": """# Memory Bank Instructions

## Purpose
Instructions for using the Memory Bank system.

## Structure
- Project Brief: High-level project overview
- Active Context: Current work and priorities
- System Patterns: Architectural decisions and patterns

## Usage Guidelines
1. Keep files focused and concise
2. Update regularly
3. Link related information
""",
        "projectBrief.md": """# Project Brief

## Overview
MCP Memory Bank enhancement project.

## Goals
- Implement hybrid storage with metadata tracking
- Add DRY linking and transclusion
- Enable token optimization

## Key Features
- Version history
- Dependency tracking
- Content validation
""",
        "activeContext.md": """# Active Context

## Current Work
Phase 7: Code Quality Excellence

## Recent Changes
- Split main.py into modular structure
- Refactored oversized modules

## Next Steps
- Add comprehensive test coverage (90%+)
- Fix silent exception handlers
- Extract long functions
""",
        "systemPatterns.md": """# System Patterns

## Architecture
- Modular design with clear separation of concerns
- Async/await for all I/O operations
- Manager pattern for lifecycle management

## Design Decisions
- JSON for metadata storage
- Full snapshots for version history
- Watchdog for file monitoring
""",
        "techContext.md": """# Technical Context

## Stack
- Python 3.10+
- FastMCP for MCP protocol
- tiktoken for token counting
- watchdog for file monitoring

## Dependencies
- mcp: MCP protocol implementation
- aiofiles: Async file I/O
- tiktoken: Token counting
""",
        "productContext.md": """# Product Context

## Target Users
- AI assistants (Claude, GPT-4)
- Developers using AI coding tools

## Use Cases
- Project context management
- Knowledge persistence
- Conversation continuity
""",
        "progress.md": """# Progress Tracking

## Completed Phases
- ✅ Phase 1: Foundation
- ✅ Phase 2: DRY Linking
- ✅ Phase 3: Validation
- ✅ Phase 4: Optimization
- ✅ Phase 5: Self-Evolution
- ✅ Phase 6: Shared Rules
- 🚧 Phase 7: Code Quality (in progress)

## Current Sprint
Phase 7.2: Test Coverage (target: 90%+)
""",
    }

    file_paths: dict[str, Path] = {}
    for filename, content in files.items():
        file_path = memory_bank_dir / filename
        _ = file_path.write_text(content)
        file_paths[filename] = file_path

    return file_paths


@pytest.fixture
def sample_file_with_links(memory_bank_dir: Path) -> Path:
    """
    Create a sample file with markdown links for testing link parsing.

    Args:
        memory_bank_dir: Memory bank directory fixture

    Returns:
        Path: File path with links
    """
    content = """# Test File with Links

## Internal Links
See [Project Brief](projectBrief.md) for overview.
Check [Active Context](activeContext.md#current-work) for status.

## Transclusions
{{include: systemPatterns.md#architecture}}
{{include: techContext.md|lines=1-10}}

## External Links
- [Python Docs](https://docs.python.org/)
- [MCP Spec](https://modelcontextprotocol.io/)
"""

    file_path = memory_bank_dir / "test-links.md"
    _ = file_path.write_text(content)
    return file_path


# ============================================================================
# Rules and Configuration Fixtures
# ============================================================================


@pytest.fixture
def sample_rules_folder(temp_project_root: Path) -> Path:
    """
    Create a sample rules folder with multiple rule files.

    Args:
        temp_project_root: Temporary project root fixture

    Returns:
        Path: Rules folder path
    """
    rules_dir = temp_project_root / ".cursorrules"
    rules_dir.mkdir(exist_ok=True)

    # General rules
    _ = (rules_dir / "general.md").write_text(
        """# General Coding Rules

## Code Style
- Follow PEP 8 for Python
- Use type hints
- Write docstrings for all public functions
- Keep functions under 30 lines

## Testing
- Write tests for all new features
- Maintain 90%+ coverage
- Use AAA pattern (Arrange-Act-Assert)
"""
    )

    # Python-specific rules
    _ = (rules_dir / "python.md").write_text(
        """# Python Best Practices

## Async/Await
- Use async/await for I/O operations
- Use aiofiles for file operations
- Avoid blocking calls in async functions

## Error Handling
- Use custom exception hierarchy
- Provide meaningful error messages
- Log errors with context
"""
    )

    # Security rules
    _ = (rules_dir / "security.md").write_text(
        """# Security Guidelines

## Authentication
- Use JWT tokens for API auth
- Hash passwords with bcrypt
- Implement rate limiting

## Input Validation
- Validate all user input
- Sanitize file paths
- Check for path traversal attacks
"""
    )

    return rules_dir


@pytest.fixture
def optimization_config_dict() -> dict[str, object]:
    """
    Get default optimization configuration for testing.

    Returns:
        dict[str, object]: Default optimization config
    """
    return {
        "enabled": True,
        "token_budget": {
            "default_budget": 80000,
            "max_budget": 100000,
            "reserve_tokens": 5000,
        },
        "loading_strategies": {
            "default_strategy": "priority",
            "available_strategies": ["priority", "dependency", "relevance"],
        },
        "summarization": {
            "enabled": True,
            "default_strategy": "key_sections",
            "reduction_target": 0.5,
        },
        "rules": {
            "enabled": True,
            "rules_folder": ".cursorrules",
            "reindex_interval_minutes": 30,
            "max_rules_tokens": 5000,
            "min_relevance_score": 0.3,
            "auto_include": True,
        },
    }


@pytest.fixture
def validation_config_dict() -> dict[str, object]:
    """
    Get default validation configuration for testing.

    Returns:
        dict[str, object]: Default validation config
    """
    return {
        "enabled": True,
        "schemas": {
            "memorybankinstructions.md": {
                "required_sections": ["Purpose", "Structure"],
                "recommended_sections": ["Usage Guidelines"],
            },
            "projectBrief.md": {
                "required_sections": ["Overview", "Goals"],
                "recommended_sections": ["Key Features"],
            },
        },
        "duplication": {
            "enabled": True,
            "similarity_threshold": 0.85,
            "min_section_length": 100,
        },
        "token_budget": {
            "enabled": True,
            "max_total_tokens": 100000,
            "max_file_tokens": 20000,
            "warning_threshold": 0.8,
        },
    }


@pytest.fixture
def adaptation_config_dict() -> dict[str, object]:
    """
    Get default adaptation configuration for testing.

    Returns:
        dict[str, object]: Default adaptation config
    """
    return {
        "self_evolution": {
            "learning": {
                "enabled": True,
                "learning_rate": "moderate",
                "min_confidence_threshold": 0.6,
                "max_confidence_threshold": 0.9,
            },
            "pattern_tracking": {
                "enabled": True,
                "min_access_count": 3,
                "time_window_days": 30,
                "track_task_patterns": True,
            },
        },
    }


# ============================================================================
# Mock Manager Fixtures
# ============================================================================


@pytest.fixture
async def mock_file_system(temp_project_root: Path):
    """
    Create a real FileSystemManager instance for testing.

    Args:
        temp_project_root: Temporary project root fixture

    Yields:
        FileSystemManager: File system manager instance
    """
    from cortex.core.file_system import FileSystemManager

    fs_manager = FileSystemManager(temp_project_root)
    yield fs_manager

    # Cleanup would happen here if needed


@pytest.fixture
async def mock_metadata_index(temp_project_root: Path):
    """
    Create a real MetadataIndex instance for testing.

    Args:
        temp_project_root: Temporary project root fixture

    Returns:
        MetadataIndex: Metadata index instance
    """
    from cortex.core.metadata_index import MetadataIndex

    metadata = MetadataIndex(temp_project_root)
    _ = await metadata.load()
    yield metadata

    # Cleanup
    await metadata.save()


@pytest.fixture
def mock_link_parser():
    """
    Create a real LinkParser instance for testing.

    Returns:
        LinkParser: Link parser instance
    """
    from cortex.linking.link_parser import LinkParser

    parser = LinkParser()
    return parser


@pytest.fixture
def mock_dependency_graph():
    """
    Create a DependencyGraph instance for testing.

    Returns:
        DependencyGraph: Dependency graph instance
    """
    from cortex.core.dependency_graph import DependencyGraph

    graph = DependencyGraph()
    return graph


@pytest.fixture
def mock_token_counter():
    """
    Create a mocked TokenCounter that doesn't require network access.

    Returns a mock that estimates tokens as: len(text.split()) * 1.3
    This avoids the tiktoken CDN download issue while providing reasonable estimates.

    Returns:
        Mock TokenCounter instance
    """
    from unittest.mock import Mock

    mock = Mock()

    # Simple token estimation: words * 1.3 (rough approximation)
    def count_tokens_mock(text: str | None) -> int:
        if text is None or not text:
            return 0
        return int(len(text.split()) * 1.3)

    mock.count_tokens = count_tokens_mock

    def count_tokens_with_cache_mock(text: str | None, hash: str | None) -> int:
        return count_tokens_mock(text)

    mock.count_tokens_with_cache = count_tokens_with_cache_mock
    mock.clear_cache = Mock()
    mock.get_cache_size = Mock(return_value=0)

    return mock


@pytest.fixture
async def mock_relevance_scorer(
    mock_dependency_graph: "DependencyGraph", mock_metadata_index: "MetadataIndex"
):
    """
    Create a RelevanceScorer instance for testing.

    Args:
        mock_dependency_graph: Dependency graph fixture
        mock_metadata_index: Metadata index fixture

    Returns:
        RelevanceScorer: Relevance scorer instance
    """
    from cortex.optimization.relevance_scorer import RelevanceScorer

    scorer = RelevanceScorer(mock_dependency_graph, mock_metadata_index)
    return scorer


@pytest.fixture
async def mock_context_optimizer(
    mock_token_counter: "TokenCounter",
    mock_relevance_scorer: "RelevanceScorer",
    mock_dependency_graph: "DependencyGraph",
):
    """
    Create a ContextOptimizer instance for testing with mocked strategies.

    Args:
        mock_token_counter: Token counter fixture
        mock_relevance_scorer: Relevance scorer fixture
        mock_dependency_graph: Dependency graph fixture

    Returns:
        ContextOptimizer: Context optimizer instance with mocked strategies
    """
    from unittest.mock import AsyncMock

    from cortex.optimization.context_optimizer import ContextOptimizer
    from cortex.optimization.optimization_strategies import OptimizationResult

    optimizer = ContextOptimizer(
        mock_token_counter, mock_relevance_scorer, mock_dependency_graph
    )

    # Mock strategies methods
    mock_result = OptimizationResult(
        selected_files=["file1.md"],
        selected_sections={},
        total_tokens=500,
        utilization=0.5,
        excluded_files=["file2.md"],
        strategy_used="test",
        metadata={"test": True},
    )

    optimizer.strategies.optimize_by_priority = AsyncMock(return_value=mock_result)
    optimizer.strategies.optimize_by_dependencies = AsyncMock(return_value=mock_result)
    optimizer.strategies.optimize_with_sections = AsyncMock(return_value=mock_result)
    optimizer.strategies.optimize_hybrid = AsyncMock(return_value=mock_result)

    # Mock relevance scorer
    mock_relevance_scorer.score_files = AsyncMock(
        return_value={
            "file1.md": {"total_score": 0.8, "components": {}},
            "file2.md": {"total_score": 0.6, "components": {}},
        }
    )

    return optimizer


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_metadata_entry():
    """
    Get a sample metadata entry for testing.

    Returns:
        Dict: Sample metadata entry
    """
    return {
        "path": "memory-bank/projectBrief.md",
        "size": 1234,
        "token_count": 256,
        "content_hash": "abc123def456",
        "last_modified": datetime.now().isoformat(),
        "sections": [
            {"title": "Overview", "level": 2, "start_line": 1, "end_line": 5},
            {"title": "Goals", "level": 2, "start_line": 7, "end_line": 12},
        ],
        "links": [
            {"type": "markdown", "target": "activeContext.md", "line": 10},
        ],
        "dependencies": ["activeContext.md"],
    }


@pytest.fixture
def sample_version_snapshot():
    """
    Get a sample version snapshot for testing.

    Returns:
        Dict: Sample version snapshot
    """
    return {
        "version_id": "v[PAN3]",
        "timestamp": "2025-01-01T12:00:00",
        "content": "# Project Brief\n\nOld content here.",
        "content_hash": "old_hash_123",
        "metadata": {
            "size": 50,
            "token_count": 10,
        },
        "comment": "Before major update",
    }


@pytest.fixture
def sample_files_content():
    """
    Get sample files content for optimization testing.

    Returns:
        dict[str, str]: Mapping of file names to content
    """
    return {
        "file1.md": """# File 1

## Overview
This is a sample file for testing optimization.

## Details
Contains important information about the project.
""",
        "file2.md": """# File 2

## Introduction
Another sample file for testing.

## Content
More details here.
""",
        "file3.md": """# File 3

## Summary
A third file for comprehensive testing.
""",
    }


@pytest.fixture
def sample_files_metadata():
    """
    Get sample files metadata for optimization testing.

    Returns:
        dict[str, dict]: Mapping of file names to metadata
    """
    return {
        "file1.md": {
            "path": "memory-bank/file1.md",
            "size": 150,
            "token_count": 30,
            "content_hash": "hash1",
            "last_modified": "2025-01-01T12:00:00",
        },
        "file2.md": {
            "path": "memory-bank/file2.md",
            "size": 120,
            "token_count": 25,
            "content_hash": "hash2",
            "last_modified": "2025-01-01T13:00:00",
        },
        "file3.md": {
            "path": "memory-bank/file3.md",
            "size": 80,
            "token_count": 15,
            "content_hash": "hash3",
            "last_modified": "2025-01-01T14:00:00",
        },
    }


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config: object) -> None:  # type: ignore[type-arg]
    """Configure pytest with custom markers."""
    if hasattr(config, "addinivalue_line"):
        config.addinivalue_line(  # type: ignore[attr-defined]
            "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
        )
        config.addinivalue_line(  # type: ignore[attr-defined]
            "markers", "integration: marks tests as integration tests"
        )
        config.addinivalue_line(  # type: ignore[attr-defined]
            "markers", "unit: marks tests as unit tests"
        )


@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Set event loop policy for async tests.

    Returns:
        Event loop policy
    """
    return asyncio.get_event_loop_policy()


# ============================================================================
# Utility Functions for Tests
# ============================================================================


def assert_file_exists(file_path: Path, message: str | None = None) -> None:
    """
    Assert that a file exists.

    Args:
        file_path: Path to check
        message: Optional custom error message
    """
    if not file_path.exists():
        msg = message or f"Expected file does not exist: {file_path}"
        raise AssertionError(msg)


def assert_file_contains(
    file_path: Path, text: str, message: str | None = None
) -> None:
    """
    Assert that a file contains specific text.

    Args:
        file_path: Path to check
        text: Text to search for
        message: Optional custom error message
    """
    content = file_path.read_text()
    if text not in content:
        msg = message or f"File {file_path} does not contain: {text}"
        raise AssertionError(msg)


def assert_json_valid(json_path: Path, message: str | None = None) -> None:
    """
    Assert that a file contains valid JSON.

    Args:
        json_path: Path to JSON file
        message: Optional custom error message
    """
    try:
        json.loads(json_path.read_text())
    except json.JSONDecodeError as e:
        msg = message or f"Invalid JSON in {json_path}: {e}"
        raise AssertionError(msg) from e


# ============================================================================
# Additional Fixtures for Consolidated Tool Tests
# ============================================================================


@pytest.fixture
def temp_memory_bank(temp_project_root: Path) -> Path:
    """
    Get a temporary memory bank file path for testing.

    Args:
        temp_project_root: Temporary project root fixture

    Returns:
        Path: Path to a test file in memory-bank directory
    """
    memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
    return memory_bank_dir / "projectBrief.md"


@pytest.fixture
def mock_managers() -> ManagersDict:
    """
    Provide mock managers for testing tools.

    Returns:
        ManagersDict: Typed manager container with MagicMock defaults
    """
    from tests.helpers.managers import make_test_managers

    return make_test_managers()


@pytest.fixture
def mock_fs_manager():
    """
    Create a mock FileSystemManager for testing.

    Returns:
        Mock FileSystemManager instance with commonly used methods mocked
    """
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.construct_safe_path = MagicMock()
    mock.read_file = MagicMock()
    mock.write_file = MagicMock()
    return mock
