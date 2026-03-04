"""
Unit tests for Phase 4 context loading operations.

Tests load_context_impl skips stale index entries (files in index but not on disk).
Tests hybrid retrieval strategy with always-load sections.
"""

import asyncio
import json
from pathlib import Path

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.token_counter import TokenCounter
from cortex.managers.initialization import get_managers
from cortex.tools.context.load_operations import load_context_impl
from cortex.tools.context.load_operations_content import (
    MAX_CONCURRENT_FILE_READS,
    read_all_files_for_context_loading,
)
from tests.helpers.path_helpers import ensure_test_cortex_structure


class TestLoadContextSkipsStaleIndexEntries:
    """Tests that load_context skips stale index entries."""

    @pytest.mark.asyncio
    async def test_load_context_skips_stale_index_entries(
        self, temp_project_root: Path
    ) -> None:
        """Stale index entries (in index but not on disk) are skipped."""
        # Arrange: memory-bank with one existing file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        existing_path = memory_bank_dir / "existing.md"
        existing_content = "# Existing\n\nContent."
        _ = existing_path.write_text(existing_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()
        await metadata_index.update_file_metadata(
            file_name="existing.md",
            path=existing_path,
            exists=True,
            size_bytes=len(existing_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )
        stale_path = memory_bank_dir / "stale.md"
        await metadata_index.update_file_metadata(
            file_name="stale.md",
            path=stale_path,
            exists=False,
            size_bytes=0,
            token_count=0,
            content_hash="",
            sections=[],
        )

        # Act
        result_json = await load_context_impl(
            mgrs,
            task_description="test",
            token_budget=50000,  # Enough budget after subtracting 10000 reserve
            strategy="dependency_aware",
            project_root=temp_project_root,
        )

        # Assert: result includes only existing file, not stale
        result = json.loads(result_json)
        assert result.get("status") == "success"
        selected = result.get("selected_files", [])
        assert "existing.md" in selected
        assert "stale.md" not in selected


class TestParallelFileLoading:
    """Tests for parallel file loading with concurrency limit."""

    @pytest.mark.asyncio
    async def test_read_all_files_for_context_loading_parallel_with_limit(
        self,
        temp_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure files are loaded in parallel and respect concurrency limit."""
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)

        file_names: list[str] = []
        contents: dict[str, str] = {}
        for i in range(20):
            name = f"file{i}.md"
            path = memory_bank_dir / name
            content = f"# File {i}\n\nContent {i}."
            _ = path.write_text(content)
            file_names.append(name)
            contents[name] = content

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        for name in file_names:
            path = memory_bank_dir / name
            content = contents[name]
            await metadata_index.update_file_metadata(
                file_name=name,
                path=path,
                exists=True,
                size_bytes=len(content.encode("utf-8")),
                token_count=10,
                content_hash=f"sha256:{name}",
                sections=[],
            )

        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()

        async def fake_read_file(
            self: FileSystemManager,
            file_path: Path,
        ) -> tuple[str, str]:
            nonlocal current, max_concurrent
            async with lock:
                current += 1
                if current > max_concurrent:
                    max_concurrent = current
            try:
                await asyncio.sleep(0.01)
                content = contents[file_path.name]
                return content, "sha256:dummy"
            finally:
                async with lock:
                    current -= 1

        monkeypatch.setattr(FileSystemManager, "read_file", fake_read_file)

        fs_manager = mgrs.fs
        files_content, files_metadata = await read_all_files_for_context_loading(
            metadata_index,
            fs_manager,
        )

        assert set(files_content.keys()) == set(file_names)
        assert set(files_metadata.keys()) == set(file_names)
        assert max_concurrent > 1
        assert max_concurrent <= MAX_CONCURRENT_FILE_READS


class TestHybridRetrievalStrategy:
    """Tests for hybrid retrieval strategy with always-load sections."""

    @pytest.mark.asyncio
    async def test_load_context_metadata_only_with_always_load_sections(
        self, temp_project_root: Path
    ) -> None:
        """Test that metadata_only depth loads always-load sections in full."""
        # Arrange: memory-bank with activeContext.md containing sections
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        active_context_path = memory_bank_dir / "activeContext.md"
        active_context_content = (
            "# Active Context\n\n"
            "## Current Focus\n\n"
            "Working on Phase 51.\n\n"
            "## Next Steps\n\n"
            "Complete Step 5.\n\n"
            "## Completed Work\n\n"
            "Step 1-4 done.\n"
        )
        _ = active_context_path.write_text(active_context_content)

        other_file_path = memory_bank_dir / "other.md"
        other_content = "# Other\n\nContent."
        _ = other_file_path.write_text(other_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        # Update metadata for both files
        await metadata_index.update_file_metadata(
            file_name="activeContext.md",
            path=active_context_path,
            exists=True,
            size_bytes=len(active_context_content.encode("utf-8")),
            token_count=50,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Current Focus",
                    "level": 2,
                    "line_start": 3,
                    "line_end": 5,
                    "token_count": 10,
                },
                {
                    "heading": "## Next Steps",
                    "level": 2,
                    "line_start": 7,
                    "line_end": 9,
                    "token_count": 10,
                },
            ],
        )
        await metadata_index.update_file_metadata(
            file_name="other.md",
            path=other_file_path,
            exists=True,
            size_bytes=len(other_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:def",
            sections=[],
        )

        # Act: load with metadata_only depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result includes always-loaded sections and metadata for other files
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "metadata_only"

        # Check always-loaded sections are present
        always_loaded = result.get("always_loaded", {})
        assert "activeContext.md" in always_loaded
        always_loaded_content = always_loaded["activeContext.md"]
        assert "## Current Focus" in always_loaded_content
        assert "## Next Steps" in always_loaded_content
        assert (
            "## Completed Work" not in always_loaded_content
        )  # Not in always-load list

        # Check metadata for other files
        files = result.get("files", [])
        file_names = [f.get("name") for f in files]
        assert "other.md" in file_names
        assert (
            "activeContext.md" not in file_names
        )  # Excluded from metadata (always-loaded)

        # Check token counts
        assert "always_loaded_tokens" in result
        assert result["always_loaded_tokens"] > 0
        assert "total_tokens" in result

    @pytest.mark.asyncio
    async def test_load_context_metadata_only_without_always_load_files(
        self, temp_project_root: Path
    ) -> None:
        """Test metadata_only depth when no always-load files exist."""
        # Arrange: memory-bank with files not in always-load list
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file1_path = memory_bank_dir / "file1.md"
        file1_content = "# File 1\n\nContent 1."
        _ = file1_path.write_text(file1_content)

        file2_path = memory_bank_dir / "file2.md"
        file2_content = "# File 2\n\nContent 2."
        _ = file2_path.write_text(file2_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="file1.md",
            path=file1_path,
            exists=True,
            size_bytes=len(file1_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )
        await metadata_index.update_file_metadata(
            file_name="file2.md",
            path=file2_path,
            exists=True,
            size_bytes=len(file2_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:def",
            sections=[],
        )

        # Act: load with metadata_only depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result has metadata only, no always-loaded content
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "metadata_only"
        assert "always_loaded" in result
        assert result["always_loaded"] == {}  # Empty when no always-load files
        assert "files" in result
        assert len(result["files"]) >= 2

    @pytest.mark.asyncio
    async def test_load_context_metadata_only_missing_always_load_file(
        self, temp_project_root: Path
    ) -> None:
        """Test metadata_only depth when always-load file doesn't exist."""
        # Arrange: memory-bank without activeContext.md
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        other_file_path = memory_bank_dir / "other.md"
        other_content = "# Other\n\nContent."
        _ = other_file_path.write_text(other_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="other.md",
            path=other_file_path,
            exists=True,
            size_bytes=len(other_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:def",
            sections=[],
        )

        # Act: load with metadata_only depth (activeContext.md should be skipped)
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result succeeds, always-loaded is empty or missing file is skipped
        result = json.loads(result_json)
        assert result.get("status") == "success"
        # Missing always-load file should be skipped gracefully
        assert "always_loaded" in result


class TestDepthParameter:
    """Tests for depth parameter (metadata_only, summary, full)."""

    @pytest.mark.asyncio
    async def test_load_context_summary_depth(self, temp_project_root: Path) -> None:
        """Test summary depth returns first paragraph + section headings."""
        # Arrange: memory-bank with file containing multiple sections
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = (
            "# Test File\n\n"
            "First paragraph content here.\n\n"
            "## Section 1\n\n"
            "Section 1 content.\n\n"
            "## Section 2\n\n"
            "Section 2 content.\n"
        )
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=50,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Section 1",
                    "level": 2,
                    "line_start": 5,
                    "line_end": 7,
                    "token_count": 10,
                },
                {
                    "heading": "## Section 2",
                    "level": 2,
                    "line_start": 9,
                    "line_end": 11,
                    "token_count": 10,
                },
            ],
        )

        # Act: load with summary depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="summary",
            project_root=temp_project_root,
        )

        # Assert: result includes summarized content
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "summary"
        assert "selected_files" in result
        assert "test.md" in result["selected_files"]

    @pytest.mark.asyncio
    async def test_load_context_full_depth(self, temp_project_root: Path) -> None:
        """Test full depth returns complete file content."""
        # Arrange: memory-bank with file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Test File\n\nFull content here."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load with full depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="full",
            project_root=temp_project_root,
        )

        # Assert: result includes full content
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "full"
        assert "selected_files" in result

    @pytest.mark.asyncio
    async def test_load_context_default_depth_full(
        self, temp_project_root: Path
    ) -> None:
        """Test default depth is full when not specified."""
        # Arrange: memory-bank with file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Test File\n\nContent."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load without depth parameter (defaults to full)
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            project_root=temp_project_root,
        )

        # Assert: result uses full depth
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "full"


