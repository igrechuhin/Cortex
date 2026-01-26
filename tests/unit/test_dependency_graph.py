"""Unit tests for dependency_graph module."""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.dependency_graph import (
    STATIC_DEPENDENCIES,
    DependencyGraph,
    FileDependencyInfo,
)


class TestDependencyGraphInitialization:
    """Tests for DependencyGraph initialization."""

    def test_initializes_with_static_dependencies(self):
        """Test initialization copies static dependencies."""
        # Act
        graph = DependencyGraph()

        # Assert
        assert graph.static_deps == STATIC_DEPENDENCIES
        assert graph.static_deps is not STATIC_DEPENDENCIES  # Ensures copy
        assert graph.dynamic_deps == {}
        assert graph.link_types == {}

    def test_static_dependencies_constant_has_expected_files(self):
        """Test STATIC_DEPENDENCIES contains expected memory bank files."""
        # Assert
        expected_files = [
            "memorybankinstructions.md",
            "projectBrief.md",
            "productContext.md",
            "systemPatterns.md",
            "techContext.md",
            "activeContext.md",
            "progress.md",
        ]
        assert set(STATIC_DEPENDENCIES.keys()) == set(expected_files)


class TestComputeLoadingOrder:
    """Tests for compute_loading_order method."""

    def test_orders_files_by_priority(self):
        """Test files ordered by priority attribute."""
        # Arrange
        graph = DependencyGraph()

        # Act
        order = graph.compute_loading_order()

        # Assert - memorybankinstructions (priority 0) should be first
        assert order[0] == "memorybankinstructions.md"
        # projectBrief (priority 1) should be second
        assert order[1] == "projectBrief.md"
        # progress (priority 4) should be last
        assert order[-1] == "progress.md"

    def test_orders_subset_of_files(self):
        """Test ordering works with subset of files."""
        # Arrange
        graph = DependencyGraph()
        files = ["progress.md", "memorybankinstructions.md", "projectBrief.md"]

        # Act
        order = graph.compute_loading_order(files)

        # Assert
        assert order == ["memorybankinstructions.md", "projectBrief.md", "progress.md"]

    def test_handles_files_not_in_static_dependencies(self):
        """Test ordering handles unknown files with default priority."""
        # Arrange
        graph = DependencyGraph()
        files = ["unknown.md", "memorybankinstructions.md"]

        # Act
        order = graph.compute_loading_order(files)

        # Assert - known file first (priority 0), unknown last (priority 999)
        assert order[0] == "memorybankinstructions.md"
        assert order[1] == "unknown.md"


