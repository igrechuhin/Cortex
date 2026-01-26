"""
Tests for OptimizationStrategies module.

Tests different optimization strategies for context selection within token budgets.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.optimization.models import SectionScoreModel
from cortex.optimization.optimization_strategies import (
    OptimizationResult,
    OptimizationStrategies,
)


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_optimization_result_creation(self):
        """Test creating an OptimizationResult instance."""
        result = OptimizationResult(
            selected_files=["file1.md", "file2.md"],
            selected_sections={"file3.md": ["Section 1", "Section 2"]},
            total_tokens=500,
            utilization=0.5,
            excluded_files=["file4.md"],
            strategy_used="priority",
            metadata={"test": True},
        )

        assert result.selected_files == ["file1.md", "file2.md"]
        assert result.selected_sections == {"file3.md": ["Section 1", "Section 2"]}
        assert result.total_tokens == 500
        assert result.utilization == 0.5
        assert result.excluded_files == ["file4.md"]
        assert result.strategy_used == "priority"
        assert result.metadata == {"test": True}

    def test_optimization_result_with_empty_values(self):
        """Test OptimizationResult with empty values."""
        result = OptimizationResult(
            selected_files=[],
            selected_sections={},
            total_tokens=0,
            utilization=0.0,
            excluded_files=[],
            strategy_used="test",
            metadata={},
        )

        assert result.selected_files == []
        assert result.selected_sections == {}
        assert result.total_tokens == 0
        assert result.utilization == 0.0


class TestOptimizationStrategiesInitialization:
    """Tests for OptimizationStrategies initialization."""

    def test_init_with_all_parameters(
        self,
        mock_token_counter: MagicMock,
        mock_relevance_scorer: MagicMock,
        mock_dependency_graph: MagicMock,
    ):
        """Test initialization with all parameters."""
        mandatory_files = ["file1.md", "file2.md"]
        strategies = OptimizationStrategies(
            token_counter=mock_token_counter,
            relevance_scorer=mock_relevance_scorer,
            dependency_graph=mock_dependency_graph,
            mandatory_files=mandatory_files,
        )

        assert strategies.token_counter is mock_token_counter
        assert strategies.relevance_scorer is mock_relevance_scorer
        assert strategies.dependency_graph is mock_dependency_graph
        assert strategies.mandatory_files == mandatory_files

    def test_init_stores_references(
        self,
        mock_token_counter: MagicMock,
        mock_relevance_scorer: MagicMock,
        mock_dependency_graph: MagicMock,
    ):
        """Test that initialization stores references correctly."""
        strategies = OptimizationStrategies(
            token_counter=mock_token_counter,
            relevance_scorer=mock_relevance_scorer,
            dependency_graph=mock_dependency_graph,
            mandatory_files=["test.md"],
        )

        assert hasattr(strategies, "token_counter")
        assert hasattr(strategies, "relevance_scorer")
        assert hasattr(strategies, "dependency_graph")
        assert hasattr(strategies, "mandatory_files")


class TestOptimizeByPriority:
    """Tests for optimize_by_priority strategy."""

    @pytest.mark.asyncio
    async def test_optimize_by_priority_with_mandatory_files(self):
        """Test priority optimization includes mandatory files first."""
        # Setup mocks
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        mock_scorer = MagicMock()
        mock_graph = MagicMock()

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=mock_graph,
            mandatory_files=["mandatory.md"],
        )

        files_content = {
            "mandatory.md": "Mandatory content",
            "high.md": "High score content",
            "low.md": "Low score content",
        }
        relevance_scores = {"high.md": 0.9, "low.md": 0.3, "mandatory.md": 0.5}

        result = await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget=250
        )

        assert "mandatory.md" in result.selected_files
        assert result.strategy_used == "priority"

    @pytest.mark.asyncio
    async def test_optimize_by_priority_selects_highest_scores(self):
        """Test that priority optimization selects highest-scoring files."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {
            "high.md": "High score",
            "medium.md": "Medium score",
            "low.md": "Low score",
        }
        relevance_scores = {"high.md": 0.9, "medium.md": 0.6, "low.md": 0.3}

        result = await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget=250
        )

        # Should select high and medium, exclude low
        assert "high.md" in result.selected_files
        assert "medium.md" in result.selected_files
        assert "low.md" not in result.selected_files
        assert "low.md" in result.excluded_files

    @pytest.mark.asyncio
    async def test_optimize_by_priority_respects_token_budget(self):
        """Test that priority optimization respects token budget."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 150

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"file1.md": "Content 1", "file2.md": "Content 2"}
        relevance_scores = {"file1.md": 0.9, "file2.md": 0.8}

        result = await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget=200
        )

        # Can only fit one file (150 tokens), not both (300 tokens)
        assert len(result.selected_files) == 1
        assert result.total_tokens <= 200

    @pytest.mark.asyncio
    async def test_optimize_by_priority_calculates_utilization(self):
        """Test that utilization is calculated correctly."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"file1.md": "Content"}
        relevance_scores = {"file1.md": 0.9}

        result = await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget=500
        )

        # 100 tokens / 500 budget = 0.2 utilization
        assert result.utilization == 0.2
        assert result.total_tokens == 100

    @pytest.mark.asyncio
    async def test_optimize_by_priority_with_zero_budget(self):
        """Test priority optimization with zero budget."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"file1.md": "Content"}
        relevance_scores = {"file1.md": 0.9}

        result = await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget=0
        )

        assert result.selected_files == []
        assert result.total_tokens == 0
        assert result.utilization == 0.0

    @pytest.mark.asyncio
    async def test_optimize_by_priority_with_empty_files(self):
        """Test priority optimization with no files."""
        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        result = await strategies.optimize_by_priority({}, {}, token_budget=1000)

        assert result.selected_files == []
        assert result.excluded_files == []
        assert result.total_tokens == 0


class TestOptimizeByDependencies:
    """Tests for optimize_by_dependencies strategy."""

    @pytest.mark.asyncio
    async def test_optimize_by_dependencies_includes_dependencies(self):
        """Test that dependency optimization includes file dependencies."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 50

        mock_graph = MagicMock()

        def get_deps(f: str) -> list[str]:
            return ["dep.md"] if f == "main.md" else []

        mock_graph.get_dependencies.side_effect = get_deps

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {"main.md": "Main content", "dep.md": "Dependency content"}
        relevance_scores = {"main.md": 0.9, "dep.md": 0.3}

        result = await strategies.optimize_by_dependencies(
            relevance_scores, files_content, token_budget=150
        )

        # Should include both main and its dependency
        assert "main.md" in result.selected_files
        assert "dep.md" in result.selected_files

    @pytest.mark.asyncio
    async def test_optimize_by_dependencies_with_mandatory_files(self):
        """Test dependency optimization includes mandatory file dependencies."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        mock_graph = MagicMock()

        def get_deps(f: str) -> list[str]:
            return ["dep.md"] if f == "mandatory.md" else []

        mock_graph.get_dependencies.side_effect = get_deps

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=["mandatory.md"],
        )

        files_content = {
            "mandatory.md": "Mandatory",
            "dep.md": "Dependency",
            "other.md": "Other",
        }
        relevance_scores = {"mandatory.md": 0.5, "dep.md": 0.3, "other.md": 0.9}

        result = await strategies.optimize_by_dependencies(
            relevance_scores, files_content, token_budget=250
        )

        # Should include mandatory and its dependency
        assert "mandatory.md" in result.selected_files
        assert "dep.md" in result.selected_files

    @pytest.mark.asyncio
    async def test_optimize_by_dependencies_respects_budget(self):
        """Test that dependency optimization respects token budget."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 200

        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = ["dep.md"]

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {"main.md": "Main", "dep.md": "Dependency"}
        relevance_scores = {"main.md": 0.9, "dep.md": 0.8}

        result = await strategies.optimize_by_dependencies(
            relevance_scores, files_content, token_budget=300
        )

        # Budget too small for both files + dependency
        assert result.total_tokens <= 300

    @pytest.mark.asyncio
    async def test_optimize_by_dependencies_avoids_duplicates(self):
        """Test that shared dependencies are not counted twice."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 50

        mock_graph = MagicMock()
        # Both files depend on same dependency

        def get_deps(f: str) -> list[str]:
            return ["shared.md"] if f in ["file1.md", "file2.md"] else []

        mock_graph.get_dependencies.side_effect = get_deps

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {
            "file1.md": "File 1",
            "file2.md": "File 2",
            "shared.md": "Shared",
        }
        relevance_scores = {"file1.md": 0.9, "file2.md": 0.8, "shared.md": 0.5}

        result = await strategies.optimize_by_dependencies(
            relevance_scores, files_content, token_budget=200
        )

        # Should include all three files, but shared dep only counted once
        assert len(result.selected_files) == 3
        assert result.total_tokens == 150  # 50 * 3


class TestOptimizeWithSections:
    """Tests for optimize_with_sections strategy."""

    @pytest.mark.asyncio
    async def test_optimize_with_sections_includes_high_scoring_files(self):
        """Test that section optimization includes high-scoring files fully."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(return_value=[])

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"high.md": "High score", "low.md": "Low score"}
        relevance_scores = {"high.md": 0.9, "low.md": 0.3}

        result = await strategies.optimize_with_sections(
            "test task", relevance_scores, files_content, token_budget=250
        )

        # High-scoring file should be included fully
        assert "high.md" in result.selected_files
        assert "low.md" not in result.selected_files

    @pytest.mark.asyncio
    async def test_optimize_with_sections_scores_medium_files(self):
        """Test that medium-scoring files have sections scored."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 50

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(
            return_value=[
                SectionScoreModel(section="Section 1", score=0.8),
                SectionScoreModel(section="Section 2", score=0.6),
            ]
        )

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"medium.md": "# Section 1\nContent\n# Section 2\nMore"}
        relevance_scores = {"medium.md": 0.5}

        _ = await strategies.optimize_with_sections(
            "test task", relevance_scores, files_content, token_budget=200
        )

        # Should call score_sections for medium-scoring file
        mock_scorer.score_sections.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_with_sections_selects_high_scoring_sections(self):
        """Test that only high-scoring sections are selected."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 30

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(
            return_value=[
                SectionScoreModel(section="Good Section", score=0.8),
                SectionScoreModel(section="Bad Section", score=0.2),
            ]
        )

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"medium.md": "# Good Section\nContent\n# Bad Section\nMore"}
        relevance_scores = {"medium.md": 0.5}

        result = await strategies.optimize_with_sections(
            "test task", relevance_scores, files_content, token_budget=100
        )

        # Should only include high-scoring section
        assert "medium.md" in result.selected_sections
        sections = result.selected_sections["medium.md"]
        assert "Good Section" in sections
        assert "Bad Section" not in sections

    @pytest.mark.asyncio
    async def test_optimize_with_sections_respects_budget(self):
        """Test that section optimization respects token budget."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 150

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(
            return_value=[SectionScoreModel(section="Section", score=0.8)]
        )

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        files_content = {"medium.md": "# Section\nContent"}
        relevance_scores = {"medium.md": 0.5}

        result = await strategies.optimize_with_sections(
            "test task", relevance_scores, files_content, token_budget=100
        )

        # Budget too small to include section
        assert result.total_tokens <= 100


class TestOptimizeHybrid:
    """Tests for optimize_hybrid strategy."""

    @pytest.mark.asyncio
    async def test_optimize_hybrid_uses_dependency_strategy_first(self):
        """Test that hybrid strategy uses dependency-aware first."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(return_value=[])

        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = []

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {"high.md": "High", "low.md": "Low"}
        relevance_scores = {"high.md": 0.8, "low.md": 0.3}

        result = await strategies.optimize_hybrid(
            "test task", relevance_scores, files_content, token_budget=500
        )

        assert result.strategy_used == "hybrid"
        assert "high.md" in result.selected_files

    @pytest.mark.asyncio
    async def test_optimize_hybrid_fills_remaining_with_sections(self):
        """Test that hybrid fills remaining budget with sections."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 100

        mock_scorer = MagicMock()
        mock_scorer.score_sections = AsyncMock(
            return_value=[SectionScoreModel(section="Section", score=0.6)]
        )

        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = []

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=mock_scorer,
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {"high.md": "High", "medium.md": "# Section\nContent"}
        relevance_scores = {"high.md": 0.8, "medium.md": 0.5}

        result = await strategies.optimize_hybrid(
            "test task", relevance_scores, files_content, token_budget=300
        )

        # Should include high file and have metadata about phases
        assert "phase1_files" in result.metadata
        assert "phase2_sections" in result.metadata

    @pytest.mark.asyncio
    async def test_optimize_hybrid_returns_phase1_when_budget_full(self):
        """Test that hybrid returns phase1 result if budget is exhausted."""
        mock_counter = MagicMock()
        mock_counter.count_tokens.return_value = 500

        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = []

        strategies = OptimizationStrategies(
            token_counter=mock_counter,
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        files_content = {"high.md": "High"}
        relevance_scores = {"high.md": 0.8}

        result = await strategies.optimize_hybrid(
            "test task", relevance_scores, files_content, token_budget=500
        )

        # Budget fully used by phase 1, should return phase1 result
        assert result.total_tokens == 500


class TestGetAllDependencies:
    """Tests for get_all_dependencies helper method."""

    def test_get_all_dependencies_with_no_dependencies(self):
        """Test getting dependencies for file with no dependencies."""
        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = []

        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        deps = strategies.get_all_dependencies("standalone.md")

        assert deps == set()

    def test_get_all_dependencies_with_direct_dependencies(self):
        """Test getting direct dependencies."""
        mock_graph = MagicMock()

        def get_deps(f: str) -> list[str]:
            return ["dep.md"] if f == "main.md" else []

        mock_graph.get_dependencies.side_effect = get_deps

        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        deps = strategies.get_all_dependencies("main.md")

        assert deps == {"dep.md"}

    def test_get_all_dependencies_with_transitive_dependencies(self):
        """Test getting transitive dependencies (dep chain)."""
        mock_graph = MagicMock()

        def get_deps(f: str) -> list[str]:
            return {
                "main.md": ["dep1.md"],
                "dep1.md": ["dep2.md"],
                "dep2.md": [],
            }.get(f, [])

        mock_graph.get_dependencies.side_effect = get_deps

        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        deps = strategies.get_all_dependencies("main.md")

        assert deps == {"dep1.md", "dep2.md"}

    def test_get_all_dependencies_excludes_self(self):
        """Test that file itself is excluded from dependencies."""
        mock_graph = MagicMock()
        mock_graph.get_dependencies.return_value = ["dep.md"]

        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=mock_graph,
            mandatory_files=[],
        )

        deps = strategies.get_all_dependencies("main.md")

        assert "main.md" not in deps


class TestExtractSectionContent:
    """Tests for extract_section_content helper method."""

    def test_extract_section_content_single_section(self):
        """Test extracting a single section."""
        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        content = """# Section 1
Content of section 1
More content

# Section 2
Content of section 2"""

        result = strategies.extract_section_content(content, "Section 1")

        assert "# Section 1" in result
        assert "Content of section 1" in result
        assert "Section 2" not in result

    def test_extract_section_content_stops_at_next_section(self):
        """Test that extraction stops at next section header."""
        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        content = """# First
First content
# Second
Second content"""

        result = strategies.extract_section_content(content, "First")

        assert "First content" in result
        assert "Second" not in result

    def test_extract_section_content_partial_match(self):
        """Test extraction with partial section name match."""
        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        content = """# Overview Section
Content here

# Details
Other content"""

        result = strategies.extract_section_content(content, "Overview")

        assert "Content here" in result

    def test_extract_section_content_no_match(self):
        """Test extraction when section doesn't exist."""
        strategies = OptimizationStrategies(
            token_counter=MagicMock(),
            relevance_scorer=MagicMock(),
            dependency_graph=MagicMock(),
            mandatory_files=[],
        )

        content = """# Section 1
Content"""

        result = strategies.extract_section_content(content, "Nonexistent")

        assert result == ""
