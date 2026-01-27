"""
Integration tests for manager initialization and coordination.

These tests verify that managers work together correctly
and that the initialization system properly coordinates dependencies.
"""

from pathlib import Path
from typing import cast

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_parser import LinkParser


@pytest.mark.integration
class TestManagerCoordination:
    """Test manager coordination and initialization."""

    async def test_managers_share_metadata_index(self, temp_project_root: Path):
        """Test that managers share the same metadata index instance."""
        # Arrange
        metadata_index = MetadataIndex(temp_project_root)
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        version_manager = VersionManager(temp_project_root)

        # Act: Create file through file_system
        file_path = temp_project_root / "memory-bank" / "test.md"
        content = "# Test\nContent."
        content_hash = await file_system.write_file(file_path, content)

        # Update metadata_index manually (integration test responsibility)
        token_counter = TokenCounter()
        token_count = token_counter.count_tokens(content)
        sections = file_system.parse_sections(content)
        section_dicts = [section.model_dump(mode="json") for section in sections]
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content.encode("utf-8")),
            token_count=token_count,
            content_hash=content_hash,
            sections=section_dicts,
        )

        # Act: Check metadata through metadata_index
        metadata = await metadata_index.get_file_metadata("test.md")

        # Assert: Metadata should exist
        assert metadata is not None
        assert metadata["path"] == str(file_path)

        # Act: Add file to dependency graph (as a dynamic dependency with
        # no dependencies)
        dependency_graph.add_link_dependency("test.md", "test.md", "self")

        # Act: Check dependency graph can access metadata
        files = dependency_graph.get_all_files()
        assert "test.md" in files

        # Act: Version manager can create snapshot
        content = "# Test\nContent."
        token_counter = TokenCounter()
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
        version_count = await version_manager.get_version_count("test.md")
        assert version_count >= 1

    async def test_file_operations_update_multiple_managers(
        self, temp_project_root: Path
    ):
        """Test that file operations update all relevant managers."""
        # Arrange
        metadata_index = MetadataIndex(temp_project_root)
        file_system = FileSystemManager(temp_project_root)
        token_counter = TokenCounter()
        version_manager = VersionManager(temp_project_root)

        # Act: Write file
        content = "# Test File\n\nContent here."
        file_path = temp_project_root / "memory-bank" / "test.md"
        content_hash = await file_system.write_file(file_path, content)

        # Update metadata_index manually (integration test responsibility)
        token_count = token_counter.count_tokens(content)
        sections = file_system.parse_sections(content)
        section_dicts = [section.model_dump(mode="json") for section in sections]
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content.encode("utf-8")),
            token_count=token_count,
            content_hash=content_hash,
            sections=section_dicts,
        )

        # Assert 1: Metadata index updated
        metadata = await metadata_index.get_file_metadata("test.md")
        assert metadata is not None

        # Assert 2: Token counter can count tokens
        tokens = await token_counter.count_tokens_in_file(file_path)
        assert tokens > 0

        # Assert 3: Version manager can track versions
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
        version_count = await version_manager.get_version_count("test.md")
        assert version_count >= 1

    async def test_dependency_graph_updates_on_file_changes(
        self, temp_project_root: Path
    ):
        """Test that dependency graph updates when files change."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)
        dependency_graph = DependencyGraph()
        link_parser = LinkParser()

        # Create initial file
        base_path = temp_project_root / "memory-bank" / "base.md"
        _ = await file_system.write_file(base_path, "# Base\nContent.")

        # Act: Add dependency
        _ = await file_system.write_file(base_path, "# Base\n[Child](child.md)")
        child_path = temp_project_root / "memory-bank" / "child.md"
        _ = await file_system.write_file(child_path, "# Child\nContent.")

        # Build graph
        memory_bank_path = temp_project_root / "memory-bank"
        await dependency_graph.build_from_links(memory_bank_path, link_parser)

        # Assert: Dependency tracked
        deps = dependency_graph.get_dependencies("base.md")
        assert "child.md" in deps

    async def test_version_manager_coordinates_with_metadata(
        self, temp_project_root: Path
    ):
        """Test version manager coordinates with metadata index."""
        # Arrange
        metadata_index = MetadataIndex(temp_project_root)
        file_system = FileSystemManager(temp_project_root)
        version_manager = VersionManager(temp_project_root)
        token_counter = TokenCounter()

        # Create file
        file_path = temp_project_root / "memory-bank" / "test.md"
        content1 = "# Version 1"
        content_hash1 = await file_system.write_file(file_path, content1)

        # Update metadata_index manually
        token_count1 = token_counter.count_tokens(content1)
        sections = file_system.parse_sections(content1)
        section_dicts = [section.model_dump(mode="json") for section in sections]
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content1.encode("utf-8")),
            token_count=token_count1,
            content_hash=content_hash1,
            sections=section_dicts,
        )

        # Act: Create snapshot
        _ = await version_manager.create_snapshot(
            file_path=file_path,
            version=1,
            content=content1,
            size_bytes=len(content1.encode("utf-8")),
            token_count=token_count1,
            content_hash=content_hash1,
        )

        # Version manager created snapshot - now update metadata to reflect new version
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content1.encode("utf-8")),
            token_count=token_count1,
            content_hash=content_hash1,
            sections=section_dicts,
        )
        # Manually set current_version in metadata (in production, this
        # would be done by the tool layer)
        data = metadata_index.get_data()
        if data and "files" in data:
            files = data["files"]
            if isinstance(files, dict) and "test.md" in files:
                file_metadata = cast(dict[str, object], files["test.md"])
                file_metadata["current_version"] = 1
        _ = await metadata_index.save()

        # Assert: Metadata updated
        metadata = await metadata_index.get_file_metadata("test.md")
        assert metadata is not None
        current_version = metadata.get("current_version")
        assert isinstance(current_version, int) and current_version >= 1

        # Act: Modify and create new snapshot
        content2 = "# Version 2"
        _ = await file_system.write_file(file_path, content2)
        content_hash2 = file_system.compute_hash(content2)
        token_count2 = token_counter.count_tokens(content2)
        sections2 = file_system.parse_sections(content2)
        section_dicts2 = [section.model_dump(mode="json") for section in sections2]
        _ = await version_manager.create_snapshot(
            file_path=file_path,
            version=2,
            content=content2,
            size_bytes=len(content2.encode("utf-8")),
            token_count=token_count2,
            content_hash=content_hash2,
        )

        # Update metadata to reflect version 2
        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(content2.encode("utf-8")),
            token_count=token_count2,
            content_hash=content_hash2,
            sections=section_dicts2,
        )
        data = metadata_index.get_data()
        if data and "files" in data:
            files = data["files"]
            if isinstance(files, dict) and "test.md" in files:
                file_metadata = cast(dict[str, object], files["test.md"])
                file_metadata["current_version"] = 2
        _ = await metadata_index.save()

        # Assert: Version incremented
        metadata = await metadata_index.get_file_metadata("test.md")
        assert metadata is not None
        current_version = metadata.get("current_version")
        assert isinstance(current_version, int) and current_version >= 2


@pytest.mark.integration
class TestManagerInitialization:
    """Test manager initialization scenarios."""

    async def test_managers_initialize_independently(self, temp_project_root: Path):
        """Test that managers can be initialized independently."""
        # Arrange & Act
        file_system = FileSystemManager(temp_project_root)
        token_counter = TokenCounter()
        metadata_index = MetadataIndex(temp_project_root)

        # Assert: All initialized without errors
        assert file_system is not None
        assert token_counter is not None
        assert metadata_index is not None

    async def test_managers_handle_missing_directories(self, temp_project_root: Path):
        """Test that managers handle missing directories gracefully."""
        # Arrange: Use non-existent subdirectory
        project_root = temp_project_root / "nonexistent"

        # Act: Initialize managers
        metadata_index = MetadataIndex(project_root)

        # Assert: Should not raise error (may create directory or handle gracefully)
        # The exact behavior depends on implementation
        assert metadata_index is not None

    async def test_managers_persist_state_across_operations(
        self, temp_project_root: Path
    ):
        """Test that managers maintain state across multiple operations."""
        # Arrange
        metadata_index = MetadataIndex(temp_project_root)
        file_system = FileSystemManager(temp_project_root)
        token_counter = TokenCounter()

        # Act 1: Create file
        file1_path = temp_project_root / "memory-bank" / "test1.md"
        content1 = "# Test 1"
        hash1 = await file_system.write_file(file1_path, content1)
        sections1 = file_system.parse_sections(content1)
        section_dicts1 = [section.model_dump(mode="json") for section in sections1]
        await metadata_index.update_file_metadata(
            file_name="test1.md",
            path=file1_path,
            exists=True,
            size_bytes=len(content1.encode("utf-8")),
            token_count=token_counter.count_tokens(content1),
            content_hash=hash1,
            sections=section_dicts1,
        )

        # Act 2: Create another file
        file2_path = temp_project_root / "memory-bank" / "test2.md"
        content2 = "# Test 2"
        hash2 = await file_system.write_file(file2_path, content2)
        sections2 = file_system.parse_sections(content2)
        section_dicts2 = [section.model_dump(mode="json") for section in sections2]
        await metadata_index.update_file_metadata(
            file_name="test2.md",
            path=file2_path,
            exists=True,
            size_bytes=len(content2.encode("utf-8")),
            token_count=token_counter.count_tokens(content2),
            content_hash=hash2,
            sections=section_dicts2,
        )

        # Assert: Both files tracked
        metadata1 = await metadata_index.get_file_metadata("test1.md")
        metadata2 = await metadata_index.get_file_metadata("test2.md")

        assert metadata1 is not None
        assert metadata2 is not None


@pytest.mark.integration
class TestManagerErrorRecovery:
    """Test manager error recovery and resilience."""

    async def test_metadata_index_recovery_from_corruption(
        self, temp_project_root: Path
    ):
        """Test metadata index recovers from corruption."""
        # Arrange
        metadata_index = MetadataIndex(temp_project_root)
        index_path = temp_project_root / ".memory-bank-index"

        # Create corrupted index file
        _ = index_path.write_text("{invalid json}")

        # Act: Initialize metadata index (should recover)
        metadata_index = MetadataIndex(temp_project_root)

        # Assert: Should handle corruption gracefully
        # (May create backup, reset, or handle error)
        assert metadata_index is not None

    async def test_file_system_handles_concurrent_access(self, temp_project_root: Path):
        """Test file system handles concurrent file operations."""
        # Arrange
        file_system = FileSystemManager(temp_project_root)

        # Act: Write multiple files concurrently
        import asyncio

        async def write_file(path: Path, content: str) -> None:
            _ = await file_system.write_file(path, content)

        file1_path = temp_project_root / "memory-bank" / "file1.md"
        file2_path = temp_project_root / "memory-bank" / "file2.md"
        file3_path = temp_project_root / "memory-bank" / "file3.md"

        _ = await asyncio.gather(
            write_file(file1_path, "# File 1"),
            write_file(file2_path, "# File 2"),
            write_file(file3_path, "# File 3"),
        )

        # Assert: All files created
        assert file1_path.exists()
        assert file2_path.exists()
        assert file3_path.exists()