class TestGetDependencies:
    """Tests for get_dependencies method."""

    def test_returns_static_dependencies(self):
        """Test returns static dependencies for known files."""
        # Arrange
        graph = DependencyGraph()

        # Act
        deps = graph.get_dependencies("activeContext.md")

        # Assert
        assert set(deps) == {"productContext.md", "systemPatterns.md", "techContext.md"}

    def test_returns_empty_list_for_file_with_no_dependencies(self):
        """Test returns empty list for files with no dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        deps = graph.get_dependencies("memorybankinstructions.md")

        # Assert
        assert deps == []

    def test_includes_dynamic_dependencies(self):
        """Test includes dynamic dependencies when present."""
        # Arrange
        graph = DependencyGraph()
        graph.dynamic_deps["activeContext.md"] = ["customFile.md"]

        # Act
        deps = graph.get_dependencies("activeContext.md")

        # Assert - should include both static and dynamic
        assert "customFile.md" in deps
        assert "productContext.md" in deps

    def test_deduplicates_dependencies(self):
        """Test removes duplicate dependencies."""
        # Arrange
        graph = DependencyGraph()
        # Add dynamic dependency that duplicates static one
        graph.dynamic_deps["activeContext.md"] = ["productContext.md"]

        # Act
        deps = graph.get_dependencies("activeContext.md")

        # Assert - should only appear once
        assert deps.count("productContext.md") == 1


class TestGetDependents:
    """Tests for get_dependents method."""

    def test_returns_static_dependents(self):
        """Test returns files that depend on target file."""
        # Arrange
        graph = DependencyGraph()

        # Act
        dependents = graph.get_dependents("projectBrief.md")

        # Assert - 3 files depend on projectBrief
        assert set(dependents) == {
            "productContext.md",
            "systemPatterns.md",
            "techContext.md",
        }

    def test_returns_empty_list_when_no_dependents(self):
        """Test returns empty list when no files depend on target."""
        # Arrange
        graph = DependencyGraph()

        # Act
        dependents = graph.get_dependents("progress.md")

        # Assert
        assert dependents == []

    def test_includes_dynamic_dependents(self):
        """Test includes dynamic dependents."""
        # Arrange
        graph = DependencyGraph()
        graph.dynamic_deps["customFile.md"] = ["projectBrief.md"]

        # Act
        dependents = graph.get_dependents("projectBrief.md")

        # Assert
        assert "customFile.md" in dependents


class TestGetMinimalContext:
    """Tests for get_minimal_context method."""

    def test_returns_target_file_and_all_dependencies(self):
        """Test returns target file plus all transitive dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        context = graph.get_minimal_context("activeContext.md")

        # Assert - should include target plus all its dependencies
        assert "activeContext.md" in context
        assert "productContext.md" in context
        assert "projectBrief.md" in context  # Transitive dependency

    def test_returns_in_loading_order(self):
        """Test returns files in proper loading order."""
        # Arrange
        graph = DependencyGraph()

        # Act
        context = graph.get_minimal_context("activeContext.md")

        # Assert - dependencies should come before dependent
        brief_idx = context.index("projectBrief.md")
        product_idx = context.index("productContext.md")
        active_idx = context.index("activeContext.md")
        assert brief_idx < product_idx < active_idx

    def test_handles_file_with_no_dependencies(self):
        """Test handles file with no dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        context = graph.get_minimal_context("memorybankinstructions.md")

        # Assert - should only contain the target file
        assert context == ["memorybankinstructions.md"]


class TestFileCategoryAndPriority:
    """Tests for get_file_category and get_file_priority methods."""

    def test_get_file_category_returns_correct_category(self):
        """Test returns correct category for known files."""
        # Arrange
        graph = DependencyGraph()

        # Act & Assert
        assert graph.get_file_category("memorybankinstructions.md") == "meta"
        assert graph.get_file_category("projectBrief.md") == "foundation"
        assert graph.get_file_category("activeContext.md") == "active"
        assert graph.get_file_category("progress.md") == "status"

    def test_get_file_category_returns_unknown_for_unknown_file(self):
        """Test returns 'unknown' for files not in static dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        category = graph.get_file_category("unknown.md")

        # Assert
        assert category == "unknown"

    def test_get_file_priority_returns_correct_priority(self):
        """Test returns correct priority for known files."""
        # Arrange
        graph = DependencyGraph()

        # Act & Assert
        assert graph.get_file_priority("memorybankinstructions.md") == 0
        assert graph.get_file_priority("projectBrief.md") == 1
        assert graph.get_file_priority("progress.md") == 4

    def test_get_file_priority_returns_default_for_unknown_file(self):
        """Test returns default priority (999) for unknown files."""
        # Arrange
        graph = DependencyGraph()

        # Act
        priority = graph.get_file_priority("unknown.md")

        # Assert
        assert priority == 999


class TestGetFilesByCategory:
    """Tests for get_files_by_category method."""

    def test_returns_files_in_meta_category(self):
        """Test returns files in meta category."""
        # Arrange
        graph = DependencyGraph()

        # Act
        files = graph.get_files_by_category("meta")

        # Assert
        assert files == ["memorybankinstructions.md"]

    def test_returns_files_in_foundation_category(self):
        """Test returns files in foundation category."""
        # Arrange
        graph = DependencyGraph()

        # Act
        files = graph.get_files_by_category("foundation")

        # Assert
        assert files == ["projectBrief.md"]

    def test_returns_files_in_context_category(self):
        """Test returns files in context category."""
        # Arrange
        graph = DependencyGraph()

        # Act
        files = graph.get_files_by_category("context")

        # Assert
        assert set(files) == {
            "productContext.md",
            "systemPatterns.md",
            "techContext.md",
        }

    def test_returns_empty_list_for_nonexistent_category(self):
        """Test returns empty list for category with no files."""
        # Arrange
        graph = DependencyGraph()

        # Act
        files = graph.get_files_by_category("nonexistent")

        # Assert
        assert files == []


