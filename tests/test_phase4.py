"""
Comprehensive test suite for Phase 4: Token Optimization

Tests all Phase 4 modules:
- RelevanceScorer
- ContextOptimizer
- ProgressiveLoader
- SummarizationEngine
- OptimizationConfig
"""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

# Import dependencies
from cortex.core.token_counter import TokenCounter
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.progressive_loader import ProgressiveLoader

# Import Phase 4 modules
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.optimization.summarization_engine import SummarizationEngine


class TestRelevanceScorer:
    """Test relevance scoring functionality."""

    @pytest.fixture
    def scorer(self) -> Generator[RelevanceScorer, None, None]:
        """Create a relevance scorer."""
        dep_graph = DependencyGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_index = MetadataIndex(Path(tmpdir))
            scorer = RelevanceScorer(dep_graph, metadata_index)
            yield scorer

    def test_extract_keywords(self, scorer: RelevanceScorer) -> None:
        """Test keyword extraction."""
        text = "Build a new authentication system with OAuth and JWT tokens"
        keywords_raw = scorer.extract_keywords(text)
        keywords: list[str] = keywords_raw

        assert "build" in keywords
        assert "authentication" in keywords
        assert "system" in keywords
        assert "oauth" in keywords
        assert "jwt" in keywords
        assert "tokens" in keywords
        # Stop words should be filtered
        assert "a" not in keywords
        assert "with" not in keywords

    def test_keyword_score(self, scorer: RelevanceScorer) -> None:
        """Test keyword scoring."""
        task_keywords = ["authentication", "login", "user"]
        content = "This file describes the authentication system and user login flow."

        score = scorer.calculate_keyword_score(task_keywords, content)

        assert 0.0 <= score <= 1.0
        assert score > 0.0  # Should match some keywords

    def test_keyword_score_no_match(self, scorer: RelevanceScorer) -> None:
        """Test keyword scoring with no matches."""
        task_keywords = ["database", "schema", "table"]
        content = "This file describes the authentication system and user login flow."

        score = scorer.calculate_keyword_score(task_keywords, content)

        assert score == 0.0  # No keyword matches

    @pytest.mark.asyncio
    async def test_score_files(self, scorer: RelevanceScorer) -> None:
        """Test file scoring."""
        task_description = "Implement user authentication"

        files_content = {
            "auth.md": "Complete guide to authentication system with OAuth and JWT.",
            "database.md": "Database schema and table definitions.",
            "ui.md": "User interface components and styling.",
        }

        files_metadata = {
            "auth.md": {"last_modified": "2025-12-19T10:00:00Z"},
            "database.md": {"last_modified": "2025-11-01T10:00:00Z"},
            "ui.md": {"last_modified": "2025-10-01T10:00:00Z"},
        }

        scores = await scorer.score_files(
            task_description,
            files_content,
            cast(dict[str, dict[str, object]], files_metadata),
        )

        assert "auth.md" in scores
        assert "database.md" in scores
        assert "ui.md" in scores

        # auth.md should score highest
        auth_score = scores["auth.md"].get("total_score", 0.0)
        db_score = scores["database.md"].get("total_score", 0.0)
        ui_score = scores["ui.md"].get("total_score", 0.0)
        assert isinstance(auth_score, (int, float))
        assert isinstance(db_score, (int, float))
        assert isinstance(ui_score, (int, float))
        assert float(auth_score) > float(db_score)
        assert float(auth_score) > float(ui_score)

    @pytest.mark.asyncio
    async def test_score_sections(self, scorer: RelevanceScorer) -> None:
        """Test section scoring."""
        task_description = "Implement authentication"
        content = """
# Overview
General project information.

# Authentication System
Details about the authentication system with OAuth.

# Database Schema
Table definitions and relationships.
"""

        sections = await scorer.score_sections(task_description, "test.md", content)

        assert len(sections) > 0
        # Authentication section should score highest
        auth_section = next(
            (s for s in sections if "Authentication" in str(s.get("section", ""))), None
        )
        assert auth_section is not None
        score = auth_section.get("score", 0)
        assert isinstance(score, (int, float))
        assert float(score) > 0


