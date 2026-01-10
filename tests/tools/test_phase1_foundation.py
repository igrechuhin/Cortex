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
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.dependency_graph import FileDependencyInfo
from cortex.tools.phase1_foundation import (
    get_dependency_graph,
    get_memory_bank_stats,
    get_version_history,
    rollback_file_version,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root with memory-bank directory."""
    memory_bank = tmp_path / "memory-bank"
    memory_bank.mkdir()
    return tmp_path


@pytest.fixture
def mock_dependency_graph() -> MagicMock:
    """Create mock DependencyGraph."""
    mock = MagicMock()
    mock.static_deps = {
        "projectBrief.md": {"priority": 1, "depends_on": set()},
        "activeContext.md": {"priority": 2, "depends_on": {"projectBrief.md"}},
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
            "version_history": [
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
            ],
        }
    )
    mock.get_all_files_metadata = AsyncMock(
        return_value={
            "projectBrief.md": {
                "token_count": 1000,
                "size_bytes": 4000,
                "read_count": 10,
            },
            "activeContext.md": {
                "token_count": 500,
                "size_bytes": 2000,
                "read_count": 5,
            },
        }
    )
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
    mock.get_snapshot_path = MagicMock(
        return_value=Path("/mock/.memory-bank-history/test.md/v2.md")
    )
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
    mock.construct_safe_path = MagicMock(return_value=Path("/mock/memory-bank/test.md"))
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
) -> dict[str, Any]:
    """Create mock managers dictionary."""
    return {
        "graph": mock_dependency_graph,
        "index": mock_metadata_index,
        "versions": mock_version_manager,
        "fs": mock_file_system_manager,
        "tokens": mock_token_counter,
    }


# ============================================================================
# Test get_dependency_graph
# ============================================================================


@pytest.mark.asyncio
async def test_get_dependency_graph_success_json_format(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_dependency_graph with JSON format returns correct structure."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(
                project_root=str(mock_project_root), format="json"
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["format"] == "json"
            assert "graph" in result_dict
            assert "loading_order" in result_dict
            assert result_dict["loading_order"] == [
                "projectBrief.md",
                "activeContext.md",
            ]


@pytest.mark.asyncio
async def test_get_dependency_graph_success_mermaid_format(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_dependency_graph with mermaid format returns diagram."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(
                project_root=str(mock_project_root), format="mermaid"
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["format"] == "mermaid"
            assert "diagram" in result_dict
            assert "graph TD" in result_dict["diagram"]


@pytest.mark.asyncio
async def test_get_dependency_graph_error_handling(mock_project_root: Path):
    """Test get_dependency_graph handles exceptions correctly."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        side_effect=ValueError("Invalid project root"),
    ):
        # Act
        result = await get_dependency_graph(project_root=str(mock_project_root))

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "error" in result_dict
        assert result_dict["error_type"] == "ValueError"


@pytest.mark.asyncio
async def test_get_dependency_graph_default_project_root(mock_managers: dict[str, Any]):
    """Test get_dependency_graph with None project_root uses default."""
    # Arrange
    with patch("cortex.tools.phase1_foundation.get_project_root") as mock_get_root:
        mock_get_root.return_value = Path("/default/root")
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_dependency_graph(project_root=None, format="json")

            # Assert
            mock_get_root.assert_called_once_with(None)
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"


# ============================================================================
# Test get_version_history
# ============================================================================


