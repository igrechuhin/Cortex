"""
Comprehensive tests for Phase 2: Link Management Tools

This test suite provides comprehensive coverage for:
- parse_file_links()
- resolve_transclusions()
- validate_links()
- get_link_graph()
- All helper functions and error paths
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
)
from cortex.managers.types import ManagersDict
from cortex.tools.phase2_linking import (
    get_link_graph,
    parse_file_links,
    resolve_transclusions,
    validate_links,
)
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import get_test_memory_bank_dir

# ============================================================================
# Helper Functions
# ============================================================================


def _get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
    """Helper function to get manager by field name."""
    return getattr(mgrs, key)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root with memory-bank directory."""
    from tests.helpers.path_helpers import ensure_test_cortex_structure

    _ = ensure_test_cortex_structure(tmp_path)
    return tmp_path


@pytest.fixture
def mock_parsed_links() -> dict[str, list[dict[str, Any]]]:
    """Create mock parsed links result."""
    return {
        "markdown_links": [
            {"text": "link1", "target": "file1.md", "section": None},
            {"text": "link2", "target": "file2.md", "section": "Section 1"},
        ],
        "transclusions": [
            {"target": "file3.md", "section": None, "options": {}},
        ],
    }


@pytest.fixture
def mock_managers(
    mock_parsed_links: dict[str, list[dict[str, Any]]],
) -> ManagersDict:
    """Create typed mock managers container."""
    fs_manager = MagicMock()
    fs_manager.read_file = AsyncMock(return_value=("Test content", None))
    fs_manager.construct_safe_path = MagicMock(
        return_value=Path("/mock/.cortex/memory-bank/test.md")
    )

    link_parser = MagicMock()
    link_parser.parse_file = AsyncMock(return_value=mock_parsed_links)
    link_parser.has_transclusions = MagicMock(return_value=True)

    transclusion_engine = MagicMock()
    transclusion_engine.resolve_content = AsyncMock(
        return_value="Resolved content with transclusions"
    )
    transclusion_engine.get_cache_stats = MagicMock(
        return_value={"hits": 5, "misses": 2, "entries": 3}
    )
    transclusion_engine.max_depth = 5

    link_validator = MagicMock()
    link_validator.validate_file = AsyncMock(
        return_value={
            "valid_links": [{"target": "file1.md"}],
            "broken_links": [],
            "warnings": [],
        }
    )
    link_validator.validate_all = AsyncMock(
        return_value={
            "files_checked": 5,
            "total_links": 10,
            "valid_links": 8,
            "broken_links": 2,
            "warnings": 1,
            "validation_errors": [],
            "validation_warnings": [],
        }
    )
    link_validator.generate_report = MagicMock(return_value="Validation report")

    dependency_graph = MagicMock()
    dependency_graph.build_from_links = AsyncMock()
    dependency_graph.detect_cycles = MagicMock(return_value=[])
    dependency_graph.to_dict = MagicMock(
        return_value=MagicMock(
            model_dump=MagicMock(
                return_value={"nodes": ["file1.md", "file2.md"], "edges": []}
            )
        )
    )
    dependency_graph.get_reference_graph = MagicMock(
        return_value=MagicMock(
            model_dump=MagicMock(return_value={"nodes": ["file1.md"], "edges": []})
        )
    )
    dependency_graph.to_mermaid = MagicMock(return_value="graph TD\nA-->B")
    dependency_graph.get_all_files = MagicMock(return_value=["file1.md", "file2.md"])
    dependency_graph.link_types = {
        "file1.md": {"file2.md": "reference"},
        "file2.md": {"file3.md": "transclusion"},
    }

    return make_test_managers(
        fs=fs_manager,
        graph=dependency_graph,
        link_parser=link_parser,
        transclusion=transclusion_engine,
        link_validator=link_validator,
    )


# ============================================================================
# Test parse_file_links()
# ============================================================================