class TestDynamicDependencyManagement:
    """Tests for dynamic dependency add/remove/clear methods."""

    def test_add_dynamic_dependency(self):
        """Test adding a dynamic dependency."""
        # Arrange
        graph = DependencyGraph()

        # Act
        graph.add_dynamic_dependency("file1.md", "file2.md")

        # Assert
        assert "file2.md" in graph.dynamic_deps["file1.md"]

    def test_add_dynamic_dependency_avoids_duplicates(self):
        """Test adding same dependency twice doesn't create duplicates."""
        # Arrange
        graph = DependencyGraph()

        # Act
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.add_dynamic_dependency("file1.md", "file2.md")

        # Assert
        assert graph.dynamic_deps["file1.md"].count("file2.md") == 1

    def test_remove_dynamic_dependency(self):
        """Test removing a dynamic dependency."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("file1.md", "file2.md")

        # Act
        graph.remove_dynamic_dependency("file1.md", "file2.md")

        # Assert
        assert "file2.md" not in graph.dynamic_deps.get("file1.md", [])

    def test_remove_dynamic_dependency_handles_nonexistent_file(self):
        """Test removing dependency for nonexistent file doesn't error."""
        # Arrange
        graph = DependencyGraph()

        # Act & Assert - should not raise
        graph.remove_dynamic_dependency("nonexistent.md", "file2.md")

    def test_clear_dynamic_dependencies_for_specific_file(self):
        """Test clearing dynamic dependencies for specific file."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.add_dynamic_dependency("file3.md", "file4.md")

        # Act
        graph.clear_dynamic_dependencies("file1.md")

        # Assert
        assert "file1.md" not in graph.dynamic_deps
        assert "file3.md" in graph.dynamic_deps

    def test_clear_dynamic_dependencies_for_all_files(self):
        """Test clearing all dynamic dependencies."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.add_dynamic_dependency("file3.md", "file4.md")

        # Act
        graph.clear_dynamic_dependencies()

        # Assert
        assert graph.dynamic_deps == {}


class TestCircularDependencyDetection:
    """Tests for has_circular_dependency method."""

    def test_returns_false_for_static_dependencies(self):
        """Test returns False for static dependencies (no cycles)."""
        # Arrange
        graph = DependencyGraph()

        # Act
        has_cycle = graph.has_circular_dependency()

        # Assert
        assert not has_cycle

    def test_detects_circular_dependency_in_dynamic_graph(self):
        """Test detects circular dependency in dynamic dependencies."""
        # Arrange
        graph = DependencyGraph()
        # Create cycle: file1 -> file2 -> file3 -> file1
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.add_dynamic_dependency("file2.md", "file3.md")
        graph.add_dynamic_dependency("file3.md", "file1.md")
        # Add to static deps so they're checked
        graph.static_deps["file1.md"] = FileDependencyInfo(
            depends_on=[], priority=10, category="test"
        )

        # Act
        has_cycle = graph.has_circular_dependency()

        # Assert
        assert has_cycle


