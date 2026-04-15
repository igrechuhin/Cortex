"""
Comprehensive tests for Phase 1: Foundation Tools

This test suite provides comprehensive coverage for:
- get_dependency_graph()
- get_version_history()
- rollback_file_version()
- get_memory_bank_stats()
- All helper functions and error paths
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.dependency_graph import FileDependencyInfo
from cortex.core.models import FileCategory
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.types import ManagersDict
from cortex.tools.memory.foundation_dependency import (
    get_dependency_graph,
    get_dependency_graph_resource,
)
from tests.helpers.managers import make_test_managers

# ============================================================================
# Fixtures
# ============================================================================

_METADATA_VERSION_HISTORY = [
    {
        "version": 3,
        "timestamp": "2026-01-10T10:00:00",
        "change_type": "update",
        "change_description": "Updated content",
        "size_bytes": 1024,
        "token_count": 256,
    },
    {
        "version": 2,
        "timestamp": "2026-01-09T10:00:00",
        "change_type": "rollback",
        "size_bytes": 512,
        "token_count": 128,
    },
    {
        "version": 1,
        "timestamp": "2026-01-08T10:00:00",
        "change_type": "create",
        "size_bytes": 256,
    },
]

_FILES_METADATA = {
    "projectBrief.md": {"token_count": 1000, "size_bytes": 4000, "read_count": 10},
    "activeContext.md": {"token_count": 500, "size_bytes": 2000, "read_count": 5},
}


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root with memory-bank directory."""
    memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_dependency_graph() -> MagicMock:
    """Create mock DependencyGraph."""
    mock = MagicMock()
    mock.static_deps = {
        "projectBrief.md": FileDependencyInfo(
            depends_on=[],
            priority=1,
            category=FileCategory.FOUNDATION,
        ),
        "activeContext.md": FileDependencyInfo(
            depends_on=["projectBrief.md"],
            priority=2,
            category=FileCategory.CONTEXT,
        ),
    }
    mock.compute_loading_order = MagicMock(
        return_value=["projectBrief.md", "activeContext.md"]
    )
    mock.to_mermaid = MagicMock(
        return_value="graph TD\n  projectBrief.md --> activeContext.md"
    )
    return mock


@pytest.fixture
def mock_metadata_index() -> MagicMock:
    """Create mock MetadataIndex."""
    mock = MagicMock()
    mock.get_file_metadata = AsyncMock(
        return_value={
            "current_version": 3,
            "version_history": _METADATA_VERSION_HISTORY,
        }
    )
    mock.get_all_files_metadata = AsyncMock(return_value=_FILES_METADATA)
    mock.get_stats = AsyncMock(
        return_value={
            "totals": {
                "last_full_scan": "2026-01-10T12:00:00",
                "total_files": 2,
            }
        }
    )
    mock.update_file_metadata = AsyncMock()
    mock.add_version_to_history = AsyncMock()
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def mock_version_manager() -> MagicMock:
    """Create mock VersionManager."""
    mock = MagicMock()
    mock.get_disk_usage = AsyncMock(return_value={"total_bytes": 10240})
    _mock_history = get_cortex_path(Path("/mock"), CortexResourceType.HISTORY)
    mock.get_snapshot_path = MagicMock(return_value=_mock_history / "test_v2.md")
    mock.get_snapshot_content = AsyncMock(return_value="# Old Content\n\nTest content")
    mock.create_snapshot = AsyncMock(
        return_value={
            "version": 4,
            "timestamp": "2026-01-10T11:00:00",
            "change_type": "rollback",
            "change_description": "Rolled back to version 2",
            "size_bytes": 512,
            "token_count": 128,
            "content_hash": "new_hash_123",
        }
    )
    return mock


@pytest.fixture
def mock_file_system_manager() -> MagicMock:
    """Create mock FileSystemManager."""
    mock = MagicMock()
    _mock_mb = get_cortex_path(Path("/mock"), CortexResourceType.MEMORY_BANK)
    mock.construct_safe_path = MagicMock(return_value=_mock_mb / "test.md")
    mock.write_file = AsyncMock(return_value="new_hash_123")
    mock.parse_sections = MagicMock(
        return_value=[
            {"title": "Section 1", "level": 1, "start_line": 1, "end_line": 3}
        ]
    )
    return mock


@pytest.fixture
def mock_token_counter() -> MagicMock:
    """Create mock TokenCounter."""
    mock = MagicMock()
    mock.count_tokens = MagicMock(return_value=128)
    return mock


@pytest.fixture
def mock_managers(
    mock_dependency_graph: MagicMock,
    mock_metadata_index: MagicMock,
    mock_version_manager: MagicMock,
    mock_file_system_manager: MagicMock,
    mock_token_counter: MagicMock,
) -> ManagersDict:
    """Create typed mock managers container."""
    return make_test_managers(
        graph=mock_dependency_graph,
        index=mock_metadata_index,
        versions=mock_version_manager,
        fs=mock_file_system_manager,
        tokens=mock_token_counter,
    )


# ============================================================================
# Test get_dependency_graph
# ============================================================================


@pytest.mark.asyncio
async def test_get_dependency_graph_success_json_format(
    mock_project_root: Path, mock_managers: ManagersDict
):
    """Test get_dependency_graph with JSON format returns correct structure."""
    # Arrange
    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.managers.initialization.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(format="json")

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["format"] == "json"
            assert "graph" in result_dict
            assert "loading_order" in result_dict
            # Check that expected files are in loading order (may include
            # additional files)
            loading_order = result_dict["loading_order"]
            assert "projectBrief.md" in loading_order
            assert "activeContext.md" in loading_order


@pytest.mark.asyncio
async def test_get_dependency_graph_success_mermaid_format(
    mock_project_root: Path, mock_managers: ManagersDict
):
    """Test get_dependency_graph with mermaid format returns diagram."""
    # Arrange
    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.managers.initialization.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(format="mermaid")

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["format"] == "mermaid"
            assert "diagram" in result_dict
            # Mermaid diagrams may use "flowchart TD" or "graph TD"
            diagram = result_dict["diagram"]
            assert "graph TD" in diagram or "flowchart TD" in diagram


@pytest.mark.asyncio
async def test_get_dependency_graph_error_handling(mock_project_root: Path):
    """Test get_dependency_graph handles exceptions correctly."""
    # Arrange - patch build_graph_data to raise an exception
    with patch(
        "cortex.tools.foundation_dependency.build_graph_data",
        side_effect=ValueError("Invalid project root"),
    ):
        # Act
        result = await get_dependency_graph(format="json")

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "error" in result_dict
        assert result_dict.get("error_type") == "ValueError"


@pytest.mark.asyncio
async def test_get_dependency_graph_default_project_root(mock_managers: ManagersDict):
    """Test get_dependency_graph resolves root via resolve_project_root_async."""
    # Arrange
    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=Path("/default/root"),
    ):
        with patch(
            "cortex.managers.initialization.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(format="json")

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"


@pytest.mark.asyncio
async def test_get_dependency_graph_resource_returns_json(
    mock_managers: ManagersDict,
):
    """Test get_dependency_graph_resource returns valid JSON (Phase 43 resource)."""
    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=Path("/default/root"),
    ):
        with patch(
            "cortex.managers.initialization.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            result = await get_dependency_graph_resource()
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert "graph" in result_dict or "format" in result_dict


# ============================================================================
# Test get_version_history, rollback_file_version, get_memory_bank_stats, helper
# functions, and context logging moved into dedicated split modules to keep
# this file under repository file-size limits.