class TestParseFileLinks:
    """Tests for parse_file_links() tool."""

    async def test_parse_file_links_success(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test successful link parsing."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_parser_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await parse_file_links(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["file"] == "test.md"
            assert "markdown_links" in result
            assert "transclusions" in result
            assert "summary" in result
            assert result["summary"]["markdown_links"] == 2
            assert result["summary"]["transclusions"] == 1

    async def test_parse_file_links_invalid_path(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test parsing with invalid file path."""
        # Arrange
        mock_managers.fs.construct_safe_path.side_effect = ValueError("Invalid path")  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_parser_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await parse_file_links(file_name="../evil.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid file name" in result["error"]

    async def test_parse_file_links_not_found(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test parsing when file doesn't exist."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "nonexistent.md"
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_parser_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await parse_file_links(file_name="nonexistent.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not found" in result["error"]

    async def test_parse_file_links_exception(self, mock_project_root: Path) -> None:
        """Test exception handling in parse_file_links."""
        # Arrange
        with patch(
            "cortex.tools.link_parser_operations.get_project_root",
            side_effect=RuntimeError("Test error"),
        ):
            # Act
            result_str = await parse_file_links(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Test error" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Test resolve_transclusions()
# ============================================================================


class TestResolveTransclusions:
    """Tests for resolve_transclusions() tool."""

    async def test_resolve_transclusions_success(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test successful transclusion resolution."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["file"] == "test.md"
            assert "original_content" in result
            assert "resolved_content" in result
            assert result["has_transclusions"] is True
            assert "cache_stats" in result

    async def test_resolve_transclusions_no_transclusions(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test resolution when file has no transclusions."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]
        mock_managers.link_parser.has_transclusions.return_value = False  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["has_transclusions"] is False
            assert "No transclusions found" in result["message"]

    async def test_resolve_transclusions_circular_dependency(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test circular dependency detection."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]
        mock_managers.transclusion.resolve_content.side_effect = (  # type: ignore[attr-defined]
            CircularDependencyError(
                "Circular dependency detected: a.md -> b.md -> a.md"
            )
        )

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert result["error_type"] == "CircularDependencyError"
            assert "Circular transclusion detected" in result["message"]

    async def test_resolve_transclusions_max_depth_exceeded(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test max depth exceeded error."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]
        mock_managers.transclusion.resolve_content.side_effect = MaxDepthExceededError(  # type: ignore[attr-defined]
            "Maximum transclusion depth (5) exceeded"
        )

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="test.md", max_depth=5)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert result["error_type"] == "MaxDepthExceededError"
            assert "Maximum transclusion depth (5) exceeded" in result["message"]

    async def test_resolve_transclusions_custom_max_depth(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test resolution with custom max depth."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="test.md", max_depth=10)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Verify max_depth was set
            assert mock_managers.transclusion.max_depth == 10  # type: ignore[attr-defined]

    async def test_resolve_transclusions_invalid_file(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test resolution with invalid file name."""
        # Arrange
        mock_managers.fs.construct_safe_path.side_effect = ValueError("Invalid path")  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="../evil.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid file name" in result["error"]

    async def test_resolve_transclusions_file_not_found(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test resolution when file doesn't exist."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "nonexistent.md"
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await resolve_transclusions(file_name="nonexistent.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not found" in result["error"]


# ============================================================================
# Test validate_links()
# ============================================================================


class TestValidateLinks:
    """Tests for validate_links() tool."""

    async def test_validate_links_single_file(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test validating links in a single file."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await validate_links(file_name="test.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["mode"] == "single_file"
            assert "valid_links" in result
            assert "broken_links" in result

    async def test_validate_links_all_files(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test validating links in all files."""
        # Arrange
        with (
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await validate_links()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["mode"] == "all_files"
            assert result["files_checked"] == 5
            assert result["total_links"] == 10
            assert "report" in result

    async def test_validate_links_invalid_file_path(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test validation with invalid file path."""
        # Arrange
        mock_managers.fs.construct_safe_path.side_effect = ValueError("Invalid path")  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await validate_links(file_name="../evil.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid file name" in result["error"]

    async def test_validate_links_file_not_found(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test validation when file doesn't exist."""
        # Arrange
        file_path = get_test_memory_bank_dir(mock_project_root) / "nonexistent.md"
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act
            result_str = await validate_links(file_name="nonexistent.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "not found" in result["error"]

    async def test_validate_links_exception(self, mock_project_root: Path) -> None:
        """Test exception handling in validate_links."""
        # Arrange
        with patch(
            "cortex.tools.link_validation_operations.get_project_root",
            side_effect=RuntimeError("Validation failed"),
        ):
            # Act
            result_str = await validate_links()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Validation failed" in result["error"]


# ============================================================================
# Test get_link_graph()
# ============================================================================


class TestGetLinkGraph:
    """Tests for get_link_graph() tool."""

    async def test_get_link_graph_json_format(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test link graph in JSON format."""
        # Arrange
        with (
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_link_graph(format="json")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["format"] == "json"
            assert "nodes" in result
            assert "edges" in result
            assert "cycles" in result
            assert "summary" in result
            assert result["summary"]["total_files"] == 2

    async def test_get_link_graph_mermaid_format(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test link graph in Mermaid format."""
        # Arrange
        with (
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_link_graph(format="mermaid")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["format"] == "mermaid"
            assert "diagram" in result
            assert "cycles" in result
            assert "graph TD" in result["diagram"]

    async def test_get_link_graph_without_transclusions(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test link graph excluding transclusion links."""
        # Arrange
        with (
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_link_graph(include_transclusions=False)
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Verify get_reference_graph was called instead of to_dict
            mock_managers.graph.get_reference_graph.assert_called_once()  # type: ignore[attr-defined]

    async def test_get_link_graph_with_cycles(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test link graph with circular dependencies."""
        # Arrange
        mock_managers.graph.detect_cycles.return_value = [  # type: ignore[attr-defined]
            ["file1.md", "file2.md", "file1.md"]
        ]

        with (
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_link_graph()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert len(result["cycles"]) > 0
            assert result["summary"]["has_cycles"] is True
            assert result["summary"]["cycle_count"] == 1

    async def test_get_link_graph_summary_stats(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test link graph summary statistics."""
        # Arrange
        with (
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_link_graph()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            summary = result["summary"]
            assert "total_files" in summary
            assert "total_links" in summary
            assert "reference_links" in summary
            assert "transclusion_links" in summary
            assert summary["reference_links"] == 1  # file1->file2
            assert summary["transclusion_links"] == 1  # file2->file3

    async def test_get_link_graph_exception(self, mock_project_root: Path) -> None:
        """Test exception handling in get_link_graph."""
        # Arrange
        with patch(
            "cortex.tools.link_graph_operations.get_project_root",
            side_effect=RuntimeError("Graph build failed"),
        ):
            # Act
            result_str = await get_link_graph()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Graph build failed" in result["error"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for Phase 2 linking workflows."""

    async def test_full_linking_workflow(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test complete workflow: parse -> resolve -> validate -> graph."""
        file_path = get_test_memory_bank_dir(mock_project_root) / "test.md"
        file_path.touch()
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_parser_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_graph_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act 1: Parse links
            parse_result = await parse_file_links(file_name="test.md")
            parse_data = json.loads(parse_result)

            # Assert 1
            assert parse_data["status"] == "success"
            assert parse_data["summary"]["total"] > 0

            # Act 2: Resolve transclusions
            resolve_result = await resolve_transclusions(file_name="test.md")
            resolve_data = json.loads(resolve_result)

            # Assert 2
            assert resolve_data["status"] == "success"
            assert resolve_data["has_transclusions"] is True

            # Act 3: Validate links
            validate_result = await validate_links(file_name="test.md")
            validate_data = json.loads(validate_result)

            # Assert 3
            assert validate_data["status"] == "success"

            # Act 4: Get link graph
            graph_result = await get_link_graph()
            graph_data = json.loads(graph_result)

            # Assert 4
            assert graph_data["status"] == "success"
            assert "summary" in graph_data

    async def test_error_handling_workflow(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """Test error handling across multiple operations."""
        # Arrange - simulate file not found
        file_path = get_test_memory_bank_dir(mock_project_root) / "missing.md"
        mock_managers.fs.construct_safe_path.return_value = file_path  # type: ignore[attr-defined]

        with (
            patch(
                "cortex.tools.link_parser_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_parser_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.transclusion_operations.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.link_validation_operations.get_managers",
                return_value=mock_managers,
            ),
        ):
            # Act & Assert: Parse should fail
            parse_result = await parse_file_links(file_name="missing.md")
            parse_data = json.loads(parse_result)
            assert parse_data["status"] == "error"

            # Act & Assert: Resolve should fail
            resolve_result = await resolve_transclusions(file_name="missing.md")
            resolve_data = json.loads(resolve_result)
            assert resolve_data["status"] == "error"

            # Act & Assert: Validate should fail
            validate_result = await validate_links(file_name="missing.md")
            validate_data = json.loads(validate_result)
            assert validate_data["status"] == "error"