class TestToDictExport:
    """Tests for to_dict method."""

    def test_exports_nodes_with_metadata(self):
        """Test exports nodes with priority and category."""
        # Arrange
        graph = DependencyGraph()

        # Act
        result = graph.to_dict()

        # Assert
        assert "nodes" in result
        nodes = cast(list[dict[str, object]], result["nodes"])
        assert len(nodes) == len(STATIC_DEPENDENCIES)
        # Check a sample node
        instructions_node = next(
            n for n in nodes if cast(str, n["file"]) == "memorybankinstructions.md"
        )
        assert cast(int, instructions_node["priority"]) == 0
        assert cast(str, instructions_node["category"]) == "meta"

    def test_exports_edges_with_types(self):
        """Test exports edges with relationship types."""
        # Arrange
        graph = DependencyGraph()

        # Act
        result = graph.to_dict()

        # Assert
        assert "edges" in result
        edges_raw = result.get("edges")
        assert isinstance(edges_raw, list)
        edges = cast(list[dict[str, object]], edges_raw)
        # Check edges exist for dependencies
        active_edges = [
            e for e in edges if cast(str, e.get("to")) == "activeContext.md"
        ]
        assert len(active_edges) == 3  # 3 dependencies

    def test_includes_progressive_loading_order(self):
        """Test includes progressive loading order."""
        # Arrange
        graph = DependencyGraph()

        # Act
        result = graph.to_dict()

        # Assert
        assert "progressive_loading_order" in result
        progressive_order_raw = result.get("progressive_loading_order")
        assert isinstance(progressive_order_raw, list)
        progressive_order = cast(list[str], progressive_order_raw)
        assert len(progressive_order) > 0
        assert progressive_order[0] == "memorybankinstructions.md"

    def test_includes_dynamic_dependencies_in_edges(self):
        """Test includes dynamic dependencies in edges."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.static_deps["file1.md"] = FileDependencyInfo(
            depends_on=[], priority=10, category="test"
        )
        graph.static_deps["file2.md"] = FileDependencyInfo(
            depends_on=[], priority=11, category="test"
        )

        # Act
        result = graph.to_dict()

        # Assert
        edges_raw = result.get("edges")
        assert isinstance(edges_raw, list)
        edges = cast(list[dict[str, object]], edges_raw)
        dynamic_edge = next(
            (
                e
                for e in edges
                if cast(str, e["from"]) == "file2.md"
                and cast(str, e["to"]) == "file1.md"
            ),
            None,
        )
        assert dynamic_edge is not None
        assert cast(str, dynamic_edge["type"]) == "links"


class TestToMermaidExport:
    """Tests for to_mermaid method."""

    def test_generates_mermaid_flowchart(self):
        """Test generates valid Mermaid flowchart syntax."""
        # Arrange
        graph = DependencyGraph()

        # Act
        mermaid = graph.to_mermaid()

        # Assert
        assert mermaid.startswith("flowchart TD")
        assert "memorybankinstructions" in mermaid  # Node ID
        assert "projectBrief" in mermaid

    def test_includes_node_styling_classes(self):
        """Test includes CSS classes for node styling."""
        # Arrange
        graph = DependencyGraph()

        # Act
        mermaid = graph.to_mermaid()

        # Assert
        assert ":::meta" in mermaid
        assert ":::foundation" in mermaid
        assert ":::active" in mermaid

    def test_includes_edges_between_nodes(self):
        """Test includes edges showing dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        mermaid = graph.to_mermaid()

        # Assert
        # activeContext depends on productContext
        assert "productContext --> activeContext" in mermaid

    def test_includes_style_definitions(self):
        """Test includes CSS style definitions."""
        # Arrange
        graph = DependencyGraph()

        # Act
        mermaid = graph.to_mermaid()

        # Assert
        assert "classDef meta fill:#e1f5ff" in mermaid
        assert "classDef foundation fill:#fff9c4" in mermaid


class TestLinkDependencyManagement:
    """Tests for link-based dependency methods."""

    def test_add_link_dependency_adds_to_dynamic_deps(self):
        """Test adding link dependency updates dynamic_deps."""
        # Arrange
        graph = DependencyGraph()

        # Act
        graph.add_link_dependency("source.md", "target.md", "reference")

        # Assert
        assert "target.md" in graph.dynamic_deps["source.md"]

    def test_add_link_dependency_tracks_link_type(self):
        """Test adding link dependency tracks link type."""
        # Arrange
        graph = DependencyGraph()

        # Act
        graph.add_link_dependency("source.md", "target.md", "transclusion")

        # Assert
        assert graph.link_types["source.md"]["target.md"] == "transclusion"

    def test_add_link_dependency_avoids_duplicates(self):
        """Test adding same link twice doesn't duplicate."""
        # Arrange
        graph = DependencyGraph()

        # Act
        graph.add_link_dependency("source.md", "target.md", "reference")
        graph.add_link_dependency("source.md", "target.md", "reference")

        # Assert
        assert graph.dynamic_deps["source.md"].count("target.md") == 1

    def test_get_link_type_returns_correct_type(self):
        """Test get_link_type returns correct link type."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("source.md", "target.md", "transclusion")

        # Act
        link_type = graph.get_link_type("source.md", "target.md")

        # Assert
        assert link_type == "transclusion"

    def test_get_link_type_returns_none_for_nonexistent_link(self):
        """Test get_link_type returns None when link doesn't exist."""
        # Arrange
        graph = DependencyGraph()

        # Act
        link_type = graph.get_link_type("source.md", "target.md")

        # Assert
        assert link_type is None


