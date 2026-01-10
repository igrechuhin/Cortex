"""
Comprehensive tests for Phase 4: Token Optimization Tools

This test suite provides comprehensive coverage for:
- optimize_context()
- load_progressive_context()
- summarize_content()
- get_relevance_scores()
- All helper functions and error paths
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.phase4_optimization import (
    get_relevance_scores,
    load_progressive_context,
    optimize_context,
    summarize_content,
)

# ============================================================================
# Helper Functions
# ============================================================================


def _get_manager_helper(mgrs: dict[str, Any], key: str, _: object) -> Any:
    """Helper function to get manager from dictionary."""
    return mgrs[key]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_optimization_result() -> MagicMock:
    """Create mock optimization result."""
    return MagicMock(
        selected_files=["file1.md", "file2.md"],
        selected_sections={"file1.md": ["Section 1"]},
        total_tokens=5000,
        utilization=0.5,
        excluded_files=["file3.md"],
        metadata={"relevance_scores": {"file1.md": 0.9, "file2.md": 0.8}},
    )


@pytest.fixture
def mock_loaded_content() -> list[Any]:
    """Create mock loaded content items."""

    class MockLoadedContent:
        def __init__(
            self,
            file_name: str,
            tokens: int,
            cumulative: int,
            priority: int,
            relevance: float,
        ) -> None:
            self.file_name = file_name
            self.tokens = tokens
            self.cumulative_tokens = cumulative
            self.priority = priority
            self.relevance_score = relevance
            self.more_available = False

    return [
        MockLoadedContent("file1.md", 1000, 1000, 1, 0.9),
        MockLoadedContent("file2.md", 2000, 3000, 2, 0.8),
    ]


@pytest.fixture
def mock_managers(
    mock_optimization_result: MagicMock, mock_loaded_content: list[Any]
) -> dict[str, Any]:
    """Create mock managers dictionary."""
    optimization_config = MagicMock()
    optimization_config.get_token_budget.return_value = 10000
    optimization_config.get_priority_order.return_value = ["file1.md", "file2.md"]
    optimization_config.get_mandatory_files.return_value = ["file1.md"]

    context_optimizer = MagicMock()
    context_optimizer.optimize_context = AsyncMock(
        return_value=mock_optimization_result
    )

    progressive_loader = MagicMock()
    progressive_loader.load_by_priority = AsyncMock(return_value=mock_loaded_content)
    progressive_loader.load_by_dependencies = AsyncMock(
        return_value=mock_loaded_content
    )
    progressive_loader.load_by_relevance = AsyncMock(return_value=mock_loaded_content)

    summarization_engine = MagicMock()
    summarization_engine.summarize_file = AsyncMock(
        return_value={
            "original_tokens": 1000,
            "summarized_tokens": 500,
            "reduction": 0.5,
            "cached": False,
            "summary": "Test summary",
        }
    )

    relevance_scorer = MagicMock()
    relevance_scorer.score_files = AsyncMock(
        return_value={
            "file1.md": {"total_score": 0.9, "keyword_score": 0.8},
            "file2.md": {"total_score": 0.7, "keyword_score": 0.6},
        }
    )
    relevance_scorer.score_sections = AsyncMock(
        return_value={"Section 1": 0.9, "Section 2": 0.8}
    )

    metadata_index = MagicMock()
    metadata_index.list_all_files = AsyncMock(return_value=["file1.md", "file2.md"])
    metadata_index.get_file_metadata = AsyncMock(
        return_value={"tokens": 1000, "priority": 1}
    )
    metadata_index.memory_bank_dir = Path("/mock/memory-bank")

    fs_manager = MagicMock()
    fs_manager.read_file = AsyncMock(return_value=("Test content", None))

    return {
        "optimization_config": optimization_config,
        "context_optimizer": context_optimizer,
        "progressive_loader": progressive_loader,
        "summarization_engine": summarization_engine,
        "relevance_scorer": relevance_scorer,
        "index": metadata_index,
        "fs": fs_manager,
    }


# ============================================================================
# Test optimize_context()
# ============================================================================


class TestOptimizeContext:
    """Tests for optimize_context() tool."""

    async def test_optimize_context_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful context optimization."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await optimize_context(
                task_description="Test task", token_budget=10000, strategy="priority"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["task_description"] == "Test task"
            assert result["token_budget"] == 10000
            assert result["strategy"] == "priority"
            assert "selected_files" in result
            assert "total_tokens" in result

    async def test_optimize_context_default_budget(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test optimization with default budget from config."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await optimize_context(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["token_budget"] == 10000  # From mock config

    async def test_optimize_context_dependency_aware_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test optimization with dependency_aware strategy."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await optimize_context(
                task_description="Test task", strategy="dependency_aware"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "dependency_aware"

    async def test_optimize_context_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in optimize_context."""
        # Arrange
        with patch(
            "cortex.tools.phase4_optimization.get_project_root",
            side_effect=RuntimeError("Test error"),
        ):
            # Act
            result_str = await optimize_context(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Test error" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Test load_progressive_context()
# ============================================================================


class TestLoadProgressiveContext:
    """Tests for load_progressive_context() tool."""

    async def test_load_progressive_by_priority(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test progressive loading by priority."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_progressive_context(
                task_description="Test task", loading_strategy="by_priority"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["loading_strategy"] == "by_priority"
            assert result["files_loaded"] == 2
            assert len(result["loaded_files"]) == 2

    async def test_load_progressive_by_dependencies(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive loading by dependencies."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_progressive_context(
                task_description="Test task", loading_strategy="by_dependencies"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["loading_strategy"] == "by_dependencies"

    async def test_load_progressive_by_relevance(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive loading by relevance."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_progressive_context(
                task_description="Test task", loading_strategy="by_relevance"
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["loading_strategy"] == "by_relevance"

    async def test_load_progressive_default_budget(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive loading with default budget."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_progressive_context(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["token_budget"] == 10000  # From mock config

    async def test_load_progressive_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in load_progressive_context."""
        # Arrange
        with patch(
            "cortex.tools.phase4_optimization.get_project_root",
            side_effect=ValueError("Invalid project root"),
        ):
            # Act
            result_str = await load_progressive_context(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Invalid project root" in result["error"]


# ============================================================================
# Test summarize_content()
# ============================================================================


class TestSummarizeContent:
    """Tests for summarize_content() tool."""

    async def test_summarize_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing a single file."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(
                file_name="file1.md", target_reduction=0.5
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 1
            assert result["target_reduction"] == 0.5

    async def test_summarize_all_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing all files."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 2  # Mock returns 2 files

    async def test_summarize_with_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarization with different strategies."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(strategy="headers_only")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "headers_only"

    async def test_summarize_invalid_reduction(self, mock_project_root: Path) -> None:
        """Test summarization with invalid reduction value."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(target_reduction=1.5)
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "target_reduction must be between 0 and 1" in result["error"]

    async def test_summarize_invalid_strategy(self, mock_project_root: Path) -> None:
        """Test summarization with invalid strategy."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(strategy="invalid_strategy")
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "Invalid strategy" in result["error"]

    async def test_summarize_exception_handling(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test exception handling in summarize_content."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_summarization_operations.get_manager",
                side_effect=RuntimeError("Summarization failed"),
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Summarization failed" in result["error"]


# ============================================================================
# Test get_relevance_scores()
# ============================================================================


class TestGetRelevanceScores:
    """Tests for get_relevance_scores() tool."""

    async def test_get_relevance_scores_files_only(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test getting relevance scores for files only."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(
                task_description="Test task", include_sections=False
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_scored"] == 2
            assert "file_scores" in result
            assert "section_scores" not in result

    async def test_get_relevance_scores_with_sections(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test getting relevance scores including sections."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(
                task_description="Test task", include_sections=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "file_scores" in result
            assert "section_scores" in result
            assert len(result["section_scores"]) == 2  # Mock returns 2 files

    async def test_get_relevance_scores_sorted(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test that relevance scores are sorted by total_score."""
        # Arrange
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            file_scores = result["file_scores"]
            scores = [v["total_score"] for v in file_scores.values()]
            assert scores == sorted(scores, reverse=True)  # Should be descending

    async def test_get_relevance_scores_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in get_relevance_scores."""
        # Arrange
        with patch(
            "cortex.tools.phase4_optimization.get_project_root",
            side_effect=RuntimeError("Scoring failed"),
        ):
            # Act
            result_str = await get_relevance_scores(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Scoring failed" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for Phase 4 optimization workflows."""

    async def test_full_optimization_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test complete workflow: optimize -> score -> summarize."""
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act 1: Optimize context
            opt_result = await optimize_context(task_description="Test task")
            opt_data = json.loads(opt_result)

            # Assert 1
            assert opt_data["status"] == "success"

            # Act 2: Get relevance scores
            scores_result = await get_relevance_scores(task_description="Test task")
            scores_data = json.loads(scores_result)

            # Assert 2
            assert scores_data["status"] == "success"

            # Act 3: Summarize content
            summary_result = await summarize_content()
            summary_data = json.loads(summary_result)

            # Assert 3
            assert summary_data["status"] == "success"

    async def test_progressive_loading_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test progressive loading with all strategies."""
        with (
            patch(
                "cortex.tools.phase4_optimization.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.phase4_optimization.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Test each loading strategy
            for strategy in ["by_priority", "by_dependencies", "by_relevance"]:
                # Act
                result_str = await load_progressive_context(
                    task_description="Test task", loading_strategy=strategy
                )
                result = json.loads(result_str)

                # Assert
                assert result["status"] == "success"
                assert result["loading_strategy"] == strategy
                assert result["files_loaded"] > 0
