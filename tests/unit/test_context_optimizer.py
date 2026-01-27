"""
Tests for ContextOptimizer module.

Tests context optimization with different strategies and coordination logic.
"""

from typing import cast
from unittest.mock import AsyncMock

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.token_counter import TokenCounter
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_strategies import OptimizationResult
from cortex.optimization.relevance_scorer import RelevanceScorer


class TestContextOptimizerInitialization:
    """Tests for ContextOptimizer initialization."""

    def test_init_with_default_mandatory_files(
        self,
        mock_token_counter: TokenCounter,
        mock_relevance_scorer: RelevanceScorer,
        mock_dependency_graph: DependencyGraph,
    ):
        """Test initialization with default mandatory files."""
        optimizer = ContextOptimizer(
            token_counter=mock_token_counter,
            relevance_scorer=mock_relevance_scorer,
            dependency_graph=mock_dependency_graph,
        )

        assert optimizer.token_counter is mock_token_counter
        assert optimizer.relevance_scorer is mock_relevance_scorer
        assert optimizer.dependency_graph is mock_dependency_graph
        assert optimizer.mandatory_files == ["memorybankinstructions.md"]
        assert optimizer.strategies is not None

    def test_init_with_custom_mandatory_files(
        self,
        mock_token_counter: TokenCounter,
        mock_relevance_scorer: RelevanceScorer,
        mock_dependency_graph: DependencyGraph,
    ):
        """Test initialization with custom mandatory files."""
        custom_files = ["file1.md", "file2.md"]
        optimizer = ContextOptimizer(
            token_counter=mock_token_counter,
            relevance_scorer=mock_relevance_scorer,
            dependency_graph=mock_dependency_graph,
            mandatory_files=custom_files,
        )

        assert optimizer.mandatory_files == custom_files

    def test_init_creates_strategies_instance(
        self,
        mock_token_counter: TokenCounter,
        mock_relevance_scorer: RelevanceScorer,
        mock_dependency_graph: DependencyGraph,
    ):
        """Test that initialization creates strategies instance with
        correct parameters."""
        optimizer = ContextOptimizer(
            token_counter=mock_token_counter,
            relevance_scorer=mock_relevance_scorer,
            dependency_graph=mock_dependency_graph,
        )

        # Verify strategies instance has correct attributes
        assert optimizer.strategies.token_counter is mock_token_counter
        assert optimizer.strategies.relevance_scorer is mock_relevance_scorer
        assert optimizer.strategies.dependency_graph is mock_dependency_graph