@pytest.mark.asyncio
async def test_get_version_history_success(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_version_history returns correct version list."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_version_history(
                file_name="test.md", project_root=str(mock_project_root), limit=10
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["file_name"] == "test.md"
            assert result_dict["total_versions"] == 3
            assert len(result_dict["versions"]) == 3
            # Verify sorted by version descending
            assert result_dict["versions"][0]["version"] == 3
            assert result_dict["versions"][1]["version"] == 2
            assert result_dict["versions"][2]["version"] == 1


@pytest.mark.asyncio
async def test_get_version_history_with_limit(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_version_history respects limit parameter."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_version_history(
                file_name="test.md", project_root=str(mock_project_root), limit=2
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["total_versions"] == 2
            assert len(result_dict["versions"]) == 2


@pytest.mark.asyncio
async def test_get_version_history_file_not_found(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_version_history handles file not found."""
    # Arrange
    mock_managers["index"].get_file_metadata = AsyncMock(return_value=None)
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_version_history(
                file_name="nonexistent.md", project_root=str(mock_project_root)
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "error"
            assert "not found" in result_dict["error"]


@pytest.mark.asyncio
async def test_get_version_history_error_handling(mock_project_root: Path):
    """Test get_version_history handles exceptions."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        side_effect=RuntimeError("Test error"),
    ):
        # Act
        result = await get_version_history(
            file_name="test.md", project_root=str(mock_project_root)
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_get_version_history_invalid_version_history_format(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_version_history handles invalid version_history format."""
    # Arrange
    mock_managers["index"].get_file_metadata = AsyncMock(
        return_value={"version_history": "not a list"}
    )
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_version_history(
                file_name="test.md", project_root=str(mock_project_root)
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["total_versions"] == 0


@pytest.mark.asyncio
async def test_get_version_history_missing_optional_fields(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_version_history handles missing optional fields."""
    # Arrange
    mock_managers["index"].get_file_metadata = AsyncMock(
        return_value={
            "version_history": [
                {
                    "version": 1,
                    "timestamp": "2026-01-08T10:00:00",
                    "change_type": "create",
                }
            ]
        }
    )
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_version_history(
                file_name="test.md", project_root=str(mock_project_root)
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            versions = result_dict["versions"]
            assert len(versions) == 1
            assert "change_description" not in versions[0]
            assert "size_bytes" not in versions[0]
            assert "token_count" not in versions[0]


# ============================================================================
# Test rollback_file_version
# ============================================================================


@pytest.mark.asyncio
async def test_rollback_file_version_success(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test rollback_file_version successfully rolls back file."""
    # Arrange
    snapshot_path = mock_project_root / ".memory-bank-history/test.md/v2.md"
    _ = snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    _ = snapshot_path.write_text("# Old Content\n\nTest content")

    mock_managers["versions"].get_snapshot_path.return_value = snapshot_path

    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await rollback_file_version(
                file_name="test.md", version=2, project_root=str(mock_project_root)
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["file_name"] == "test.md"
            assert result_dict["rolled_back_from_version"] == 2
            assert result_dict["new_version"] == 4
            assert result_dict["token_count"] == 128


@pytest.mark.asyncio
async def test_rollback_file_version_invalid_file_name(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test rollback_file_version handles invalid file name."""
    # Arrange
    mock_managers["fs"].construct_safe_path = MagicMock(
        side_effect=ValueError("Invalid file name")
    )
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await rollback_file_version(
                file_name="../../../etc/passwd",
                version=1,
                project_root=str(mock_project_root),
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "error"
            assert "Invalid file name" in result_dict["error"]


@pytest.mark.asyncio
async def test_rollback_file_version_snapshot_not_found(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test rollback_file_version handles missing snapshot."""
    # Arrange
    nonexistent_path = mock_project_root / ".memory-bank-history/test.md/v99.md"
    mock_managers["versions"].get_snapshot_path.return_value = nonexistent_path

    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await rollback_file_version(
                file_name="test.md", version=99, project_root=str(mock_project_root)
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "error"
            assert "not found" in result_dict["error"]


@pytest.mark.asyncio
async def test_rollback_file_version_error_handling(mock_project_root: Path):
    """Test rollback_file_version handles exceptions."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        side_effect=RuntimeError("Test error"),
    ):
        # Act
        result = await rollback_file_version(
            file_name="test.md", version=1, project_root=str(mock_project_root)
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["error_type"] == "RuntimeError"


# ============================================================================
# Test get_memory_bank_stats
# ============================================================================


@pytest.mark.asyncio
async def test_get_memory_bank_stats_success_basic(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_memory_bank_stats returns basic statistics."""
    # Arrange
    # Create history directory so disk usage check works
    history_dir = mock_project_root / ".memory-bank-history"
    history_dir.mkdir(exist_ok=True)

    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_memory_bank_stats(
                project_root=str(mock_project_root),
                include_token_budget=False,
                include_refactoring_history=False,
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert "summary" in result_dict
            assert result_dict["summary"]["total_files"] == 2
            assert result_dict["summary"]["total_tokens"] == 1500
            assert result_dict["summary"]["total_size_bytes"] == 6000
            assert result_dict["summary"]["total_reads"] == 15
            assert result_dict["summary"]["history_size_bytes"] == 10240


@pytest.mark.asyncio
async def test_get_memory_bank_stats_with_token_budget(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_memory_bank_stats includes token budget analysis."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_memory_bank_stats(
                project_root=str(mock_project_root),
                include_token_budget=True,
                include_refactoring_history=False,
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert "token_budget" in result_dict
            token_budget = result_dict["token_budget"]
            assert "status" in token_budget
            assert "total_tokens" in token_budget
            assert "max_tokens" in token_budget
            assert "remaining_tokens" in token_budget
            assert "usage_percentage" in token_budget


@pytest.mark.asyncio
async def test_get_memory_bank_stats_with_refactoring_history(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_memory_bank_stats includes refactoring history."""
    # Arrange
    mock_refactoring_executor = MagicMock()
    mock_refactoring_executor.get_execution_history = AsyncMock(
        return_value={
            "total_refactorings": 5,
            "successful": 4,
            "rolled_back": 1,
        }
    )
    mock_managers["refactoring_executor"] = mock_refactoring_executor

    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_memory_bank_stats(
                project_root=str(mock_project_root),
                include_token_budget=False,
                include_refactoring_history=True,
                refactoring_days=30,
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert "refactoring_history" in result_dict
            assert result_dict["refactoring_history"]["total_refactorings"] == 5


@pytest.mark.asyncio
async def test_get_memory_bank_stats_refactoring_executor_unavailable(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_memory_bank_stats handles missing refactoring executor."""
    # Arrange
    # Don't add refactoring_executor to managers
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_memory_bank_stats(
                project_root=str(mock_project_root),
                include_token_budget=False,
                include_refactoring_history=True,
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert "refactoring_history" in result_dict
            assert result_dict["refactoring_history"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_get_memory_bank_stats_error_handling(mock_project_root: Path):
    """Test get_memory_bank_stats handles exceptions."""
    # Arrange
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        side_effect=RuntimeError("Test error"),
    ):
        # Act
        result = await get_memory_bank_stats(project_root=str(mock_project_root))

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_get_memory_bank_stats_empty_metadata(
    mock_project_root: Path, mock_managers: dict[str, Any]
):
    """Test get_memory_bank_stats handles empty metadata."""
    # Arrange
    mock_managers["index"].get_all_files_metadata = AsyncMock(return_value={})
    with patch(
        "cortex.tools.phase1_foundation.get_project_root",
        return_value=mock_project_root,
    ):
        with patch(
            "cortex.tools.phase1_foundation.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ):
            # Act
            result = await get_memory_bank_stats(
                project_root=str(mock_project_root), include_token_budget=False
            )

            # Assert
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["summary"]["total_files"] == 0
            assert result_dict["summary"]["total_tokens"] == 0


# ============================================================================
# Test Helper Functions
# ============================================================================


def test_build_graph_data_with_dependencies():
    """Test _build_graph_data helper constructs correct graph structure."""
    # Arrange
    from cortex.tools.phase1_foundation import build_graph_data

    static_deps: dict[str, FileDependencyInfo] = {
        "projectBrief.md": {"priority": 1, "depends_on": [], "category": "core"},
        "activeContext.md": {
            "priority": 2,
            "depends_on": ["projectBrief.md"],
            "category": "context",
        },
    }

    # Act
    result = build_graph_data(static_deps)

    # Assert
    assert "files" in result
    files = cast(dict[str, object], result["files"])
    assert "projectBrief.md" in files
    projectBrief = cast(dict[str, object], files["projectBrief.md"])
    assert projectBrief["priority"] == 1
    assert projectBrief["dependencies"] == []
    assert "activeContext.md" in files
    active_context = cast(dict[str, object], files["activeContext.md"])
    assert active_context["priority"] == 2
    dependencies = cast(list[object], active_context["dependencies"])
    assert "projectBrief.md" in dependencies


def testextract_version_history_valid_list():
    """Test extract_version_history with valid version list."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_version_history

    file_meta = {
        "version_history": [
            {"version": 1, "timestamp": "2026-01-10T10:00:00"},
            {"version": 2, "timestamp": "2026-01-10T11:00:00"},
        ]
    }

    # Act
    result = extract_version_history(cast(dict[str, object], file_meta))

    # Assert
    assert len(result) == 2
    assert result[0]["version"] == 1
    assert result[1]["version"] == 2


def testextract_version_history_invalid_format():
    """Test extract_version_history handles invalid format."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_version_history

    file_meta = {"version_history": "not a list"}

    # Act
    result = extract_version_history(cast(dict[str, object], file_meta))

    # Assert
    assert result == []


def testextract_version_history_missing_field():
    """Test extract_version_history handles missing version_history field."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_version_history

    file_meta = {}

    # Act
    result = extract_version_history(cast(dict[str, object], file_meta))

    # Assert
    assert result == []


def testsort_and_limit_versions():
    """Test sort_and_limit_versions sorts and limits correctly."""
    # Arrange
    from cortex.tools.phase1_foundation import sort_and_limit_versions

    versions = [
        {"version": 1},
        {"version": 3},
        {"version": 2},
    ]

    # Act
    result = sort_and_limit_versions(cast(list[dict[str, object]], versions), limit=2)

    # Assert
    assert len(result) == 2
    assert result[0]["version"] == 3
    assert result[1]["version"] == 2


def testsort_and_limit_versions_with_float_versions():
    """Test sort_and_limit_versions handles float version numbers."""
    # Arrange
    from cortex.tools.phase1_foundation import sort_and_limit_versions

    versions = [
        {"version": 1.5},
        {"version": 3.2},
        {"version": 2.1},
    ]

    # Act
    result = sort_and_limit_versions(cast(list[dict[str, object]], versions), limit=10)

    # Assert
    assert len(result) == 3
    assert result[0]["version"] == 3.2
    assert result[1]["version"] == 2.1
    assert result[2]["version"] == 1.5


def testsort_and_limit_versions_with_missing_version():
    """Test sort_and_limit_versions handles missing version field."""
    # Arrange
    from cortex.tools.phase1_foundation import sort_and_limit_versions

    versions = [
        {"version": 2},
        {},  # Missing version
        {"version": 1},
    ]

    # Act
    result = sort_and_limit_versions(cast(list[dict[str, object]], versions), limit=10)

    # Assert
    assert len(result) == 3
    assert result[0]["version"] == 2
    assert result[1]["version"] == 1


def testformat_versions_for_export_all_fields():
    """Test format_versions_for_export includes all fields."""
    # Arrange
    from cortex.tools.phase1_foundation import format_versions_for_export

    versions = [
        {
            "version": 1,
            "timestamp": "2026-01-10T10:00:00",
            "change_type": "create",
            "change_description": "Initial version",
            "size_bytes": 1024,
            "token_count": 256,
        }
    ]

    # Act
    result = format_versions_for_export(cast(list[dict[str, object]], versions))

    # Assert
    assert len(result) == 1
    version_dict = result[0]
    assert version_dict["version"] == 1
    assert version_dict["timestamp"] == "2026-01-10T10:00:00"
    assert version_dict["change_type"] == "create"
    assert version_dict["change_description"] == "Initial version"
    assert version_dict["size_bytes"] == 1024
    assert version_dict["token_count"] == 256


def testformat_versions_for_export_minimal_fields():
    """Test format_versions_for_export with minimal fields."""
    # Arrange
    from cortex.tools.phase1_foundation import format_versions_for_export

    versions = [{"version": 1, "timestamp": "2026-01-10T10:00:00"}]

    # Act
    result = format_versions_for_export(cast(list[dict[str, object]], versions))

    # Assert
    assert len(result) == 1
    version_dict = result[0]
    assert version_dict["version"] == 1
    assert version_dict["timestamp"] == "2026-01-10T10:00:00"
    assert version_dict["change_type"] == "unknown"
    assert "change_description" not in version_dict


def testsum_file_field():
    """Test sum_file_field sums numeric fields correctly."""
    # Arrange
    from cortex.tools.phase1_foundation import sum_file_field

    files_metadata = {
        "file1.md": {"token_count": 100, "size_bytes": 400},
        "file2.md": {"token_count": 200, "size_bytes": 800},
    }

    # Act
    total_tokens = sum_file_field(
        cast(dict[str, dict[str, object]], files_metadata), "token_count"
    )
    total_size = sum_file_field(
        cast(dict[str, dict[str, object]], files_metadata), "size_bytes"
    )

    # Assert
    assert total_tokens == 300
    assert total_size == 1200


def testsum_file_field_missing_field():
    """Test sum_file_field handles missing fields."""
    # Arrange
    from cortex.tools.phase1_foundation import sum_file_field

    files_metadata = {
        "file1.md": {"token_count": 100},
        "file2.md": {},
    }

    # Act
    result = sum_file_field(
        cast(dict[str, dict[str, object]], files_metadata), "token_count"
    )

    # Assert
    assert result == 100


def testsum_file_field_non_numeric():
    """Test sum_file_field ignores non-numeric values."""
    # Arrange
    from cortex.tools.phase1_foundation import sum_file_field

    files_metadata = {
        "file1.md": {"token_count": 100},
        "file2.md": {"token_count": "not a number"},
    }

    # Act
    result = sum_file_field(
        cast(dict[str, dict[str, object]], files_metadata), "token_count"
    )

    # Assert
    assert result == 100


def testextract_last_updated_success():
    """Test extract_last_updated extracts timestamp."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_last_updated

    index_stats = {"totals": {"last_full_scan": "2026-01-10T12:00:00"}}

    # Act
    result = extract_last_updated(cast(dict[str, object], index_stats))

    # Assert
    assert result == "2026-01-10T12:00:00"


def testextract_last_updated_missing_field():
    """Test extract_last_updated handles missing field."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_last_updated

    index_stats: dict[str, object] = {"totals": {}}

    # Act
    result = extract_last_updated(index_stats)

    # Assert
    assert result is None


def testextract_last_updated_invalid_structure():
    """Test extract_last_updated handles invalid structure."""
    # Arrange
    from cortex.tools.phase1_foundation import extract_last_updated

    index_stats = {"totals": "not a dict"}

    # Act
    result = extract_last_updated(cast(dict[str, object], index_stats))

    # Assert
    assert result is None


def testbuild_summary_dict():
    """Test build_summary_dict constructs correct summary."""
    # Arrange
    from cortex.tools.phase1_foundation import build_summary_dict

    files_metadata = {
        "file1.md": {"token_count": 100},
        "file2.md": {"token_count": 200},
    }

    # Act
    result = build_summary_dict(
        cast(dict[str, dict[str, object]], files_metadata),
        total_tokens=300,
        total_size=1024,
        total_reads=10,
        history_size=2048,
    )

    # Assert
    assert result["total_files"] == 2
    assert result["total_tokens"] == 300
    assert result["total_size_bytes"] == 1024
    assert result["total_size_kb"] == 1.0
    assert result["total_reads"] == 10
    assert result["history_size_bytes"] == 2048
    assert result["history_size_kb"] == 2.0


def testcalculate_token_status_healthy():
    """Test calculate_token_status returns healthy status."""
    # Arrange
    from cortex.tools.phase1_foundation import calculate_token_status

    # Act
    result = calculate_token_status(
        total_tokens=5000, max_tokens=10000, warn_threshold=80.0
    )

    # Assert
    assert result == "healthy"


def testcalculate_token_status_warning():
    """Test calculate_token_status returns warning status."""
    # Arrange
    from cortex.tools.phase1_foundation import calculate_token_status

    # Act
    result = calculate_token_status(
        total_tokens=8500, max_tokens=10000, warn_threshold=80.0
    )

    # Assert
    assert result == "warning"


def testcalculate_token_status_over_budget():
    """Test calculate_token_status returns over_budget status."""
    # Arrange
    from cortex.tools.phase1_foundation import calculate_token_status

    # Act
    result = calculate_token_status(
        total_tokens=10500, max_tokens=10000, warn_threshold=80.0
    )

    # Assert
    assert result == "over_budget"


def testcalculate_totals():
    """Test calculate_totals computes correct totals."""
    # Arrange
    from cortex.tools.phase1_foundation import calculate_totals

    files_metadata = {
        "file1.md": {"token_count": 100, "size_bytes": 400, "read_count": 5},
        "file2.md": {"token_count": 200, "size_bytes": 800, "read_count": 10},
    }

    # Act
    total_tokens, total_size, total_reads = calculate_totals(
        cast(dict[str, dict[str, object]], files_metadata)
    )

    # Assert
    assert total_tokens == 300
    assert total_size == 1200
    assert total_reads == 15


def testbuild_rollback_success_response():
    """Test build_rollback_success_response constructs correct response."""
    # Arrange
    from cortex.tools.phase1_foundation import (
        build_rollback_success_response,
    )

    # Act
    result = build_rollback_success_response(
        file_name="test.md",
        rolled_back_from_version=2,
        new_version=4,
        token_count=128,
    )

    # Assert
    assert result["status"] == "success"
    assert result["file_name"] == "test.md"
    assert result["rolled_back_from_version"] == 2
    assert result["new_version"] == 4
    assert result["token_count"] == 128


def testbuild_rollback_error_response():
    """Test build_rollback_error_response constructs correct response."""
    # Arrange
    from cortex.tools.phase1_foundation import build_rollback_error_response

    # Act
    result = build_rollback_error_response("Test error", "ValueError")

    # Assert
    assert result["status"] == "error"
    assert result["error"] == "Test error"
    assert result["error_type"] == "ValueError"
