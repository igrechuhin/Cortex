"""
Tests for the ProgressiveLoader module.

This module tests progressive context loading for incremental content delivery.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.progressive_loader import (
    LoadedContent,
    ProgressiveLoader,
)


class TestProgressiveLoaderInitialization:
    """Tests for ProgressiveLoader initialization."""

    def test_init_with_dependencies(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
    ):
        """Test initialization with required dependencies."""
        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        assert loader.file_system == mock_file_system
        assert loader.context_optimizer == mock_context_optimizer
        assert loader.metadata_index == mock_metadata_index


class TestLoadedContentDataclass:
    """Tests for LoadedContent dataclass."""

    def test_loaded_content_creation(self):
        """Test creating a LoadedContent instance."""
        content = LoadedContent(
            file_name="test.md",
            content="Test content",
            tokens=10,
            cumulative_tokens=10,
            priority=0,
            relevance_score=0.85,
            more_available=True,
            metadata={"last_modified": "2024-01-01"},
        )

        assert content.file_name == "test.md"
        assert content.content == "Test content"
        assert content.tokens == 10
        assert content.cumulative_tokens == 10
        assert content.priority == 0
        assert content.relevance_score == 0.85
        assert content.more_available is True
        assert content.metadata == {"last_modified": "2024-01-01"}


class TestGetDefaultPriorityOrder:
    """Tests for default priority order."""

    def test_get_default_priority_order(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
    ):
        """Test getting default priority order."""
        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        order = loader.get_default_priority_order()

        assert len(order) == 7
        assert order[0] == "memorybankinstructions.md"
        assert order[1] == "projectBrief.md"
        assert "activeContext.md" in order
        assert "systemPatterns.md" in order
        assert "techContext.md" in order
        assert "productContext.md" in order
        assert "progress.md" in order


class TestLoadByPriority:
    """Tests for loading files by priority."""

    @pytest.mark.asyncio
    async def test_load_by_priority_default_order(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test loading files using default priority order."""
        # Setup
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(
            return_value=("Test content for file", "hash123")
        )
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=10)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={"tokens": 10})

        # Create test files
        for filename in ["memorybankinstructions.md", "projectBrief.md"]:
            _ = (tmp_path / filename).write_text("Test content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        # Load with large budget
        result = await loader.load_by_priority("task description", token_budget=1000)

        assert len(result) > 0
        assert result[0].file_name == "memorybankinstructions.md"
        assert result[0].priority == 0
        assert result[0].tokens == 10

    @pytest.mark.asyncio
    async def test_load_by_priority_custom_order(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test loading files with custom priority order."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(
            return_value=("Custom content", "hash123")
        )
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=15)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        # Create files
        for filename in ["file1.md", "file2.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task", token_budget=1000, priority_order=["file2.md", "file1.md"]
        )

        assert len(result) >= 1
        assert result[0].file_name == "file2.md"

    @pytest.mark.asyncio
    async def test_load_by_priority_respects_budget(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that priority loading respects token budget."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        # Budget allows only 2 files (200 tokens)
        result = await loader.load_by_priority(
            "task",
            token_budget=200,
            priority_order=["file1.md", "file2.md", "file3.md"],
        )

        assert len(result) == 2
        assert result[-1].cumulative_tokens == 200

    @pytest.mark.asyncio
    async def test_load_by_priority_skips_missing_files(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that priority loading skips missing files."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(side_effect=FileNotFoundError())
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=10)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task", token_budget=1000, priority_order=["missing.md"]
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_load_by_priority_tracks_cumulative_tokens(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that cumulative tokens are tracked correctly."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))

        # Different token counts for each file
        token_counts = [50, 75, 100]
        mock_context_optimizer.token_counter.count_tokens = MagicMock(
            side_effect=token_counts
        )
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task",
            token_budget=1000,
            priority_order=["file1.md", "file2.md", "file3.md"],
        )

        assert result[0].cumulative_tokens == 50
        assert result[1].cumulative_tokens == 125  # 50 + 75
        assert result[2].cumulative_tokens == 225  # 50 + 75 + 100


class TestLoadByDependencies:
    """Tests for loading files by dependency chain."""

    @pytest.mark.asyncio
    async def test_load_by_dependencies_single_file(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test loading a single entry file with no dependencies."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=50)
        mock_context_optimizer.dependency_graph.get_dependencies = MagicMock(
            return_value=[]
        )
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        _ = (tmp_path / "entry.md").write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_dependencies(
            entry_files=["entry.md"], token_budget=1000
        )

        assert len(result) == 1
        assert result[0].file_name == "entry.md"
        assert result[0].priority == 0  # Depth 0

    @pytest.mark.asyncio
    async def test_load_by_dependencies_with_chain(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test loading dependency chain."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=50)

        # Setup dependency chain: entry -> dep1 -> dep2
        def get_deps(file_name: str) -> list[str]:
            if file_name == "entry.md":
                return ["dep1.md"]
            elif file_name == "dep1.md":
                return ["dep2.md"]
            return []

        mock_context_optimizer.dependency_graph.get_dependencies = MagicMock(
            side_effect=get_deps
        )
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["entry.md", "dep1.md", "dep2.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_dependencies(
            entry_files=["entry.md"], token_budget=1000
        )

        assert len(result) == 3
        file_names = [r.file_name for r in result]
        assert "entry.md" in file_names
        assert "dep1.md" in file_names
        assert "dep2.md" in file_names

    @pytest.mark.asyncio
    async def test_load_by_dependencies_respects_budget(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test dependency loading respects token budget."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)
        mock_context_optimizer.dependency_graph.get_dependencies = MagicMock(
            return_value=["dep.md"]
        )
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["entry.md", "dep.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        # Budget allows only 1 file
        result = await loader.load_by_dependencies(
            entry_files=["entry.md"], token_budget=100
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_load_by_dependencies_avoids_cycles(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that dependency loading handles cycles correctly."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=50)

        # Circular dependency: file1 -> file2 -> file1
        def get_deps(file_name: str) -> list[str]:
            if file_name == "file1.md":
                return ["file2.md"]
            elif file_name == "file2.md":
                return ["file1.md"]
            return []

        mock_context_optimizer.dependency_graph.get_dependencies = MagicMock(
            side_effect=get_deps
        )
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_dependencies(
            entry_files=["file1.md"], token_budget=1000
        )

        # Should load both files but not infinitely loop
        assert len(result) == 2


class TestLoadByRelevance:
    """Tests for loading files by relevance."""

    @pytest.mark.asyncio
    async def test_load_by_relevance_uses_optimizer(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that relevance loading uses context optimizer."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_metadata_index.memory_bank_dir = tmp_path
        mock_metadata_index.list_all_files = AsyncMock(return_value=["file1.md"])
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        # Mock optimization result
        from cortex.optimization.optimization_strategies import (
            OptimizationResult,
        )

        mock_result = OptimizationResult(
            selected_files=["file1.md"],
            selected_sections={},
            total_tokens=100,
            utilization=0.5,
            excluded_files=[],
            strategy_used="priority",
            metadata={"relevance_scores": {"file1.md": 0.85}},
        )
        mock_context_optimizer.optimize_context = AsyncMock(return_value=mock_result)
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)

        _ = (tmp_path / "file1.md").write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_relevance("task description", token_budget=1000)

        assert len(result) == 1
        assert result[0].relevance_score == 0.85
        mock_context_optimizer.optimize_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_by_relevance_with_quality_scores(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test relevance loading with quality scores."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_metadata_index.memory_bank_dir = tmp_path
        mock_metadata_index.list_all_files = AsyncMock(return_value=["file1.md"])
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        from cortex.optimization.optimization_strategies import (
            OptimizationResult,
        )

        mock_result = OptimizationResult(
            selected_files=["file1.md"],
            selected_sections={},
            total_tokens=100,
            utilization=0.5,
            excluded_files=[],
            strategy_used="priority",
            metadata={"relevance_scores": {"file1.md": 0.90}},
        )
        mock_context_optimizer.optimize_context = AsyncMock(return_value=mock_result)
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)

        _ = (tmp_path / "file1.md").write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        quality_scores = {"file1.md": 0.95}
        result = await loader.load_by_relevance(
            "task", token_budget=1000, quality_scores=quality_scores
        )

        assert len(result) == 1
        # Quality scores should be passed to optimizer
        call_kwargs = mock_context_optimizer.optimize_context.call_args.kwargs
        assert call_kwargs["quality_scores"] == quality_scores


class TestLoadWithBudget:
    """Tests for loading files with budget constraints."""

    @pytest.mark.asyncio
    async def test_load_with_budget_stops_at_budget(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that loading stops at budget when flag is set."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_with_budget(
            files=["file1.md", "file2.md", "file3.md"],
            token_budget=200,
            stop_at_budget=True,
        )

        assert len(result) == 2
        assert result[-1].cumulative_tokens <= 200

    @pytest.mark.asyncio
    async def test_load_with_budget_loads_all_when_not_stopping(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that all files are loaded when stop_at_budget is False."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_with_budget(
            files=["file1.md", "file2.md", "file3.md"],
            token_budget=150,  # Less than needed for all
            stop_at_budget=False,
        )

        # All 3 files should be loaded despite budget
        assert len(result) == 3


class TestStreamByPriority:
    """Tests for streaming files by priority."""

    @pytest.mark.asyncio
    async def test_stream_by_priority_yields_content(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that priority streaming yields content one at a time."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=50)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        results: list[LoadedContent] = []
        async for content in loader.stream_by_priority(
            "task", token_budget=1000, priority_order=["file1.md", "file2.md"]
        ):
            results.append(content)

        assert len(results) == 2
        assert isinstance(results[0], LoadedContent)

    @pytest.mark.asyncio
    async def test_stream_by_priority_respects_budget(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that streaming stops when budget is exceeded."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        results: list[LoadedContent] = []
        async for content in loader.stream_by_priority(
            "task",
            token_budget=150,
            priority_order=["file1.md", "file2.md", "file3.md"],
        ):
            results.append(content)

        # Should stop after 1 file (100 tokens) because next would exceed budget
        assert len(results) == 1


class TestStreamByRelevance:
    """Tests for streaming files by relevance."""

    @pytest.mark.asyncio
    async def test_stream_by_relevance_uses_load_by_relevance(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that streaming by relevance uses load_by_relevance."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_metadata_index.memory_bank_dir = tmp_path
        mock_metadata_index.list_all_files = AsyncMock(return_value=["file1.md"])
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        from cortex.optimization.optimization_strategies import (
            OptimizationResult,
        )

        mock_result = OptimizationResult(
            selected_files=["file1.md"],
            selected_sections={},
            total_tokens=100,
            utilization=0.5,
            excluded_files=[],
            strategy_used="priority",
            metadata={"relevance_scores": {"file1.md": 0.85}},
        )
        mock_context_optimizer.optimize_context = AsyncMock(return_value=mock_result)
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=100)

        _ = (tmp_path / "file1.md").write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        results: list[LoadedContent] = []
        async for content in loader.stream_by_relevance("task", token_budget=1000):
            results.append(content)

        assert len(results) == 1
        assert results[0].file_name == "file1.md"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_file_list(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
    ):
        """Test loading with empty file list."""
        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task", token_budget=1000, priority_order=[]
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_zero_token_budget(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test loading with zero token budget."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=10)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        _ = (tmp_path / "file.md").write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task", token_budget=0, priority_order=["file.md"]
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_more_available_flag_accuracy(
        self,
        mock_file_system: FileSystemManager,
        mock_context_optimizer: ContextOptimizer,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test that more_available flag is set correctly."""
        mock_file_system.memory_bank_dir = tmp_path
        mock_file_system.read_file = AsyncMock(return_value=("Content", "hash"))
        mock_context_optimizer.token_counter.count_tokens = MagicMock(return_value=50)
        mock_metadata_index.get_file_metadata = AsyncMock(return_value={})

        for filename in ["file1.md", "file2.md", "file3.md"]:
            _ = (tmp_path / filename).write_text("Content")

        loader = ProgressiveLoader(
            mock_file_system, mock_context_optimizer, mock_metadata_index
        )

        result = await loader.load_by_priority(
            "task",
            token_budget=1000,
            priority_order=["file1.md", "file2.md", "file3.md"],
        )

        # First and second should have more_available=True
        assert result[0].more_available is True
        assert result[1].more_available is True
        # Last should have more_available=False
        assert result[2].more_available is False