class TestOptimizeContext:
    """Tests for optimize_context method."""

    @pytest.mark.asyncio
    async def test_optimize_with_empty_files(
        self, mock_context_optimizer: ContextOptimizer
    ) -> None:
        """Test optimization with no files provided."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content={},
            files_metadata={},
            token_budget=1000,
        )

        assert isinstance(result, OptimizationResult)
        assert result.selected_files == []
        assert result.selected_sections == {}
        assert result.total_tokens == 0
        assert result.utilization == 0.0
        assert result.excluded_files == []
        assert "error" in result.metadata

    @pytest.mark.asyncio
    async def test_optimize_calls_relevance_scorer(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that optimize_context calls relevance scorer."""
        _ = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify relevance scorer was called
        mock_context_optimizer.relevance_scorer.score_files.assert_called_once()  # type: ignore[attr-defined]
        call_args = mock_context_optimizer.relevance_scorer.score_files.call_args  # type: ignore[attr-defined]
        assert call_args[0][0] == "Test task"

    @pytest.mark.asyncio
    async def test_optimize_with_quality_scores(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test optimization with quality scores provided."""
        quality_scores = {"file1.md": 0.9, "file2.md": 0.8}

        _ = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            quality_scores=quality_scores,
        )

        # Verify quality scores were passed to scorer
        call_args = mock_context_optimizer.relevance_scorer.score_files.call_args  # type: ignore[attr-defined]
        assert call_args[0][3] == quality_scores

    @pytest.mark.asyncio
    async def test_optimize_with_priority_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test optimization with priority strategy."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="priority",
        )

        # Verify priority strategy was called
        mock_context_optimizer.strategies.optimize_by_priority.assert_called_once()  # type: ignore[attr-defined]
        assert result.strategy_used == "priority"

    @pytest.mark.asyncio
    async def test_optimize_with_dependency_aware_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test optimization with dependency_aware strategy."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="dependency_aware",
        )

        # Verify dependency_aware strategy was called
        mock_context_optimizer.strategies.optimize_by_dependencies.assert_called_once()  # type: ignore[attr-defined]
        assert result.strategy_used == "dependency_aware"

    @pytest.mark.asyncio
    async def test_optimize_with_section_level_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test optimization with section_level strategy."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="section_level",
        )

        # Verify section_level strategy was called
        mock_context_optimizer.strategies.optimize_with_sections.assert_called_once()  # type: ignore[attr-defined]
        assert result.strategy_used == "section_level"

    @pytest.mark.asyncio
    async def test_optimize_with_hybrid_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test optimization with hybrid strategy."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="hybrid",
        )

        # Verify hybrid strategy was called
        mock_context_optimizer.strategies.optimize_hybrid.assert_called_once()  # type: ignore[attr-defined]
        assert result.strategy_used == "hybrid"

    @pytest.mark.asyncio
    async def test_optimize_with_unknown_strategy_defaults_to_dependency_aware(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that unknown strategy defaults to dependency_aware."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="unknown_strategy",
        )

        # Verify dependency_aware strategy was called (default)
        mock_context_optimizer.strategies.optimize_by_dependencies.assert_called_once()  # type: ignore[attr-defined]
        assert result.strategy_used == "unknown_strategy"

    @pytest.mark.asyncio
    async def test_optimize_adds_relevance_scores_to_metadata(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that relevance scores are added to result metadata."""
        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify relevance scores in metadata
        assert "relevance_scores" in result.metadata
        relevance_scores_raw = result.metadata["relevance_scores"]
        assert isinstance(relevance_scores_raw, dict)
        relevance_scores = cast(dict[str, float], relevance_scores_raw)
        assert all(isinstance(score, float) for score in relevance_scores.values())

    @pytest.mark.asyncio
    async def test_optimize_handles_integer_total_score(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that integer total_score values are handled correctly."""
        # Mock scorer to return integer scores
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            return_value={
                "file1.md": {"total_score": 85, "components": {}},
                "file2.md": {"total_score": 90, "components": {}},
            }
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify scores were converted to float
        relevance_scores_raw = result.metadata["relevance_scores"]
        assert isinstance(relevance_scores_raw, dict)
        relevance_scores = cast(dict[str, float], relevance_scores_raw)
        assert all(isinstance(score, float) for score in relevance_scores.values())

    @pytest.mark.asyncio
    async def test_optimize_handles_missing_total_score(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that missing total_score is handled with default value."""
        # Mock scorer to return results without total_score
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            return_value={
                "file1.md": {"components": {}},
                "file2.md": {"components": {}},
            }
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify default score of 0.0 was used
        relevance_scores_raw = result.metadata["relevance_scores"]
        assert isinstance(relevance_scores_raw, dict)
        relevance_scores = cast(dict[str, float], relevance_scores_raw)
        assert all(score == 0.0 for score in relevance_scores.values())

    @pytest.mark.asyncio
    async def test_optimize_handles_non_numeric_total_score(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that non-numeric total_score is handled with default value."""
        # Mock scorer to return non-numeric scores
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            return_value={
                "file1.md": {"total_score": "invalid", "components": {}},
                "file2.md": {"total_score": None, "components": {}},
            }
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify default score of 0.0 was used
        relevance_scores_raw = result.metadata["relevance_scores"]
        assert isinstance(relevance_scores_raw, dict)
        relevance_scores = cast(dict[str, float], relevance_scores_raw)
        assert all(score == 0.0 for score in relevance_scores.values())


class TestOptimizeByPriority:
    """Tests for optimize_by_priority method."""

    @pytest.mark.asyncio
    async def test_optimize_by_priority_delegates_to_strategies(
        self, mock_context_optimizer: ContextOptimizer
    ) -> None:
        """Test that optimize_by_priority delegates to strategies."""
        relevance_scores = {"file1.md": 0.8, "file2.md": 0.6}
        files_content = {"file1.md": "content1", "file2.md": "content2"}
        token_budget = 1000

        result = await mock_context_optimizer.optimize_by_priority(
            relevance_scores, files_content, token_budget
        )

        # Verify delegation
        mock_context_optimizer.strategies.optimize_by_priority.assert_called_once_with(  # type: ignore[attr-defined]
            relevance_scores, files_content, token_budget
        )
        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_optimize_by_priority_with_empty_scores(
        self, mock_context_optimizer: ContextOptimizer
    ) -> None:
        """Test optimize_by_priority with empty relevance scores."""
        result = await mock_context_optimizer.optimize_by_priority(
            relevance_scores={},
            files_content={"file1.md": "content"},
            token_budget=1000,
        )

        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_optimize_by_priority_with_zero_budget(
        self, mock_context_optimizer: ContextOptimizer
    ) -> None:
        """Test optimize_by_priority with zero token budget."""
        result = await mock_context_optimizer.optimize_by_priority(
            relevance_scores={"file1.md": 0.8},
            files_content={"file1.md": "content"},
            token_budget=0,
        )

        assert isinstance(result, OptimizationResult)


class TestRelevanceScoreExtraction:
    """Tests for relevance score extraction logic."""

    @pytest.mark.asyncio
    async def test_extracts_scores_from_nested_results(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that scores are correctly extracted from nested result structure."""
        # Mock complex nested structure
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            return_value={
                "file1.md": {
                    "total_score": 85.5,
                    "components": {"keyword": 50, "dependency": 35.5},
                },
                "file2.md": {
                    "total_score": 70.0,
                    "components": {"keyword": 40, "dependency": 30},
                },
            }
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify scores were extracted and rounded
        scores_raw = result.metadata["relevance_scores"]
        assert isinstance(scores_raw, dict)
        scores = cast(dict[str, float], scores_raw)
        assert scores["file1.md"] == 85.5
        assert scores["file2.md"] == 70.0

    @pytest.mark.asyncio
    async def test_rounds_scores_to_three_decimals(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that scores are rounded to 3 decimal places."""
        # Mock scorer with high precision scores
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            return_value={
                "file1.md": {"total_score": 85.123456789, "components": {}},
                "file2.md": {"total_score": 70.987654321, "components": {}},
            }
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify rounding
        scores_raw = result.metadata["relevance_scores"]
        assert isinstance(scores_raw, dict)
        scores = cast(dict[str, float], scores_raw)
        assert scores["file1.md"] == 85.123
        assert scores["file2.md"] == 70.988  # Rounded up


class TestStrategyDelegation:
    """Tests for strategy delegation and coordination."""

    @pytest.mark.asyncio
    async def test_passes_correct_parameters_to_priority_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that correct parameters are passed to priority strategy."""
        _ = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1500,
            strategy="priority",
        )

        # Verify parameters
        call_args = mock_context_optimizer.strategies.optimize_by_priority.call_args[0]  # type: ignore[attr-defined]
        relevance_scores, files_content, token_budget = cast(
            tuple[dict[str, float], dict[str, str], int], call_args
        )

        assert isinstance(relevance_scores, dict)
        assert files_content == sample_files_content
        assert token_budget == 1500

    @pytest.mark.asyncio
    async def test_passes_task_description_to_section_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that task description is passed to section-level strategy."""
        task_desc = "Implement authentication feature"

        _ = await mock_context_optimizer.optimize_context(
            task_description=task_desc,
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="section_level",
        )

        # Verify task description was passed
        call_args = mock_context_optimizer.strategies.optimize_with_sections.call_args[  # type: ignore[attr-defined]
            0
        ]
        assert call_args[0] == task_desc

    @pytest.mark.asyncio
    async def test_passes_task_description_to_hybrid_strategy(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that task description is passed to hybrid strategy."""
        task_desc = "Fix bug in user login"

        _ = await mock_context_optimizer.optimize_context(
            task_description=task_desc,
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
            strategy="hybrid",
        )

        # Verify task description was passed
        call_args = mock_context_optimizer.strategies.optimize_hybrid.call_args[0]  # type: ignore[attr-defined]
        assert call_args[0] == task_desc


class TestErrorHandling:
    """Tests for error handling in optimization."""

    @pytest.mark.asyncio
    async def test_handles_scorer_exception(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test handling of exceptions from relevance scorer."""
        # Mock scorer to raise exception
        mock_context_optimizer.relevance_scorer.score_files = AsyncMock(
            side_effect=Exception("Scorer error")
        )

        with pytest.raises(Exception, match="Scorer error"):
            _ = await mock_context_optimizer.optimize_context(
                task_description="Test task",
                files_content=sample_files_content,
                files_metadata=sample_files_metadata,
                token_budget=1000,
            )

    @pytest.mark.asyncio
    async def test_handles_strategy_exception(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test handling of exceptions from strategies."""
        # Mock strategy to raise exception
        mock_context_optimizer.strategies.optimize_by_dependencies = AsyncMock(
            side_effect=Exception("Strategy error")
        )

        with pytest.raises(Exception, match="Strategy error"):
            _ = await mock_context_optimizer.optimize_context(
                task_description="Test task",
                files_content=sample_files_content,
                files_metadata=sample_files_metadata,
                token_budget=1000,
            )


class TestMetadataHandling:
    """Tests for metadata handling in results."""

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test that existing metadata from strategy is preserved."""
        # Mock strategy to return result with metadata
        existing_metadata: dict[str, object] = {
            "strategy_info": "test",
            "extra_data": 123,
        }
        mock_result = OptimizationResult(
            selected_files=["file1.md"],
            selected_sections={},
            total_tokens=500,
            utilization=0.5,
            excluded_files=[],
            strategy_used="test",
            metadata=existing_metadata,
        )
        mock_context_optimizer.strategies.optimize_by_dependencies = AsyncMock(
            return_value=mock_result
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify existing metadata preserved
        assert "strategy_info" in result.metadata
        assert "extra_data" in result.metadata
        assert "relevance_scores" in result.metadata

    @pytest.mark.asyncio
    async def test_handles_none_metadata(
        self,
        mock_context_optimizer: ContextOptimizer,
        sample_files_content: dict[str, str],
        sample_files_metadata: dict[str, dict[str, object]],
    ) -> None:
        """Test handling when strategy returns None metadata."""
        # Mock strategy to return result with None metadata
        mock_result = OptimizationResult(
            selected_files=["file1.md"],
            selected_sections={},
            total_tokens=500,
            utilization=0.5,
            excluded_files=[],
            strategy_used="test",
            metadata={},  # Use empty dict instead of None
        )
        mock_context_optimizer.strategies.optimize_by_dependencies = AsyncMock(
            return_value=mock_result
        )

        result = await mock_context_optimizer.optimize_context(
            task_description="Test task",
            files_content=sample_files_content,
            files_metadata=sample_files_metadata,
            token_budget=1000,
        )

        # Verify metadata dict created and relevance scores added
        assert isinstance(result.metadata, dict)
        assert "relevance_scores" in result.metadata
