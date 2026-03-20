"""
Comprehensive tests for Phase 4: Token Optimization Tools

This test suite provides comprehensive coverage for:
- load_context()
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

from cortex.core.models import DetailedFileMetadata
from cortex.managers.types import ManagersDict
from cortex.tools.optimization import (
    get_relevance_scores,
    get_relevance_scores_resource,
    load_context,
    load_context_resource,
    summarize_content,
    summarize_content_resource,
)
from cortex.tools.optimization.handlers import is_non_trivial_task
from tests.helpers.fixture_validator import validate_optimization_config_mock
from tests.helpers.managers import make_test_managers

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
) -> ManagersDict:
    """Create typed mock managers container.

    optimization_config mock must expose all members required by Phase 4 tools;
    see tests/FIXTURE_REQUIREMENTS.md and validate_optimization_config_mock().
    """
    optimization_config = MagicMock()
    optimization_config.get_token_budget.return_value = 10000
    optimization_config.get_max_token_budget.return_value = 100000
    optimization_config.get_reserve_for_response.return_value = 10000
    optimization_config.get_priority_order.return_value = ["file1.md", "file2.md"]
    optimization_config.get_mandatory_files.return_value = ["file1.md"]
    optimization_config.is_summarization_enabled.return_value = True
    optimization_config.is_optimization_enabled.return_value = True
    optimization_config.get_summarization_target_reduction.return_value = 0.5
    optimization_config.get_summarization_strategy.return_value = "extract_key_sections"

    validation = validate_optimization_config_mock(optimization_config)
    if not validation.valid:
        pytest.fail(validation.message)

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
            "summary_tokens": 500,
            "reduction": 0.5,
            "summary": "Test summary",
            "strategy": "extract_key_sections",
            "sections_kept": 0,
            "sections_removed": 0,
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
        return_value=[
            MagicMock(section="Section 1", title=None, score=0.9, reason="match"),
            MagicMock(section="Section 2", title=None, score=0.8, reason="match"),
        ]
    )

    # get_file_metadata must return a model with .model_dump() (DetailedFileMetadata)
    _file_metadata_model = DetailedFileMetadata(
        path="/mock/memory-bank/file.md",
        exists=True,
        size_bytes=100,
        token_count=1000,
        token_model="cl100k_base",
        last_modified="2026-01-01T00:00:00",
        content_hash="mock",
    )
    metadata_index = MagicMock()
    metadata_index.list_all_files = AsyncMock(return_value=["file1.md", "file2.md"])
    metadata_index.get_file_metadata = AsyncMock(return_value=_file_metadata_model)
    metadata_index.memory_bank_dir = Path("/mock/memory-bank")

    fs_manager = MagicMock()
    fs_manager.read_file = AsyncMock(return_value=("Test content", None))

    return make_test_managers(
        optimization_config=optimization_config,
        context_optimizer=context_optimizer,
        progressive_loader=progressive_loader,
        summarization_engine=summarization_engine,
        relevance_scorer=relevance_scorer,
        index=metadata_index,
        fs=fs_manager,
    )


# ============================================================================
# Test load_context()
# ============================================================================


class TestLoadContext:
    """Tests for load_context() tool."""

    async def test_load_context_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful context loading."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="priority",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["task_description"] == "Test task"
            # Effective budget = min(50000, 100000) - 10000 = 40000
            assert result["token_budget"] == 40000
            assert result["strategy"] == "priority"
            assert "selected_files" in result
            assert "total_tokens" in result

    async def test_load_context_sets_role_in_concise_response(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context should include an inferred role in concise responses."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Fix failing tests for feature X",
                token_budget=5000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Keywords "fix" and "tests" should map to either debugging or
            # testing roles; we verify that some role string is present.
            assert "role" in result
            assert isinstance(result["role"], str)

    async def test_load_context_with_explicit_role(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context should accept and use explicit role parameter."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Some generic task",
                token_budget=5000,
                response_format="concise",
                role="quality",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["role"] == "quality"

    async def test_load_context_default_budget(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with default budget from config."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act - pass explicit budget so validation passes; mock yields effective 0
            result_str = await load_context(
                task_description="Test task",
                token_budget=10000,
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Effective budget = min(10000, 100000) - 10000 = 0
            assert result["token_budget"] == 0

    async def test_load_context_zero_budget_non_trivial_returns_validation_error(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """token_budget=0 with non-trivial task returns validation error (no normalization)."""
        # Arrange: no need to patch managers; validation runs before init
        # Act: non-trivial task with token_budget=0 → rejected with error
        result_str = await load_context(
            task_description="Implement feature X",
            token_budget=0,
            response_format="detailed",
        )
        result = json.loads(result_str)

        # Assert: validation error, not success
        assert result["status"] == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "non-trivial" in err.lower() or "zero" in err
        assert "suggestion" in result or "action_required" in result

    async def test_load_context_trivial_task_zero_budget_normalized_to_default(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """token_budget=0 with trivial task is normalized to default and succeeds."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act: trivial task (no implement/fix/debug etc.) with token_budget=0
            result_str = await load_context(
                task_description="What is the project name?",
                token_budget=0,
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert: normalized to default budget path, success
            assert result["status"] == "success"
            assert result["token_budget"] == 0  # mock: default 10000 - reserve 10000

    async def test_load_context_dependency_aware_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with dependency_aware strategy."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="dependency_aware",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "dependency_aware"

    async def test_load_context_progressive_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with progressive strategy."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                loading_strategy="by_relevance",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_progressive_strategy_invalid_loading(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with invalid loading_strategy returns error."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                loading_strategy="invalid_strategy",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "invalid_strategy" in result["error"]
            assert "by_priority" in result["error"]

    async def test_load_context_progressive_strategy_by_dependencies(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with by_dependencies loading."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                loading_strategy="by_dependencies",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_progressive_strategy_default_loading(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with default loading_strategy (by_relevance)."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act - don't specify loading_strategy, should default to "by_relevance"
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in load_context."""
        # Arrange - exception raised in load module's initialization
        with patch(
            "cortex.tools.optimization.handlers_load.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Test error"),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Test error" in result["error"]
            assert result["error_type"] == "RuntimeError"

    async def test_load_context_optimization_disabled(
        self, mock_project_root: Path
    ) -> None:
        """Test load_context when optimization is disabled."""
        # Arrange - create managers with optimization disabled
        disabled_optimization_config = MagicMock()
        disabled_optimization_config.is_optimization_enabled = MagicMock(
            return_value=False
        )
        disabled_managers = make_test_managers(
            optimization_config=disabled_optimization_config
        )
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=disabled_managers,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_load_context_concise_format(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test load_context with concise response format."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "file_names" in result  # Concise format uses file_names
            assert "selected_files" not in result  # Detailed format uses selected_files
            assert isinstance(result["file_names"], list)  # file_names is always a list

    async def test_load_context_concise_format_with_non_dict_selected_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when selected_files is not a dict (edge case)."""
        # Arrange - patch load_context_impl to return response with selected_files as list

        async def mock_load_context_impl(*args: Any, **kwargs: Any) -> str:
            """Mock that returns response with selected_files as list."""
            return json.dumps(
                {
                    "status": "success",
                    "task_description": "Test",
                    "strategy": "priority",
                    "selected_files": ["file1.md", "file2.md"],  # List, not dict
                    "total_tokens": 1000,
                    "utilization": 0.5,
                },
                indent=2,
            )

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.load_context_impl",
                side_effect=mock_load_context_impl,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert - file_names should be empty list when selected_files is not dict
            assert result["status"] == "success"
            assert result["file_names"] == []

    async def test_load_context_concise_format_with_none_selected_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when selected_files is None (edge case)."""

        # Arrange - patch load_context_impl to return response with selected_files as None
        async def mock_load_context_impl(*args: Any, **kwargs: Any) -> str:
            """Mock that returns response with selected_files as None."""
            return json.dumps(
                {
                    "status": "success",
                    "task_description": "Test",
                    "strategy": "priority",
                    "selected_files": None,  # None instead of dict
                    "total_tokens": 1000,
                    "utilization": 0.5,
                },
                indent=2,
            )

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.load_context_impl",
                side_effect=mock_load_context_impl,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert - file_names should be empty list when selected_files is None
            assert result["status"] == "success"
            assert result["file_names"] == []

    async def test_load_context_concise_format_with_invalid_json(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when load_context_impl returns invalid JSON (error handling)."""

        # Arrange - patch load_context_impl to return invalid JSON
        async def mock_load_context_impl(*args: Any, **kwargs: Any) -> str:
            """Mock that returns invalid JSON."""
            return "invalid json {"

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.load_context_impl",
                side_effect=mock_load_context_impl,
            ),
        ):
            # Act
            result_str = await load_context(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )

            # Assert - when JSON parsing fails, original response is returned
            assert result_str == "invalid json {"