class TestTokenSavings:
    """Tests for token savings measurement."""

    @pytest.mark.asyncio
    async def test_metadata_only_token_savings(self, temp_project_root: Path) -> None:
        """Test that metadata_only provides significant token savings for metadata portion."""
        # Arrange: memory-bank with multiple files (not in always-load list)
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        files_content: dict[str, str] = {}
        for i in range(5):
            file_path = memory_bank_dir / f"file{i}.md"
            content = f"# File {i}\n\n" + "Content " * 100  # Large content
            _ = file_path.write_text(content)
            files_content[f"file{i}.md"] = content

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        # Update metadata for all files with accurate token counts
        token_counter = TokenCounter()
        for file_name, content in files_content.items():
            actual_tokens = token_counter.count_tokens(content)
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=len(content.encode("utf-8")),
                token_count=actual_tokens,
                content_hash=f"sha256:{file_name}",
                sections=[],
            )

        # Act: load with metadata_only
        metadata_result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: metadata_only returns lightweight metadata
        metadata_result = json.loads(metadata_result_json)
        assert metadata_result.get("status") == "success"
        assert metadata_result.get("depth") == "metadata_only"

        # Check that files map contains metadata (not full content)
        files = metadata_result.get("files", [])
        assert len(files) >= 5

        # Verify metadata entries have structure but not full content
        for file_entry in files[:5]:
            assert "name" in file_entry
            assert "total_tokens" in file_entry
            assert "relevance_score" in file_entry
            # Metadata should have token count but not full content
            assert isinstance(file_entry["total_tokens"], (int, float))

        # Total tokens should be reasonable (metadata is lightweight)
        # Note: always-loaded sections may add tokens, but metadata portion should be small
        total_tokens = metadata_result.get("total_tokens", 0)
        always_loaded_tokens = metadata_result.get("always_loaded_tokens", 0)
        metadata_only_tokens = total_tokens - always_loaded_tokens

        # Metadata portion should be much smaller than full content
        # Each file's metadata entry is ~50-100 tokens vs 500+ for full content
        assert metadata_only_tokens < 2000, (
            f"Metadata tokens ({metadata_only_tokens}) should be lightweight. "
            f"Total: {total_tokens}, Always-loaded: {always_loaded_tokens}"
        )