class TestContextOptimizer:
    """Test context optimization functionality."""

    @pytest.fixture
    def optimizer(self) -> Generator[ContextOptimizer, None, None]:
        """Create a context optimizer."""
        token_counter = TokenCounter()
        dep_graph = DependencyGraph()

        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_index = MetadataIndex(Path(tmpdir))
            scorer = RelevanceScorer(dep_graph, metadata_index)
            optimizer = ContextOptimizer(token_counter, scorer, dep_graph)
            yield optimizer

    @pytest.mark.asyncio
    async def test_optimize_by_priority(self, optimizer: ContextOptimizer) -> None:
        """Test priority-based optimization."""
        relevance_scores = {"high.md": 0.9, "medium.md": 0.5, "low.md": 0.1}

        files_content = {
            "high.md": "A" * 100,
            "medium.md": "B" * 100,
            "low.md": "C" * 100,
        }

        result = await optimizer.optimize_by_priority(
            relevance_scores, files_content, token_budget=200
        )

        assert "high.md" in result.selected_files
        assert result.total_tokens <= 200
        assert 0 <= result.utilization <= 1.0

    @pytest.mark.asyncio
    async def test_optimize_budget_enforcement(
        self, optimizer: ContextOptimizer
    ) -> None:
        """Test that budget is enforced."""
        relevance_scores = {"file1.md": 0.9, "file2.md": 0.8, "file3.md": 0.7}

        files_content = {
            "file1.md": "A" * 1000,  # Large files
            "file2.md": "B" * 1000,
            "file3.md": "C" * 1000,
        }

        result = await optimizer.optimize_by_priority(
            relevance_scores, files_content, token_budget=500
        )

        # Budget should be respected
        assert result.total_tokens <= 500


class TestProgressiveLoader:
    """Test progressive loading functionality."""

    @pytest.fixture
    async def loader(self):
        """Create a progressive loader."""
        from collections.abc import AsyncGenerator

        async def _loader() -> AsyncGenerator[ProgressiveLoader, None]:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmppath = Path(tmpdir)

                # Create test files
                (tmppath / "memory-bank").mkdir(exist_ok=True)
                _ = (tmppath / "memory-bank" / "test1.md").write_text("Test content 1")
                _ = (tmppath / "memory-bank" / "test2.md").write_text("Test content 2")

                fs_manager = FileSystemManager(tmppath)
                metadata_index = MetadataIndex(tmppath)
                token_counter = TokenCounter()
                dep_graph = DependencyGraph()
                scorer = RelevanceScorer(dep_graph, metadata_index)
                optimizer = ContextOptimizer(token_counter, scorer, dep_graph)

                loader = ProgressiveLoader(fs_manager, optimizer, metadata_index)
                yield loader

        async for item in _loader():
            yield item

    @pytest.mark.asyncio
    async def test_load_by_priority(self, loader: ProgressiveLoader) -> None:
        """Test loading by priority."""
        loaded = await loader.load_by_priority(
            task_description="Test task",
            token_budget=1000,
            priority_order=["test1.md", "test2.md"],
        )

        assert len(loaded) > 0
        # First file should have priority 0
        assert loaded[0].priority == 0

    def test_default_priority_order(self, loader: ProgressiveLoader) -> None:
        """Test default priority order."""
        order = loader.get_default_priority_order()

        assert "memorybankinstructions.md" in order
        assert "projectBrief.md" in order
        # memorybankinstructions should be first
        assert order[0] == "memorybankinstructions.md"