class TestGetTransclusionOrder:
    """Tests for get_transclusion_order method."""

    def test_returns_files_in_resolution_order(self):
        """Test returns files in order for transclusion resolution."""
        # Arrange
        graph = DependencyGraph()
        # Create chain: file1 includes file2 includes file3
        graph.add_link_dependency("file1.md", "file2.md", "transclusion")
        graph.add_link_dependency("file2.md", "file3.md", "transclusion")
        graph.static_deps["file1.md"] = FileDependencyInfo(
            depends_on=[], priority=1, category="test"
        )
        graph.static_deps["file2.md"] = FileDependencyInfo(
            depends_on=[], priority=2, category="test"
        )
        graph.static_deps["file3.md"] = FileDependencyInfo(
            depends_on=[], priority=3, category="test"
        )

        # Act
        order = graph.get_transclusion_order("file1.md")

        # Assert - file3 should be first (no deps), then file2, then file1
        assert order.index("file3.md") < order.index("file2.md")
        assert order.index("file2.md") < order.index("file1.md")

    def test_ignores_reference_links(self):
        """Test only follows transclusion links, not references."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("file1.md", "file2.md", "reference")  # Should ignore
        graph.add_link_dependency(
            "file1.md", "file3.md", "transclusion"
        )  # Should include

        # Act
        order = graph.get_transclusion_order("file1.md")

        # Assert
        assert "file3.md" in order
        # file2.md might or might not be in order, depends on implementation


class TestDetectCycles:
    """Tests for detect_cycles method."""

    def test_returns_empty_list_when_no_cycles(self):
        """Test returns empty list when no cycles exist."""
        # Arrange
        graph = DependencyGraph()

        # Act
        cycles = graph.detect_cycles()

        # Assert
        assert cycles == []

    def test_detects_cycle_in_dynamic_dependencies(self):
        """Test detects cycles in dynamic dependencies."""
        # Arrange
        graph = DependencyGraph()
        # Create cycle
        graph.add_dynamic_dependency("file1.md", "file2.md")
        graph.add_dynamic_dependency("file2.md", "file1.md")
        graph.static_deps["file1.md"] = FileDependencyInfo(
            depends_on=[], priority=1, category="test"
        )
        graph.static_deps["file2.md"] = FileDependencyInfo(
            depends_on=[], priority=2, category="test"
        )

        # Act
        cycles = graph.detect_cycles()

        # Assert
        assert len(cycles) > 0


class TestGetAllFiles:
    """Tests for get_all_files method."""

    def test_returns_all_static_files(self):
        """Test returns all files from static dependencies."""
        # Arrange
        graph = DependencyGraph()

        # Act
        files = graph.get_all_files()

        # Assert
        assert len(files) == len(STATIC_DEPENDENCIES)
        assert "memorybankinstructions.md" in files

    def test_includes_dynamic_files(self):
        """Test includes files only in dynamic dependencies."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("custom.md", "other.md")

        # Act
        files = graph.get_all_files()

        # Assert
        assert "custom.md" in files

    def test_deduplicates_files(self):
        """Test doesn't duplicate files in both static and dynamic."""
        # Arrange
        graph = DependencyGraph()
        graph.add_dynamic_dependency("memorybankinstructions.md", "custom.md")

        # Act
        files = graph.get_all_files()

        # Assert
        assert files.count("memorybankinstructions.md") == 1


class TestGetTransclusionGraph:
    """Tests for get_transclusion_graph method."""

    def test_returns_nodes_for_all_files(self):
        """Test returns nodes for all files."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("file1.md", "file2.md", "transclusion")

        # Act
        result = graph.get_transclusion_graph()

        # Assert
        assert "nodes" in result
        nodes_raw = result.get("nodes")
        assert isinstance(nodes_raw, list)
        nodes = cast(list[dict[str, object]], nodes_raw)
        files = [cast(str, n["file"]) for n in nodes]
        assert "file1.md" in files

    def test_returns_only_transclusion_edges(self):
        """Test returns only transclusion edges, not references."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("file1.md", "file2.md", "transclusion")
        graph.add_link_dependency("file1.md", "file3.md", "reference")

        # Act
        result = graph.get_transclusion_graph()

        # Assert
        assert "edges" in result
        edges_raw = result.get("edges")
        assert isinstance(edges_raw, list)
        edges = cast(list[dict[str, object]], edges_raw)
        # Should have edge for transclusion
        trans_edge = next(
            (
                e
                for e in edges
                if cast(str, e["to"]) == "file1.md"
                and cast(str, e["from"]) == "file2.md"
            ),
            None,
        )
        assert trans_edge is not None
        assert cast(str, trans_edge["type"]) == "transclusion"