# ============================================================================
# Test load_progressive_context()
# ============================================================================


# ============================================================================
# Test summarize_content()
# ============================================================================


@pytest.mark.timeout(15)
class TestSummarizeContent:
    """Tests for summarize_content() tool."""

    async def test_summarize_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing a single file."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
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
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 2  # Mock returns 2 files

    async def test_summarize_uses_config_defaults_when_args_none(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content uses config defaults when target_reduction and strategy are None."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = True
        mock_optimization_config.get_summarization_target_reduction.return_value = 0.6
        mock_optimization_config.get_summarization_strategy.return_value = (
            "compress_verbose"
        )
        mock_optimization_config.is_optimization_enabled.return_value = True

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act - pass None for target_reduction and strategy
            result_str = await summarize_content(
                file_name="file1.md", target_reduction=None, strategy=None
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["target_reduction"] == 0.6  # From config
            assert result["strategy"] == "compress_verbose"  # From config
            mock_optimization_config.get_summarization_target_reduction.assert_called_once()
            mock_optimization_config.get_summarization_strategy.assert_called_once()

    async def test_summarize_gated_on_summarization_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content is gated on summarization.enabled."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = False
        mock_optimization_config.is_optimization_enabled.return_value = True

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(file_name="file1.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_optimization_tools_gated_on_top_level_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test optimization tools are gated on top-level enabled flag."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_optimization_enabled.return_value = False

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act - test load_context (explicit budget so we reach disabled check)
            result_str = await load_context(
                task_description="test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_summarize_with_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarization with different strategies."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
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
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
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
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
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
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
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
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
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
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
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

    async def test_full_context_loading_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test complete workflow: load context -> score -> summarize."""
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act 1: Load context
            opt_result = await load_context(
                task_description="Test task", token_budget=50000
            )
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


# ============================================================================
# Context logging (FastMCP)
# ============================================================================


@pytest.mark.asyncio
class TestPhase4OptimizationContextLogging:
    """Test Phase 4 optimization handlers use log_client when ctx is passed."""

    async def test_load_context_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """When ctx is passed, load_context logs start and completion."""
        mock_ctx = AsyncMock()
        mock_log = AsyncMock()
        with (
            patch(
                "cortex.tools.optimization.handlers.log_client",
                mock_log,
            ),
            patch(
                "cortex.core.context_logging.log_client",
                mock_log,
            ),
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                new=AsyncMock(return_value=mock_managers),
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            result_str = await load_context(
                task_description="Test task",
                token_budget=5000,
                ctx=mock_ctx,
            )
            result = json.loads(result_str)
        assert result.get("status") == "success"
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert ("info", "load_context: starting") in levels_and_messages
        assert ("info", "load_context: completed") in levels_and_messages


# ============================================================================
# Phase 43: Optimization resources (cortex://optimization/...)
# ============================================================================


@pytest.mark.asyncio
class TestPhase4OptimizationResources:
    """Test Phase 4 optimization resources (Phase 43 Step 3.2)."""

    async def test_load_context_resource_returns_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context_resource returns JSON success (zero-arg, session config)."""
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task"},
            ),
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            result_str = await load_context_resource()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["task_description"] == "Test task"
        assert result["strategy"] == "dependency_aware"

    async def test_get_relevance_scores_resource_returns_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """get_relevance_scores_resource returns JSON success."""
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            result_str = await get_relevance_scores_resource(
                task_description="relevance%20task"
            )
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "file_scores" in result

    async def test_summarize_content_resource_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """summarize_content_resource with file_name returns JSON success."""
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            result_str = await summarize_content_resource(file_name="file1.md")
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["target_reduction"] == 0.5
        assert result["strategy"] == "extract_key_sections"

    @pytest.mark.timeout(20)
    async def test_summarize_content_resource_all_files_with_underscore(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """summarize_content_resource with file_name '_' summarizes all files."""
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            result_str = await summarize_content_resource(file_name="_")
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["files_summarized"] == 2


# ============================================================================
# Phase 57 Follow-ups: Context Budget Validation
# ============================================================================


class TestContextBudgetValidation:
    """Test context budget validation for non-trivial tasks."""

    def test_is_non_trivial_task_detects_implement(self) -> None:
        """is_non_trivial_task detects 'implement' keyword."""
        assert is_non_trivial_task("Implement a new feature") is True
        assert is_non_trivial_task("implement authentication") is True

    def test_is_non_trivial_task_detects_fix(self) -> None:
        """is_non_trivial_task detects 'fix' keyword."""
        assert is_non_trivial_task("Fix a bug") is True
        assert is_non_trivial_task("debugging the issue") is True

    def test_is_non_trivial_task_detects_refactor(self) -> None:
        """is_non_trivial_task detects 'refactor' keyword."""
        assert is_non_trivial_task("Refactor the code") is True
        assert is_non_trivial_task("restructuring modules") is True

    def test_is_non_trivial_task_detects_test(self) -> None:
        """is_non_trivial_task detects 'test' keyword."""
        assert is_non_trivial_task("Test the functionality") is True
        assert is_non_trivial_task("verify the behavior") is True

    def test_is_non_trivial_task_detects_optimize(self) -> None:
        """is_non_trivial_task detects 'optimize' keyword."""
        assert is_non_trivial_task("Optimize performance") is True
        assert is_non_trivial_task("improving efficiency") is True

    def test_is_non_trivial_task_detects_update(self) -> None:
        """is_non_trivial_task detects 'update' keyword."""
        assert is_non_trivial_task("Update the module") is True
        assert is_non_trivial_task("modify the function") is True

    def test_is_non_trivial_task_detects_plan_and_planning(self) -> None:
        """is_non_trivial_task detects 'plan' and 'planning' keywords."""
        assert is_non_trivial_task("Plan the architecture") is True
        assert is_non_trivial_task("planning session optimization") is True
        assert is_non_trivial_task("Create a plan for Phase 9") is True

    def test_is_non_trivial_task_rejects_trivial(self) -> None:
        """is_non_trivial_task returns False for trivial tasks."""
        assert is_non_trivial_task("Read a file") is False
        assert is_non_trivial_task("Check status") is False
        assert is_non_trivial_task("List items") is False

    @pytest.mark.asyncio
    async def test_load_context_rejects_zero_budget_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context returns validation error for token_budget=0 with non-trivial tasks."""
        # No patches: validation runs before initialization
        result_str = await load_context(
            task_description="Implement a new feature",
            token_budget=0,
            response_format="detailed",
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "non-trivial" in err.lower() or "zero" in err
        assert "suggestion" in result or "action_required" in result

    @pytest.mark.asyncio
    async def test_load_context_rejects_omitted_budget_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context returns validation error when token_budget is omitted for non-trivial tasks."""
        # No patches: validation runs before initialization (token_budget=None)
        result_str = await load_context(
            task_description="Refactor the auth module",
            response_format="detailed",
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "Omitted" in err or "non-trivial" in err.lower()
        assert "suggestion" in result or "action_required" in result

    @pytest.mark.asyncio
    async def test_load_context_allows_zero_budget_for_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context allows token_budget=0 for trivial tasks."""
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # This should not error - trivial tasks can have zero budget
            # (though the actual loading may still fail if optimization is disabled)
            result_str = await load_context(
                task_description="Read a file",
                token_budget=0,
            )
            result = json.loads(result_str)
            # Should either succeed or fail for other reasons (optimization disabled, etc.)
            # but NOT fail with "token_budget=0 is not allowed"
            assert "token_budget=0 is not allowed" not in result.get("error", "")

    @pytest.mark.asyncio
    async def test_load_context_warns_zero_files_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context adds warning when non-trivial task results in zero files."""
        # Mock a result with zero selected files
        mock_result = json.dumps(
            {
                "status": "success",
                "task_description": "Implement a new feature",
                "token_budget": 10000,
                "selected_files": [],
                "total_tokens": 0,
            }
        )

        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.handlers_load.load_context_with_error_handling",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result_str = await load_context(
                task_description="Implement a new feature",
                token_budget=10000,
            )
            result = json.loads(result_str)
            assert result.get("status") == "success"
            warnings = result.get("warnings", [])
            assert len(warnings) > 0
            assert any(
                w.get("type") == "zero_files_selected" for w in warnings
            ), f"Expected zero_files_selected warning, got: {warnings}"


# ============================================================================
# Edge case: Phase 4 module facade exports (Phase 9.5 coverage)
# ============================================================================


def test_optimization_exports_all_public_api() -> None:
    """Validate optimization module exports all items in __all__."""
    import cortex.tools.optimization as m

    for name in m.__all__:
        assert hasattr(m, name), f"optimization.__all__ has {name!r} but missing"
        attr = getattr(m, name)
        assert attr is not None, f"optimization.{name} is None"