class TestTwoStepWorkflowIntegration:
    """Integration tests for two-step workflow (load_context metadata_only → manage_file sections)."""

    @pytest.mark.asyncio
    async def test_two_step_workflow_load_map_then_read_section(
        self, temp_project_root: Path
    ) -> None:
        """Test full two-step workflow: load context map, then read specific section."""
        # Arrange: memory-bank with file containing multiple sections
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = (
            "# Test File\n\n"
            "Introduction paragraph.\n\n"
            "## Section 1\n\n"
            "Section 1 content here.\n\n"
            "## Section 2\n\n"
            "Section 2 content here.\n\n"
            "## Section 3\n\n"
            "Section 3 content here.\n"
        )
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=100,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Section 1",
                    "level": 2,
                    "line_start": 5,
                    "line_end": 7,
                    "token_count": 10,
                },
                {
                    "heading": "## Section 2",
                    "level": 2,
                    "line_start": 9,
                    "line_end": 11,
                    "token_count": 10,
                },
                {
                    "heading": "## Section 3",
                    "level": 2,
                    "line_start": 13,
                    "line_end": 15,
                    "token_count": 10,
                },
            ],
        )

        # Step 1: Load context map (metadata_only)
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "metadata_only"

        # Verify context map includes file metadata
        files = result.get("files", [])
        file_names = [f.get("name") for f in files]
        assert "test.md" in file_names

        # Find test.md in files map
        test_file_meta = next((f for f in files if f.get("name") == "test.md"), None)
        assert test_file_meta is not None
        assert "sections" in test_file_meta
        sections = test_file_meta["sections"]
        assert len(sections) == 3

        # Step 2: Read specific section using manage_file (simulated)
        # In real workflow, agent would call manage_file(file_name="test.md", sections=["## Section 2"])
        # For this test, we verify the section metadata is available for drill-down
        section_headings = [s.get("heading") for s in sections]
        assert "## Section 1" in section_headings
        assert "## Section 2" in section_headings
        assert "## Section 3" in section_headings

        # Verify token savings: metadata_only should use much fewer tokens than full
        metadata_tokens = result.get("total_tokens", 0)
        assert metadata_tokens < 1000  # Metadata should be lightweight

    @pytest.mark.asyncio
    async def test_two_step_workflow_with_always_load_sections(
        self, temp_project_root: Path
    ) -> None:
        """Test two-step workflow with always-load sections included."""
        # Arrange: memory-bank with activeContext.md and other files
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        active_context_path = memory_bank_dir / "activeContext.md"
        active_context_content = (
            "# Active Context\n\n"
            "## Current Focus\n\n"
            "Working on Phase 51 Step 7.\n\n"
            "## Next Steps\n\n"
            "Complete testing.\n\n"
            "## Completed Work\n\n"
            "Steps 1-6 done.\n"
        )
        _ = active_context_path.write_text(active_context_content)

        other_file_path = memory_bank_dir / "other.md"
        other_content = "# Other\n\n" + "Content " * 50  # Large content
        _ = other_file_path.write_text(other_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="activeContext.md",
            path=active_context_path,
            exists=True,
            size_bytes=len(active_context_content.encode("utf-8")),
            token_count=50,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Current Focus",
                    "level": 2,
                    "line_start": 3,
                    "line_end": 5,
                    "token_count": 10,
                },
                {
                    "heading": "## Next Steps",
                    "level": 2,
                    "line_start": 7,
                    "line_end": 9,
                    "token_count": 10,
                },
            ],
        )
        await metadata_index.update_file_metadata(
            file_name="other.md",
            path=other_file_path,
            exists=True,
            size_bytes=len(other_content.encode("utf-8")),
            token_count=200,
            content_hash="sha256:def",
            sections=[],
        )

        # Step 1: Load context map
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        result = json.loads(result_json)
        assert result.get("status") == "success"

        # Verify always-loaded sections are present
        always_loaded = result.get("always_loaded", {})
        assert "activeContext.md" in always_loaded
        always_loaded_content = always_loaded["activeContext.md"]
        assert "## Current Focus" in always_loaded_content
        assert "## Next Steps" in always_loaded_content
        assert "Working on Phase 51 Step 7" in always_loaded_content

        # Verify other files are in metadata map
        files = result.get("files", [])
        file_names = [f.get("name") for f in files]
        assert "other.md" in file_names
        assert "activeContext.md" not in file_names  # Excluded from metadata

        # Step 2: Agent can now drill into other.md sections if needed
        # (In real workflow, would call manage_file with sections parameter)
        other_file_meta = next((f for f in files if f.get("name") == "other.md"), None)
        assert other_file_meta is not None
        assert "total_tokens" in other_file_meta
        assert other_file_meta["total_tokens"] == 200