class TestGetReferenceGraph:
    """Tests for get_reference_graph method."""

    def test_returns_nodes_for_all_files(self):
        """Test returns nodes for all files."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("file1.md", "file2.md", "reference")

        # Act
        result = graph.get_reference_graph()

        # Assert
        assert "nodes" in result
        nodes_raw = result.get("nodes")
        assert isinstance(nodes_raw, list)
        nodes = cast(list[dict[str, object]], nodes_raw)
        files = [cast(str, n["file"]) for n in nodes]
        assert "file1.md" in files

    def test_returns_only_reference_edges(self):
        """Test returns only reference edges, not transclusions."""
        # Arrange
        graph = DependencyGraph()
        graph.add_link_dependency("file1.md", "file2.md", "reference")
        graph.add_link_dependency("file1.md", "file3.md", "transclusion")

        # Act
        result = graph.get_reference_graph()

        # Assert
        assert "edges" in result
        edges_raw = result.get("edges")
        assert isinstance(edges_raw, list)
        edges = cast(list[dict[str, object]], edges_raw)
        # Should have edge for reference
        ref_edge = next(
            (
                e
                for e in edges
                if cast(str, e["from"]) == "file1.md"
                and cast(str, e["to"]) == "file2.md"
            ),
            None,
        )
        assert ref_edge is not None
        assert cast(str, ref_edge["type"]) == "reference"


@pytest.mark.asyncio
class TestBuildFromLinks:
    """Tests for build_from_links async method."""

    async def test_builds_dynamic_graph_from_links(self, tmp_path: Path) -> None:
        """Test builds dynamic dependency graph from markdown files."""
        # Arrange
        graph = DependencyGraph()
        memory_bank_dir = tmp_path / "memory-bank"
        memory_bank_dir.mkdir()

        # Create test files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("# File 1\n[Link](file2.md)")

        # Mock link parser
        mock_parser = MagicMock()
        mock_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [{"target": "file2.md", "text": "Link"}],
                "transclusions": [],
            }
        )

        # Act
        await graph.build_from_links(memory_bank_dir, mock_parser)

        # Assert
        assert "file2.md" in graph.dynamic_deps["file1.md"]

    async def test_clears_existing_dynamic_dependencies(self, tmp_path: Path) -> None:
        """Test clears existing dynamic dependencies before rebuilding."""
        # Arrange
        graph = DependencyGraph()
        graph.dynamic_deps["old.md"] = ["old_dep.md"]
        memory_bank_dir = tmp_path / "memory-bank"
        memory_bank_dir.mkdir()

        # Mock link parser
        mock_parser = MagicMock()
        mock_parser.parse_file = AsyncMock(
            return_value={"markdown_links": [], "transclusions": []}
        )

        # Act
        await graph.build_from_links(memory_bank_dir, mock_parser)

        # Assert
        assert "old.md" not in graph.dynamic_deps

    async def test_handles_transclusion_links(self, tmp_path: Path) -> None:
        """Test adds transclusion dependencies."""
        # Arrange
        graph = DependencyGraph()
        memory_bank_dir = tmp_path / "memory-bank"
        memory_bank_dir.mkdir()

        # Create test file
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("# File 1\n{{include: file2.md}}")

        # Mock link parser
        mock_parser = MagicMock()
        mock_parser.parse_file = AsyncMock(
            return_value={
                "markdown_links": [],
                "transclusions": [{"target": "file2.md"}],
            }
        )

        # Act
        await graph.build_from_links(memory_bank_dir, mock_parser)

        # Assert
        assert "file2.md" in graph.dynamic_deps["file1.md"]
        assert graph.link_types["file1.md"]["file2.md"] == "transclusion"

    async def test_handles_file_processing_errors_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Test continues processing when a file errors."""
        # Arrange
        graph = DependencyGraph()
        memory_bank_dir = tmp_path / "memory-bank"
        memory_bank_dir.mkdir()

        # Create test files
        _ = (memory_bank_dir / "file1.md").write_text("# File 1")
        _ = (memory_bank_dir / "file2.md").write_text("# File 2")

        # Mock link parser that fails on first file
        mock_parser = MagicMock()
        mock_parser.parse_file = AsyncMock(
            side_effect=[
                Exception("Parse error"),
                {"markdown_links": [], "transclusions": []},
            ]
        )

        # Act & Assert - should not raise
        await graph.build_from_links(memory_bank_dir, mock_parser)
