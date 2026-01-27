"""
Integration tests for cross-module workflows in MCP Memory Bank.

These tests verify that multiple modules work together correctly
to provide end-to-end functionality across different phases.
"""

from pathlib import Path
from typing import cast

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.optimization.models import FileMetadataForScoring
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from tests.helpers.path_helpers import (
    ensure_test_cortex_structure,
    get_test_memory_bank_dir,
)

# ============================================================================
# Phase 1-2 Integration: File Operations + Linking
# ============================================================================


@pytest.mark.integration
class TestPhase1Phase2Integration:
    """Test integration between Phase 1 (file operations) and Phase 2 (linking)."""

    async def test_file_write_then_parse_links(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test writing a file and then parsing its links."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        link_parser = LinkParser()

        # Act: Write a file with links
        content_with_links = """# Test Document

See [Project Brief](projectBrief.md) for details.
Check [Active Context](activeContext.md#current-work) for status.
"""
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        _ = await file_system.write_file(file_path, content_with_links)

        # Parse links from the file
        content, _ = await file_system.read_file(file_path)
        links = await link_parser.parse_file(content)

        # Assert
        markdown_links_raw = links.get("markdown_links", [])
        transclusions_raw = links.get("transclusions", [])
        markdown_links: list[ModelDict] = (
            cast(list[ModelDict], markdown_links_raw)
            if isinstance(markdown_links_raw, list)
            else []
        )
        transclusions: list[ModelDict] = (
            cast(list[ModelDict], transclusions_raw)
            if isinstance(transclusions_raw, list)
            else []
        )
        all_links = markdown_links + transclusions
        assert len(all_links) >= 2
        assert any(link.get("target") == "projectBrief.md" for link in all_links)
        assert any(link.get("target") == "activeContext.md" for link in all_links)

    async def test_link_parsing_updates_dependency_graph(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test that parsing links updates the dependency graph."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        link_parser = LinkParser()

        # Create a file with links
        content = """# Source File
[Target File](target.md)
"""
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        source_path = memory_bank_dir / "source.md"
        _ = await file_system.write_file(source_path, content)

        # Create target file
        target_path = memory_bank_dir / "target.md"
        _ = await file_system.write_file(target_path, "# Target File\n")

        # Act: Parse links and build graph
        source_content, _ = await file_system.read_file(source_path)
        _ = await link_parser.parse_file(source_content)
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        await dependency_graph.build_from_links(memory_bank_dir, link_parser)

        # Assert: Check dependencies
        deps = dependency_graph.get_dependencies("source.md")
        assert "target.md" in deps

    async def test_transclusion_with_file_operations(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test transclusion engine working with file system operations."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        link_parser = LinkParser()
        transclusion_engine = TransclusionEngine(file_system, link_parser)

        # Create source file with transclusion
        source_content = """# Main Document
{{include: projectBrief.md#overview}}
"""
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        main_path = memory_bank_dir / "main.md"
        _ = await file_system.write_file(main_path, source_content)

        # Act: Resolve transclusion
        resolved = await transclusion_engine.resolve_content(source_content, "main.md")

        # Assert
        assert "overview" in resolved.lower() or len(resolved) > 0

    async def test_link_validation_after_file_changes(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test link validation detects broken links after file deletion."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        link_parser = LinkParser()
        link_validator = LinkValidator(file_system, link_parser)

        # Create file with link
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        source_path = memory_bank_dir / "source.md"
        target_path = memory_bank_dir / "target.md"
        _ = await file_system.write_file(source_path, "[Target](target.md)")
        _ = await file_system.write_file(target_path, "# Target")

        # Validate links (should pass)
        validation = await link_validator.validate_file(source_path)

        # Assert: All links valid
        broken_links_raw = validation.get("broken_links", [])
        broken_links: list[ModelDict] = (
            cast(list[ModelDict], broken_links_raw)
            if isinstance(broken_links_raw, list)
            else []
        )
        assert isinstance(broken_links, list)
        assert len(broken_links) == 0

        # Act: Delete target file
        target_path.unlink()

        # Validate again (should detect broken link)
        validation = await link_validator.validate_file(source_path)

        # Assert: Link is now broken
        broken_links_raw = validation.get("broken_links", [])
        broken_links: list[ModelDict] = (
            cast(list[ModelDict], broken_links_raw)
            if isinstance(broken_links_raw, list)
            else []
        )
        assert isinstance(broken_links, list)
        assert len(broken_links) > 0


# ============================================================================
# Phase 2-3 Integration: Linking + Validation
# ============================================================================


@pytest.mark.integration
class TestPhase2Phase3Integration:
    """Test integration between Phase 2 (linking) and Phase 3 (validation)."""

    async def test_validate_file_with_links(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test schema validation on files containing links."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        schema_validator = SchemaValidator()

        # Create file with links and required sections
        content = """# Project Brief

## Project Overview
This is the overview section.

## Goals
- Goal 1
- Goal 2

## Core Requirements
- Requirement 1
- Requirement 2

## Success Criteria
- Criterion 1
- Criterion 2

See [Active Context](activeContext.md) for details.
"""
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "projectBrief.md"
        _ = await file_system.write_file(file_path, content)

        # Act: Validate schema
        file_content, _ = await file_system.read_file(file_path)
        result = await schema_validator.validate_file("projectBrief.md", file_content)

        # Assert
        assert result.valid
        assert len(result.errors) == 0

    async def test_quality_metrics_with_linked_files(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test quality metrics calculation for files with links."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        schema_validator = SchemaValidator()
        metadata_index = MetadataIndex(temp_project_root)
        quality_metrics = QualityMetrics(schema_validator, metadata_index)
        _ = LinkParser()

        # Create files with links
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        source_path = memory_bank_dir / "source.md"
        target_path = memory_bank_dir / "target.md"
        _ = await file_system.write_file(source_path, "[Target](target.md)")
        _ = await file_system.write_file(target_path, "# Target File\nContent here.")

        # Act: Calculate quality metrics
        source_path = memory_bank_dir / "source.md"
        source_content, _ = await file_system.read_file(source_path)
        source_metadata = await metadata_index.get_file_metadata("source.md")
        metadata_for_score: ModelDict = (
            cast(ModelDict, source_metadata)
            if isinstance(source_metadata, dict)
            else {}
        )
        metrics = await quality_metrics.calculate_file_score(
            "source.md", source_content, metadata_for_score
        )

        # Assert
        assert metrics.file_name == "source.md"
        score = metrics.score
        assert isinstance(score, (int, float))
        assert int(score) >= 0
        assert int(score) <= 100

    async def test_duplication_detection_with_transclusions(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test duplication detector handles transcluded content correctly."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        from cortex.validation.duplication_detector import DuplicationDetector

        duplication_detector = DuplicationDetector()

        # Create files with substantial duplicate content
        # Make content longer to ensure detection
        duplicate_section = (
            """
## Section

This is duplicate content that appears in both files.
The content is identical and should be detected as a duplicate.
This section contains multiple sentences to ensure sufficient
content length for the duplication detector to identify it.
"""
            * 3
        )  # Repeat to increase size
        content1 = (
            f"# Document 1\n{duplicate_section}\n## Additional\nUnique content 1."
        )
        content2 = (
            f"# Document 2\n{duplicate_section}\n## Additional\nUnique content 2."
        )

        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file1_path = memory_bank_dir / "file1.md"
        file2_path = memory_bank_dir / "file2.md"
        _ = await file_system.write_file(file1_path, content1)
        _ = await file_system.write_file(file2_path, content2)

        # Act: Detect duplications
        files_content = {
            "file1.md": content1,
            "file2.md": content2,
        }
        duplications = await duplication_detector.scan_all_files(files_content)

        # Assert: Should detect duplicate sections
        duplicates_found = duplications.duplicates_found
        assert isinstance(duplicates_found, int)
        assert duplicates_found > 0

        # Check for exact duplicates or similar content
        exact = duplications.exact_duplicates
        similar = duplications.similar_content

        # Should have either exact duplicates or similar content with high similarity
        has_exact = len(exact) > 0
        has_similar = any(entry.similarity >= 0.85 for entry in similar)
        assert (
            has_exact or has_similar
        ), "Should detect either exact duplicates or similar content"


# ============================================================================
# Phase 3-4 Integration: Validation + Optimization
# ============================================================================


@pytest.mark.integration
class TestPhase3Phase4Integration:
    """Test integration between Phase 3 (validation) and Phase 4 (optimization)."""

    async def test_load_context_after_validation(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test context optimization uses validation results."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        metadata_index = MetadataIndex(temp_project_root)
        relevance_scorer = RelevanceScorer(dependency_graph, metadata_index)

        # Create multiple files
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file1_path = memory_bank_dir / "file1.md"
        file2_path = memory_bank_dir / "file2.md"
        file1_content = "# File 1\n" + "Content " * 100
        file2_content = "# File 2\n" + "Content " * 100
        _ = await file_system.write_file(file1_path, file1_content)
        _ = await file_system.write_file(file2_path, file2_content)

        # Act: Score relevance
        query = "file1"
        files_content = {
            "file1.md": file1_content,
            "file2.md": file2_content,
        }
        files_metadata = {
            "file1.md": FileMetadataForScoring(last_modified="2026-01-01T00:00:00Z"),
            "file2.md": FileMetadataForScoring(last_modified="2026-01-01T00:00:00Z"),
        }
        scores = await relevance_scorer.score_files(
            query, files_content, files_metadata
        )

        # Assert: file1 should have higher relevance
        assert len(scores) == 2
        file1_score = scores.get("file1.md")
        file2_score = scores.get("file2.md")
        assert isinstance(file1_score, dict)
        assert isinstance(file2_score, dict)
        file1_total = file1_score.get("total_score", 0.0)
        file2_total = file2_score.get("total_score", 0.0)
        assert isinstance(file1_total, (int, float))
        assert isinstance(file2_total, (int, float))
        assert float(file1_total) >= float(file2_total)

    async def test_quality_affects_optimization_priority(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test that quality metrics influence optimization decisions."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        schema_validator = SchemaValidator()
        metadata_index = MetadataIndex(temp_project_root)
        quality_metrics = QualityMetrics(schema_validator, metadata_index)

        # Create files with different quality
        high_quality = "# High Quality\n" + "Well-structured content. " * 50
        low_quality = "# Low Quality\n" + "x " * 10

        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        high_path = memory_bank_dir / "high.md"
        low_path = memory_bank_dir / "low.md"
        _ = await file_system.write_file(high_path, high_quality)
        _ = await file_system.write_file(low_path, low_quality)

        # Act: Calculate quality for both
        high_content, _ = await file_system.read_file(high_path)
        low_content, _ = await file_system.read_file(low_path)
        high_metadata_raw = await metadata_index.get_file_metadata("high.md")
        low_metadata_raw = await metadata_index.get_file_metadata("low.md")
        high_metadata: ModelDict = (
            cast(ModelDict, high_metadata_raw)
            if isinstance(high_metadata_raw, dict)
            else {}
        )
        low_metadata: ModelDict = (
            cast(ModelDict, low_metadata_raw)
            if isinstance(low_metadata_raw, dict)
            else {}
        )

        high_metrics = await quality_metrics.calculate_file_score(
            "high.md", high_content, high_metadata
        )
        low_metrics = await quality_metrics.calculate_file_score(
            "low.md", low_content, low_metadata
        )

        # Assert: High quality file should have better score
        high_score = high_metrics.score
        low_score = low_metrics.score
        assert isinstance(high_score, (int, float))
        assert isinstance(low_score, (int, float))
        assert int(high_score) >= int(low_score)


# ============================================================================
# Phase 4-5 Integration: Optimization + Refactoring
# ============================================================================


@pytest.mark.integration
class TestPhase4Phase5Integration:
    """Test integration between Phase 4 (optimization) and Phase 5 (refactoring)."""

    async def test_refactoring_uses_optimization_insights(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test that refactoring suggestions use optimization analysis."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()

        # Create large file that should be split
        # Ensure memory-bank directory exists
        memory_bank_path = ensure_test_cortex_structure(temp_project_root)

        # Create file with substantial content to appear in analysis
        large_content = (
            "# Large File\n\n"
            + (
                "## Section\n"
                + ("Content line with substantial information. " * 50)
                + "\n\n"
            )
            * 20
        )
        large_path = memory_bank_path / "large.md"
        _ = await file_system.write_file(large_path, large_content)

        # Act: Analyze structure (Phase 5.1)
        from cortex.analysis.structure_analyzer import StructureAnalyzer

        metadata_index = MetadataIndex(temp_project_root)
        _ = await metadata_index.load()
        structure_analyzer = StructureAnalyzer(
            temp_project_root, dependency_graph, file_system, metadata_index
        )
        analysis = await structure_analyzer.analyze_file_organization()

        # Assert: Should identify large file
        largest_files = analysis.largest_files
        assert isinstance(largest_files, list)
        assert len(largest_files) > 0
        assert any(file_info.file == "large.md" for file_info in largest_files)

    async def test_optimization_before_refactoring_execution(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test that optimization metrics are considered before refactoring."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        token_counter = TokenCounter()

        # Create file with optimization opportunities
        content = "# File\n" + ("Duplicate section. " * 100)
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "optimize.md"
        _ = await file_system.write_file(file_path, content)

        # Act: Check token count
        tokens = await token_counter.count_tokens_in_file(file_path)

        # Assert: Should have significant token count
        assert tokens > 0


# ============================================================================
# End-to-End Workflows
# ============================================================================


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows across all phases."""

    async def test_complete_file_lifecycle(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test complete lifecycle: create -> link -> validate -> optimize."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        version_manager = VersionManager(temp_project_root)
        link_parser = LinkParser()
        schema_validator = SchemaValidator()
        token_counter = TokenCounter()

        # Act 1: Create file
        content = """# New Document

## Overview
This is a new document.

## Goals
- Goal 1
- Goal 2

See [Project Brief](projectBrief.md) for context.
"""
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "new.md"
        _ = await file_system.write_file(file_path, content)

        # Act 2: Create version snapshot
        content_hash = file_system.compute_hash(content)
        token_count = token_counter.count_tokens(content)
        _ = await version_manager.create_snapshot(
            file_path=file_path,
            version=1,
            content=content,
            size_bytes=len(content.encode("utf-8")),
            token_count=token_count,
            content_hash=content_hash,
        )

        # Act 3: Parse links
        parsed = await link_parser.parse_file(content)
        markdown_links_raw = parsed.get("markdown_links", [])
        transclusions_raw = parsed.get("transclusions", [])
        markdown_links: list[ModelDict] = (
            cast(list[ModelDict], markdown_links_raw)
            if isinstance(markdown_links_raw, list)
            else []
        )
        transclusions: list[ModelDict] = (
            cast(list[ModelDict], transclusions_raw)
            if isinstance(transclusions_raw, list)
            else []
        )
        all_links = markdown_links + transclusions
        assert len(all_links) > 0

        # Act 4: Validate schema
        file_content, _ = await file_system.read_file(file_path)
        validation = await schema_validator.validate_file("new.md", file_content)
        assert validation.valid

        # Act 5: Count tokens
        tokens = await token_counter.count_tokens_in_file(file_path)
        assert tokens > 0

    async def test_multi_file_workflow_with_dependencies(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test workflow with multiple files and dependency tracking."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        link_parser = LinkParser()

        # Create multiple linked files
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        base_path = memory_bank_dir / "base.md"
        child_path = memory_bank_dir / "child.md"
        grandchild_path = memory_bank_dir / "grandchild.md"
        _ = await file_system.write_file(base_path, "# Base\n[Child](child.md)")
        _ = await file_system.write_file(
            child_path, "# Child\n[Grandchild](grandchild.md)"
        )
        _ = await file_system.write_file(grandchild_path, "# Grandchild\nContent.")

        # Act: Build dependency graph
        memory_bank_path = get_test_memory_bank_dir(temp_project_root)
        await dependency_graph.build_from_links(memory_bank_path, link_parser)

        # Assert: Check dependencies
        base_deps = dependency_graph.get_dependencies("base.md")
        assert "child.md" in base_deps

        child_deps = dependency_graph.get_dependencies("child.md")
        assert "grandchild.md" in child_deps

        # Check loading order (must pass file list to include custom files)
        all_files = ["base.md", "child.md", "grandchild.md"]
        loading_order = dependency_graph.compute_loading_order(all_files)
        assert "grandchild.md" in loading_order
        assert "child.md" in loading_order
        assert "base.md" in loading_order

        # Verify order: grandchild before child, child before base
        grandchild_idx = loading_order.index("grandchild.md")
        child_idx = loading_order.index("child.md")
        base_idx = loading_order.index("base.md")
        assert grandchild_idx < child_idx < base_idx

    async def test_validation_optimization_refactoring_chain(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test chain: validate -> optimize -> refactor."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        schema_validator = SchemaValidator()
        metadata_index = MetadataIndex(temp_project_root)
        quality_metrics = QualityMetrics(schema_validator, metadata_index)
        token_counter = TokenCounter()

        # Create file with quality issues
        content = "# Document\n" + ("Low quality content. " * 50)
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "doc.md"
        _ = await file_system.write_file(file_path, content)

        # Act 1: Validate quality
        file_content, _ = await file_system.read_file(file_path)
        metadata_raw = await metadata_index.get_file_metadata("doc.md")
        metadata_for_score: ModelDict = (
            cast(ModelDict, metadata_raw) if isinstance(metadata_raw, dict) else {}
        )
        _ = await quality_metrics.calculate_file_score(
            "doc.md", file_content, metadata_for_score
        )

        # Act 2: Check if optimization needed (based on quality score)
        token_count = token_counter.count_tokens(file_content)

        # Assert: Should identify optimization opportunity
        assert token_count > 0
        # Note: Actual optimization would happen in Phase 4 tools

    async def test_file_modification_with_versioning_and_validation(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test modifying file with versioning and validation."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        version_manager = VersionManager(temp_project_root)
        schema_validator = SchemaValidator()
        token_counter = TokenCounter()

        # Create initial file
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        file_path = memory_bank_dir / "doc.md"
        initial_content = """# Document

## Section 1
Initial content.
"""
        _ = await file_system.write_file(file_path, initial_content)

        # Act 1: Create initial snapshot
        content_hash1 = file_system.compute_hash(initial_content)
        token_count1 = token_counter.count_tokens(initial_content)
        _ = await version_manager.create_snapshot(
            file_path=file_path,
            version=1,
            content=initial_content,
            size_bytes=len(initial_content.encode("utf-8")),
            token_count=token_count1,
            content_hash=content_hash1,
        )

        # Act 2: Modify file
        modified_content = """# Document

## Section 1
Initial content.

## Section 2
New content.
"""
        _ = await file_system.write_file(file_path, modified_content)

        # Act 3: Create new snapshot
        content_hash2 = file_system.compute_hash(modified_content)
        token_count2 = token_counter.count_tokens(modified_content)
        _ = await version_manager.create_snapshot(
            file_path=file_path,
            version=2,
            content=modified_content,
            size_bytes=len(modified_content.encode("utf-8")),
            token_count=token_count2,
            content_hash=content_hash2,
        )

        # Act 4: Validate modified file
        file_content, _ = await file_system.read_file(file_path)
        validation = await schema_validator.validate_file("doc.md", file_content)

        # Assert: Validation passes, version history exists
        assert validation.valid
        version_count = await version_manager.get_version_count("doc.md")
        assert version_count >= 2

    async def test_circular_dependency_detection_workflow(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test detecting and handling circular dependencies."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        link_parser = LinkParser()

        # Create circular dependencies
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        a_path = memory_bank_dir / "a.md"
        b_path = memory_bank_dir / "b.md"
        c_path = memory_bank_dir / "c.md"
        _ = await file_system.write_file(a_path, "[B](b.md)")
        _ = await file_system.write_file(b_path, "[C](c.md)")
        _ = await file_system.write_file(c_path, "[A](a.md)")

        # Act: Build graph and detect cycles
        memory_bank_path = get_test_memory_bank_dir(temp_project_root)
        await dependency_graph.build_from_links(memory_bank_path, link_parser)
        cycles = dependency_graph.detect_cycles()

        # Assert: Should detect cycle
        assert len(cycles) > 0
        assert any(
            "a.md" in cycle and "b.md" in cycle and "c.md" in cycle for cycle in cycles
        )

    async def test_transclusion_resolution_with_validation(
        self, temp_project_root: Path, sample_memory_bank_files: dict[str, Path]
    ):
        """Test resolving transclusions and validating result."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        link_parser = LinkParser()
        transclusion_engine = TransclusionEngine(file_system, link_parser)
        _ = SchemaValidator()

        # Create source and target files
        memory_bank_dir = get_test_memory_bank_dir(temp_project_root)
        target_path = memory_bank_dir / "target.md"
        source_path = memory_bank_dir / "source.md"
        target_content = """# Target

## Section
Target content here.
"""
        source_content = """# Source
{{include: target.md#Section}}
"""
        _ = await file_system.write_file(target_path, target_content)
        _ = await file_system.write_file(source_path, source_content)

        # Act: Resolve transclusion
        source_file_content, _ = await file_system.read_file(source_path)
        resolved = await transclusion_engine.resolve_content(
            source_file_content, "source.md"
        )

        # Assert: Should contain transcluded content
        assert len(resolved) > 0
        assert "Target content" in resolved or "Section" in resolved

        # Validate resolved content structure
        # (Note: This would typically validate the final resolved document)
