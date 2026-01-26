"""
Tests for structure_analyzer.py - Structure analysis functionality.

This test module covers:
- StructureAnalyzer initialization
- File organization analysis
- Anti-pattern detection
- Complexity metrics measurement
- Dependency chain finding
- Assessment and grading
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.exceptions import MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex


@pytest.fixture
def mocked_dependency_graph(mocker: MockerFixture):
    """Create a properly mocked DependencyGraph for testing."""
    mock_graph = mocker.MagicMock()
    mock_graph.get_all_files = mocker.MagicMock(return_value=[])
    mock_graph.get_dependencies = mocker.MagicMock(return_value=[])
    mock_graph.get_dependents = mocker.MagicMock(return_value=[])
    return mock_graph


class TestStructureAnalyzerInitialization:
    """Tests for StructureAnalyzer initialization."""

    def test_initializes_with_managers(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test initialization with all required managers."""
        # Arrange & Act
        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Assert
        assert analyzer.project_root == Path(temp_project_root)
        assert analyzer.dependency_graph == mocked_dependency_graph
        assert analyzer.file_system == mock_file_system
        assert analyzer.metadata_index == mock_metadata_index


class TestFileOrganizationAnalysis:
    """Tests for file organization analysis."""

    @pytest.mark.asyncio
    async def test_raises_error_when_memory_bank_dir_missing(
        self,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ):
        """Test raises error when ".cortex" / "memory-bank" directory doesn't exist."""
        # Arrange - use tmp_path which doesn't have ".cortex" / "memory-bank" dir
        analyzer = StructureAnalyzer(
            tmp_path,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act & Assert
        with pytest.raises(MemoryBankError, match="Memory bank directory not found"):
            _ = await analyzer.analyze_file_organization()

    @pytest.mark.asyncio
    async def test_handles_empty_memory_bank(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test handles empty memory bank directory."""
        # Arrange - temp_project_root already has ".cortex" / "memory-bank" dir, so it should be empty
        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.analyze_file_organization()

        # Assert
        assert result.status == "empty"
        assert result.file_count == 0
        assert len(result.issues) > 0
        assert "No files found" in result.issues[0]

    @pytest.mark.asyncio
    async def test_analyzes_file_organization(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test analyzes file organization."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"

        # Create test files with different sizes
        _ = (memory_bank_dir / "small.md").write_text("Small content")
        _ = (memory_bank_dir / "medium.md").write_text("M" * 5000)
        _ = (memory_bank_dir / "large.md").write_text("L" * 60000)

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.analyze_file_organization()

        # Assert
        assert result.status == "analyzed"
        assert result.file_count == 3
        assert result.total_size_bytes > 0
        assert result.avg_size_bytes > 0
        assert len(result.largest_files) <= 5
        assert len(result.smallest_files) <= 5

    @pytest.mark.asyncio
    async def test_identifies_large_files_issue(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test identifies large files as an issue."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"

        # Create very large file (>50KB)
        _ = (memory_bank_dir / "huge.md").write_text("X" * 60000)

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.analyze_file_organization()

        # Assert
        assert any("very large" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_identifies_small_files_issue(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test identifies small files as an issue."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"

        # Create very small file (<500 bytes)
        _ = (memory_bank_dir / "tiny.md").write_text("X")

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.analyze_file_organization()

        # Assert
        assert any("very small" in issue for issue in result.issues)


class TestAntiPatternDetection:
    """Tests for anti-pattern detection."""

    @pytest.mark.asyncio
    async def test_detects_oversized_files(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test detects oversized files."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists

        # Create oversized file (>100KB)
        _ = (memory_bank_dir / "oversized.md").write_text("X" * 110000)

        # Mock dependency graph
        mocked_dependency_graph.get_all_files.return_value = ["oversized.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        assert isinstance(result, list)
        oversized = [p for p in result if p.type == "oversized_file"]
        assert len(oversized) > 0
        assert oversized[0].severity == "high"
        assert "oversized.md" in oversized[0].file

    @pytest.mark.asyncio
    async def test_detects_orphaned_files(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test detects orphaned files."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists
        _ = (memory_bank_dir / "orphan.md").write_text("Content")

        # Mock dependency graph - file has no connections
        mocked_dependency_graph.get_all_files.return_value = ["orphan.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        assert isinstance(result, list)
        orphaned = [p for p in result if p.type == "orphaned_file"]
        assert len(orphaned) > 0
        assert orphaned[0].severity == "medium"
        assert "orphan.md" in orphaned[0].file

    @pytest.mark.asyncio
    async def test_detects_excessive_dependencies(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test detects files with excessive dependencies."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists
        _ = (memory_bank_dir / "hub.md").write_text("Content")

        # Mock dependency graph - file depends on many files
        deps = [f"dep{i}.md" for i in range(20)]
        mocked_dependency_graph.get_all_files.return_value = ["hub.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.return_value = deps  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        excessive = [p for p in result if p.type == "excessive_dependencies"]
        assert len(excessive) > 0
        assert excessive[0].severity == "medium"
        assert excessive[0].dependency_count == 20

    @pytest.mark.asyncio
    async def test_detects_excessive_dependents(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test detects files with excessive dependents."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists
        _ = (memory_bank_dir / "central.md").write_text("Content")

        # Mock dependency graph - many files depend on this one
        dependents = [f"dependent{i}.md" for i in range(20)]
        mocked_dependency_graph.get_all_files.return_value = ["central.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        excessive = [p for p in result if p.type == "excessive_dependents"]
        assert len(excessive) > 0
        assert excessive[0].severity == "low"
        assert excessive[0].dependent_count == 20

    @pytest.mark.asyncio
    async def test_detects_similar_filenames(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test detects similar file names."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists
        _ = (memory_bank_dir / "user-guide.md").write_text("Content")
        _ = (memory_bank_dir / "user-guide-advanced.md").write_text("Content")

        mocked_dependency_graph.get_all_files.return_value = [  # type: ignore[reportAttributeAccessIssue]
            "user-guide.md",
            "user-guide-advanced.md",
        ]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        similar = [p for p in result if p["type"] == "similar_filenames"]
        assert len(similar) > 0
        assert similar[0]["severity"] == "low"

    @pytest.mark.asyncio
    async def test_sorts_anti_patterns_by_severity(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test sorts anti-patterns by severity."""
        # Arrange
        memory_bank_dir = Path(temp_project_root) / ".cortex" / "memory-bank"
        # memory_bank_dir already exists

        # Create files that will trigger different severity anti-patterns
        _ = (memory_bank_dir / "oversized.md").write_text("X" * 110000)  # high
        _ = (memory_bank_dir / "orphan.md").write_text("Content")  # medium

        mocked_dependency_graph.get_all_files.return_value = [  # type: ignore[reportAttributeAccessIssue]
            "oversized.md",
            "orphan.md",
        ]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.detect_anti_patterns()

        # Assert
        if len(result) >= 2:
            # High severity should come before medium
            assert result[0]["severity"] == "high"


class TestComplexityMetrics:
    """Tests for complexity metrics measurement."""

    @pytest.mark.asyncio
    async def test_handles_no_files(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test handles case with no files."""
        # Arrange
        mocked_dependency_graph.get_all_files.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        assert result["status"] == "no_files"

    @pytest.mark.asyncio
    async def test_calculates_dependency_depth(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test calculates maximum dependency depth."""

        # Arrange
        # Create a dependency chain: A -> B -> C
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {"a.md": ["b.md"], "b.md": ["c.md"], "c.md": []}
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = ["a.md", "b.md", "c.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        assert result.status == "analyzed"
        assert result.metrics.max_dependency_depth == 2

    @pytest.mark.asyncio
    async def test_calculates_cyclomatic_complexity(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test calculates cyclomatic complexity."""

        # Arrange
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {"a.md": ["b.md"], "b.md": ["c.md"], "c.md": []}
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = ["a.md", "b.md", "c.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        assert (
            result.metrics.cyclomatic_complexity == 0
        )  # edges - nodes + 1 = 2 - 3 + 1

    @pytest.mark.asyncio
    async def test_calculates_fan_in_fan_out(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test calculates fan-in and fan-out metrics."""

        # Arrange
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {"a.md": ["b.md", "c.md"], "b.md": [], "c.md": []}
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            dependents = {"b.md": ["a.md"], "c.md": ["a.md"], "a.md": []}
            return dependents.get(file_name, [])

        mocked_dependency_graph.get_all_files.return_value = ["a.md", "b.md", "c.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        assert result.metrics.max_fan_out == 2  # a.md depends on 2 files
        assert (
            result.metrics.max_fan_in == 1
        )  # b.md and c.md each depended on by 1 file

    @pytest.mark.asyncio
    async def test_identifies_complexity_hotspots(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test identifies complexity hotspots."""

        # Arrange
        # Create a file with high complexity (many dependencies and dependents)
        def mock_get_dependencies(file_name: str) -> list[str]:
            if file_name == "hub.md":
                return [f"dep{i}.md" for i in range(10)]
            return []

        def mock_get_dependents(file_name: str) -> list[str]:
            if file_name == "hub.md":
                return [f"dependent{i}.md" for i in range(10)]
            return []

        mocked_dependency_graph.get_all_files.return_value = ["hub.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        hotspots = result.complexity_hotspots
        assert isinstance(hotspots, list)
        assert len(hotspots) > 0
        hotspot = hotspots[0]
        assert hotspot.file == "hub.md"
        assert hotspot.score > 20

    @pytest.mark.asyncio
    async def test_includes_assessment(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test includes complexity assessment."""
        # Arrange
        mocked_dependency_graph.get_all_files.return_value = ["a.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.return_value = []  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.return_value = []  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.measure_complexity_metrics()

        # Assert
        assert result.assessment is not None
        assert result.assessment.score >= 0
        assert isinstance(result.assessment.grade, str)
        assert isinstance(result.assessment.status, str)


class TestComplexityAssessment:
    """Tests for complexity assessment logic."""

    def test_assess_excellent_complexity(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test assesses excellent complexity."""
        # Arrange
        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        assessment = analyzer.assess_complexity(max_depth=3, cyclomatic=5, avg_deps=2.0)

        # Assert
        assert assessment.score >= 90
        assert assessment.grade == "A"
        assert assessment.status == "excellent"

    def test_assess_poor_complexity(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test assesses poor complexity."""
        # Arrange
        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        assessment = analyzer.assess_complexity(
            max_depth=12, cyclomatic=25, avg_deps=12.0
        )

        # Assert
        assert assessment.score < 60
        assert assessment.grade == "F"
        assert assessment.status == "poor"
        assert len(assessment.issues) > 0
        assert len(assessment.recommendations) > 0

    def test_assess_moderate_complexity(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test assesses moderate complexity."""
        # Arrange
        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        assessment = analyzer.assess_complexity(
            max_depth=7, cyclomatic=12, avg_deps=6.0
        )

        # Assert
        assert 60 <= assessment.score < 90
        assert assessment.grade in ["B", "C", "D"]
        assert assessment.status in ["good", "acceptable", "needs_improvement"]


class TestDependencyChains:
    """Tests for dependency chain finding."""

    @pytest.mark.asyncio
    async def test_finds_linear_chains(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test finds linear dependency chains."""

        # Arrange
        # Create chain: A -> B -> C -> D
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {
                "a.md": ["b.md"],
                "b.md": ["c.md"],
                "c.md": ["d.md"],
                "d.md": [],
            }
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = [  # type: ignore[reportAttributeAccessIssue]
            "a.md",
            "b.md",
            "c.md",
            "d.md",
        ]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.find_dependency_chains(max_chain_length=10)

        # Assert
        assert isinstance(result, list)
        linear_chains = [c for c in result if c.get("type") == "linear"]
        assert len(linear_chains) > 0
        assert isinstance(linear_chains[0], dict)
        length = linear_chains[0].get("length")
        assert isinstance(length, (int, float))
        assert length >= 3

    @pytest.mark.asyncio
    async def test_finds_circular_chains(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test finds circular dependency chains."""

        # Arrange
        # Create circular dependency: A -> B -> C -> A
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {"a.md": ["b.md"], "b.md": ["c.md"], "c.md": ["a.md"]}
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = ["a.md", "b.md", "c.md"]  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.find_dependency_chains(max_chain_length=10)

        # Assert
        circular_chains = [c for c in result if c["type"] == "circular"]
        assert len(circular_chains) > 0

    @pytest.mark.asyncio
    async def test_respects_max_chain_length(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test respects maximum chain length parameter."""

        # Arrange
        # Create long chain
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {
                "a.md": ["b.md"],
                "b.md": ["c.md"],
                "c.md": ["d.md"],
                "d.md": ["e.md"],
                "e.md": ["f.md"],
                "f.md": [],
            }
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = [  # type: ignore[reportAttributeAccessIssue]
            "a.md",
            "b.md",
            "c.md",
            "d.md",
            "e.md",
            "f.md",
        ]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.find_dependency_chains(max_chain_length=3)

        # Assert
        assert isinstance(result, list)
        for chain in result:
            assert isinstance(chain, dict)
            length_val = chain.get("length")
            assert isinstance(length_val, (int, float))
            assert length_val <= 3

    @pytest.mark.asyncio
    async def test_sorts_chains_by_length(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test sorts chains by length (longest first)."""

        # Arrange
        # Create chains of different lengths
        def mock_get_dependencies(file_name: str) -> list[str]:
            deps = {
                "a.md": ["b.md"],
                "b.md": ["c.md"],
                "c.md": ["d.md"],
                "d.md": [],
                "x.md": ["y.md"],
                "y.md": [],
            }
            return deps.get(file_name, [])

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = [  # type: ignore[reportAttributeAccessIssue]
            "a.md",
            "b.md",
            "c.md",
            "d.md",
            "x.md",
            "y.md",
        ]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.find_dependency_chains(max_chain_length=10)

        # Assert
        assert isinstance(result, list)
        if len(result) >= 2:
            # Longest chains should come first
            chain0 = result[0]
            chain1 = result[1]
            assert isinstance(chain0, dict) and isinstance(chain1, dict)
            length0 = chain0.get("length")
            length1 = chain1.get("length")
            assert isinstance(length0, (int, float)) and isinstance(
                length1, (int, float)
            )
            assert length0 >= length1

    @pytest.mark.asyncio
    async def test_limits_results_to_top_20(
        self,
        temp_project_root: Path,
        mocked_dependency_graph: DependencyGraph,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test limits results to top 20 chains."""
        # Arrange
        # Create many chains
        files = [f"file{i}.md" for i in range(30)]

        def mock_get_dependencies(file_name: str) -> list[str]:
            # Each file depends on the next
            idx = files.index(file_name) if file_name in files else -1
            if idx >= 0 and idx < len(files) - 1:
                return [files[idx + 1]]
            return []

        def mock_get_dependents(file_name: str) -> list[str]:
            return []

        mocked_dependency_graph.get_all_files.return_value = files  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependencies.side_effect = mock_get_dependencies  # type: ignore[reportAttributeAccessIssue]
        mocked_dependency_graph.get_dependents.side_effect = mock_get_dependents  # type: ignore[reportAttributeAccessIssue]

        analyzer = StructureAnalyzer(
            temp_project_root,
            mocked_dependency_graph,
            mock_file_system,
            mock_metadata_index,
        )

        # Act
        result = await analyzer.find_dependency_chains(max_chain_length=30)

        # Assert
        assert len(result) <= 20