class TestSummarizationEngine:
    """Test summarization functionality."""

    @pytest.fixture
    async def engine(self):
        """Create a summarization engine."""
        from collections.abc import AsyncGenerator

        async def _engine() -> AsyncGenerator[SummarizationEngine, None]:
            with tempfile.TemporaryDirectory() as tmpdir:
                token_counter = TokenCounter()
                metadata_index = MetadataIndex(Path(tmpdir))
                engine = SummarizationEngine(token_counter, metadata_index)
                yield engine

        async for item in _engine():
            yield item

    @pytest.mark.asyncio
    async def test_summarize_file_key_sections(
        self, engine: SummarizationEngine
    ) -> None:
        """Test key section extraction."""
        content = (
            """
# Overview
This is the overview section with important information.

# Goals
The main goals of this project are listed here.

# Details
Very long detailed section with lots of verbose content that could be compressed.
"""
            * 10
        )  # Make it longer

        result = await engine.summarize_file(
            file_name="test.md",
            content=content,
            target_reduction=0.5,
            strategy="extract_key_sections",
        )

        original_tokens = result.get("original_tokens", 0)
        summarized_tokens = result.get("summarized_tokens", 0)
        reduction = result.get("reduction", 0.0)
        assert isinstance(original_tokens, (int, float))
        assert isinstance(summarized_tokens, (int, float))
        assert isinstance(reduction, (int, float))
        assert float(original_tokens) > 0
        assert float(summarized_tokens) < float(original_tokens)
        assert float(reduction) > 0
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_extract_headers_only(self, engine: SummarizationEngine) -> None:
        """Test headers-only extraction."""
        content = """
# Section 1
Long paragraph 1.
Long paragraph 2.
Long paragraph 3.

# Section 2
Another long paragraph.
More content here.
Even more content.
"""

        summary = await engine.extract_headers_only(content)

        assert "# Section 1" in summary
        assert "# Section 2" in summary
        # Should be shorter than original
        assert len(summary) < len(content)

    def test_parse_sections(self, engine: SummarizationEngine) -> None:
        """Test section parsing."""
        content = """
# Section 1
Content 1

# Section 2
Content 2
"""

        sections = engine.parse_sections(content)

        assert "Section 1" in sections
        assert "Section 2" in sections

    def test_score_section_importance(self, engine: SummarizationEngine) -> None:
        """Test section importance scoring."""
        # High-value section
        score1 = engine.score_section_importance("Goals", "Short content")
        # Low-value section
        score2 = engine.score_section_importance("Example Details", "Short content")

        assert 0.0 <= score1 <= 1.0
        assert 0.0 <= score2 <= 1.0
        assert score1 > score2  # Goals should score higher than examples


class TestOptimizationConfig:
    """Test optimization configuration."""

    @pytest.fixture
    def config(self) -> Generator[OptimizationConfig, None, None]:
        """Create optimization config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OptimizationConfig(Path(tmpdir))
            yield config

    def test_default_config(self, config: OptimizationConfig) -> None:
        """Test default configuration values."""
        assert config.get_token_budget() == 80000
        assert config.get_loading_strategy() == "dependency_aware"
        assert config.is_summarization_enabled() is True

    def test_get_set_config(self, config: OptimizationConfig) -> None:
        """Test getting and setting configuration."""
        # Set a value
        success = config.set("token_budget.default_budget", 50000)
        assert success is True

        # Get the value
        value = config.get("token_budget.default_budget")
        assert value == 50000

    def test_get_relevance_weights(self, config: OptimizationConfig) -> None:
        """Test getting relevance weights."""
        weights = config.get_relevance_weights()

        assert "keyword_weight" in weights
        assert "dependency_weight" in weights
        assert "recency_weight" in weights
        assert "quality_weight" in weights

        # Weights should sum to approximately 1.0
        total = sum(weights.values())
        assert 0.9 <= total <= 1.1

    def test_validate_config(self, config: OptimizationConfig) -> None:
        """Test configuration validation."""
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None

    def test_validate_invalid_config(self, config: OptimizationConfig) -> None:
        """Test validation with invalid config."""
        # Set invalid budget
        _ = config.set("token_budget.default_budget", -100)

        is_valid, error = config.validate()
        assert is_valid is False
        assert error is not None
        _ = error  # error assigned but not used after assertion

    @pytest.mark.asyncio
    async def test_reset_config(self, config: OptimizationConfig) -> None:
        """Test resetting configuration."""
        # Modify config
        _ = config.set("token_budget.default_budget", 50000)

        # Reset
        await config.reset()

        # Should be back to default
        assert config.get_token_budget() == 80000


def run_tests():
    """Run all Phase 4 tests."""
    print("Running Phase 4 Test Suite...")
    print("=" * 60)

    # Run pytest
    _ = pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