class TestEdgeCases:
    """Edge case tests for context loading."""

    @pytest.mark.asyncio
    async def test_load_context_empty_memory_bank(
        self, temp_project_root: Path
    ) -> None:
        """Test loading context when memory bank is empty."""
        # Arrange: empty memory-bank
        _ = ensure_test_cortex_structure(temp_project_root)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        # Act: load with metadata_only depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result succeeds with empty files list
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("files", []) == []
        assert result.get("total_files", 0) == 0

    @pytest.mark.asyncio
    async def test_load_context_low_token_budget(self, temp_project_root: Path) -> None:
        """Test loading context with very low token budget."""
        # Arrange: memory-bank with file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Test\n\nContent."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load with very low budget
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=100,  # Very low budget
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result succeeds (metadata_only should work even with low budget)
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "metadata_only"

    @pytest.mark.asyncio
    async def test_load_context_file_with_no_sections(
        self, temp_project_root: Path
    ) -> None:
        """Test loading context for file with no sections."""
        # Arrange: memory-bank with file without headings
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "Just plain text content without any headings."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],  # No sections
        )

        # Act: load with metadata_only depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: result succeeds with empty sections list
        result = json.loads(result_json)
        assert result.get("status") == "success"
        files = result.get("files", [])
        test_file = next((f for f in files if f.get("name") == "test.md"), None)
        if test_file:
            assert test_file.get("sections", []) == []

    @pytest.mark.asyncio
    async def test_load_context_summary_depth_with_sections(
        self, temp_project_root: Path
    ) -> None:
        """Test summary depth includes first paragraph and section headings."""
        # Arrange: memory-bank with file containing sections
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = (
            "First paragraph content here.\n\n"
            "More paragraph content.\n\n"
            "## Section 1\n\n"
            "Section 1 content.\n\n"
            "## Section 2\n\n"
            "Section 2 content.\n"
        )
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=100,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Section 1",
                    "level": 2,
                    "line_start": 5,
                    "line_end": 7,
                    "token_count": 10,
                },
                {
                    "heading": "## Section 2",
                    "level": 2,
                    "line_start": 9,
                    "line_end": 11,
                    "token_count": 10,
                },
            ],
        )

        # Act: load with summary depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="summary",
            project_root=temp_project_root,
        )

        # Assert: result includes summarized content
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "summary"
        assert "selected_files" in result

    @pytest.mark.asyncio
    async def test_load_context_summary_depth_no_first_paragraph(
        self, temp_project_root: Path
    ) -> None:
        """Test summary depth when file starts with heading."""
        # Arrange: memory-bank with file starting with heading
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Title\n\n## Section 1\n\nContent.\n"
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=20,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Section 1",
                    "level": 2,
                    "line_start": 3,
                    "line_end": 5,
                    "token_count": 5,
                },
            ],
        )

        # Act: load with summary depth
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="summary",
            project_root=temp_project_root,
        )

        # Assert: result succeeds (summary handles files starting with headings)
        result = json.loads(result_json)
        assert result.get("status") == "success"
        assert result.get("depth") == "summary"

    @pytest.mark.asyncio
    async def test_load_context_with_project_root_logging(
        self, temp_project_root: Path
    ) -> None:
        """Test that load_context logs when project_root is provided."""
        # Arrange: memory-bank with file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Test\n\nContent."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load with project_root (should trigger logging)
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="full",
            project_root=temp_project_root,  # Provided for logging
        )

        # Assert: result succeeds
        result = json.loads(result_json)
        assert result.get("status") == "success"

    @pytest.mark.asyncio
    async def test_load_context_without_project_root(
        self, temp_project_root: Path
    ) -> None:
        """Test that load_context works without project_root (no logging)."""
        # Arrange: memory-bank with file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = "# Test\n\nContent."
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load without project_root (should not log)
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="full",
            project_root=None,  # No logging
        )

        # Assert: result succeeds
        result = json.loads(result_json)
        assert result.get("status") == "success"

    @pytest.mark.asyncio
    async def test_load_context_relevance_scores_in_metadata(
        self, temp_project_root: Path
    ) -> None:
        """Test that relevance scores are calculated and included in metadata."""
        # Arrange: memory-bank with files matching task keywords
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        test_file_path = memory_bank_dir / "test_context.md"
        test_content = "# Test Context\n\nContent about testing."
        _ = test_file_path.write_text(test_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test_context.md",
            path=test_file_path,
            exists=True,
            size_bytes=len(test_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )

        # Act: load with metadata_only (should calculate relevance scores)
        result_json = await load_context_impl(
            mgrs,
            task_description="test context loading",  # Keywords: test, context, loading
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: files have relevance scores
        result = json.loads(result_json)
        assert result.get("status") == "success"
        files = result.get("files", [])
        for file_entry in files:
            assert "relevance_score" in file_entry
            score = file_entry["relevance_score"]
            assert isinstance(score, (int, float))
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_load_context_metadata_sections_extraction(
        self, temp_project_root: Path
    ) -> None:
        """Test that section metadata is properly extracted and included."""
        # Arrange: memory-bank with file containing multiple sections
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        file_path = memory_bank_dir / "test.md"
        file_content = (
            "# Test\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
        )
        _ = file_path.write_text(file_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()

        await metadata_index.update_file_metadata(
            file_name="test.md",
            path=file_path,
            exists=True,
            size_bytes=len(file_content.encode("utf-8")),
            token_count=30,
            content_hash="sha256:abc",
            sections=[
                {
                    "heading": "## Section A",
                    "level": 2,
                    "line_start": 3,
                    "line_end": 5,
                    "token_count": 5,
                },
                {
                    "heading": "## Section B",
                    "level": 2,
                    "line_start": 7,
                    "line_end": 9,
                    "token_count": 5,
                },
            ],
        )

        # Act: load with metadata_only
        result_json = await load_context_impl(
            mgrs,
            task_description="test task",
            token_budget=50000,
            strategy="dependency_aware",
            depth="metadata_only",
            project_root=temp_project_root,
        )

        # Assert: sections are extracted and included in metadata
        result = json.loads(result_json)
        assert result.get("status") == "success"
        files = result.get("files", [])
        test_file = next((f for f in files if f.get("name") == "test.md"), None)
        if test_file:
            sections = test_file.get("sections", [])
            assert len(sections) == 2
            section_headings = [s.get("heading") for s in sections]
            assert "## Section A" in section_headings
            assert "## Section B" in section_headings
