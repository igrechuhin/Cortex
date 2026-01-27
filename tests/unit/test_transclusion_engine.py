"""Comprehensive tests for TransclusionEngine module.

Tests all functionality of the transclusion engine including:
- Content resolution with transclusion directives
- Recursive transclusion
- Circular dependency detection
- Section extraction
- Content caching
- Depth limiting
- Error handling

Part of Phase 7.2: Test Coverage Implementation
Target: 90%+ coverage for transclusion_engine.py
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
    TransclusionEngine,
)


class TestTransclusionEngineInitialization:
    """Tests for TransclusionEngine initialization."""

    @pytest.fixture
    def mock_fs(self) -> MagicMock:
        """Create a mock file system manager."""
        fs = MagicMock(spec=FileSystemManager)
        fs.memory_bank_dir = Path("/tmp/memory-bank")
        return fs

    @pytest.fixture
    def link_parser(self) -> LinkParser:
        """Create a real link parser."""
        return LinkParser()

    def test_initialization_with_defaults(
        self, mock_fs: MagicMock, link_parser: LinkParser
    ) -> None:
        """Test initialization with default parameters."""
        engine = TransclusionEngine(file_system=mock_fs, link_parser=link_parser)

        assert engine.fs == mock_fs
        assert engine.parser == link_parser
        assert engine.max_depth == 5
        assert engine.cache_enabled is True
        assert engine.cache == {}
        assert engine.cache_hits == 0
        assert engine.cache_misses == 0
        assert engine.resolution_stack == []

    def test_initialization_with_custom_max_depth(
        self, mock_fs: MagicMock, link_parser: LinkParser
    ) -> None:
        """Test initialization with custom max depth."""
        engine = TransclusionEngine(
            file_system=mock_fs, link_parser=link_parser, max_depth=10
        )

        assert engine.max_depth == 10

    def test_initialization_with_cache_disabled(
        self, mock_fs: MagicMock, link_parser: LinkParser
    ) -> None:
        """Test initialization with caching disabled."""
        engine = TransclusionEngine(
            file_system=mock_fs, link_parser=link_parser, cache_enabled=False
        )

        assert engine.cache_enabled is False


class TestResolveContent:
    """Tests for resolve_content method."""

    @pytest.fixture
    def mock_fs(self) -> MagicMock:
        """Create a mock file system manager."""
        fs = MagicMock(spec=FileSystemManager)
        fs.memory_bank_dir = Path("/tmp/memory-bank")
        return fs

    @pytest.fixture
    def link_parser(self) -> LinkParser:
        """Create a real link parser."""
        return LinkParser()

    @pytest.fixture
    def engine(self, mock_fs: MagicMock, link_parser: LinkParser) -> TransclusionEngine:
        """Create transclusion engine."""
        return TransclusionEngine(mock_fs, link_parser)

    @pytest.mark.asyncio
    async def test_resolve_content_with_no_transclusions(
        self, engine: TransclusionEngine
    ) -> None:
        """Test resolving content with no transclusions."""
        content = "# Title\n\nPlain text with no transclusions."

        result = await engine.resolve_content(content, "source.md")

        assert result == content

    @pytest.mark.asyncio
    async def test_resolve_content_with_simple_transclusion(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test resolving content with a simple transclusion."""
        content = "# Title\n\n{{include: other.md}}"
        target_content = "Included content from other.md"

        # Setup mock to return target content (content, hash)
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))
        _target_path = mock_fs.memory_bank_dir / "other.md"

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_content(content, "source.md")

        # Should replace transclusion directive with content
        assert "Included content from other.md" in result
        assert "{{include: other.md}}" not in result

    @pytest.mark.asyncio
    async def test_resolve_content_exceeds_max_depth(
        self, engine: TransclusionEngine
    ) -> None:
        """Test that max depth is enforced."""
        content = "{{include: other.md}}"

        with pytest.raises(MaxDepthExceededError) as exc_info:
            _ = await engine.resolve_content(content, "source.md", depth=10)

        assert "Maximum transclusion depth" in str(exc_info.value)
        assert "source.md" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_content_with_error_in_transclusion(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that errors are handled gracefully."""
        content = "{{include: missing.md}}"

        # Setup mock to raise FileNotFoundError
        _target_path = mock_fs.memory_bank_dir / "missing.md"

        with patch.object(Path, "exists", return_value=False):
            result = await engine.resolve_content(content, "source.md")

        # Should include error comment
        assert "<!-- TRANSCLUSION ERROR:" in result
        assert "{{include: missing.md}}" not in result

    @pytest.mark.asyncio
    async def test_resolve_content_with_multiple_transclusions(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test resolving content with multiple transclusions."""
        content = """# Title

{{include: file1.md}}

Some text

{{include: file2.md}}"""

        # Setup mocks
        async def mock_read(path: Path) -> tuple[str, str]:
            if "file1.md" in str(path):
                return ("Content from file1", "hash1")
            elif "file2.md" in str(path):
                return ("Content from file2", "hash2")
            return ("", "hash_empty")

        mock_fs.read_file = mock_read

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_content(content, "source.md")

        assert "Content from file1" in result
        assert "Content from file2" in result


class TestResolveTransclusion:
    """Tests for resolve_transclusion method."""

    @pytest.fixture
    def mock_fs(self) -> MagicMock:
        """Create a mock file system manager."""
        fs = MagicMock(spec=FileSystemManager)
        fs.memory_bank_dir = Path("/tmp/memory-bank")
        return fs

    @pytest.fixture
    def link_parser(self) -> LinkParser:
        """Create a real link parser."""
        return LinkParser()

    @pytest.fixture
    def engine(self, mock_fs: MagicMock, link_parser: LinkParser) -> TransclusionEngine:
        """Create transclusion engine."""
        return TransclusionEngine(mock_fs, link_parser)

    @pytest.mark.asyncio
    async def test_resolve_transclusion_basic(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test basic transclusion resolution."""
        target_content = "Target file content"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

        assert result == target_content

    @pytest.mark.asyncio
    async def test_resolve_transclusion_with_caching(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that caching works correctly."""
        target_content = "Target file content"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            # First call - cache miss
            result1 = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

            # Second call - cache hit
            result2 = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

        assert result1 == result2
        assert engine.cache_hits == 1
        assert engine.cache_misses == 1

    @pytest.mark.asyncio
    async def test_resolve_transclusion_cache_disabled(
        self, mock_fs: MagicMock, link_parser: LinkParser
    ) -> None:
        """Test resolution with caching disabled."""
        engine = TransclusionEngine(mock_fs, link_parser, cache_enabled=False)

        target_content = "Target file content"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            _ = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )
            _ = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

        # Both should be cache misses
        assert engine.cache_hits == 0
        assert engine.cache_misses == 2

    @pytest.mark.asyncio
    async def test_resolve_transclusion_circular_dependency(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that circular dependencies are detected."""
        # Simulate circular dependency by adding to resolution stack
        engine.resolution_stack.append("target.md")
        with pytest.raises(CircularDependencyError) as exc_info:
            _ = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

        assert "Circular dependency detected" in str(exc_info.value)
        assert "target.md" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_transclusion_file_not_found(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test handling of missing target file."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                _ = await engine.resolve_transclusion(
                    target_file="missing.md", source_file="source.md"
                )

        assert "Target file not found" in str(exc_info.value)
        assert "missing.md" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_transclusion_with_section(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test transclusion with section extraction."""
        target_content = """# Title

## Section One

Content of section one

## Section Two

Content of section two"""

        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md", section="Section One", source_file="source.md"
            )

        assert "Content of section one" in result
        assert "Content of section two" not in result

    @pytest.mark.asyncio
    async def test_resolve_transclusion_with_lines_limit(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test transclusion with lines limit."""
        target_content = "\n".join([f"Line {i}" for i in range(1, 11)])
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md", options={"lines": 3}, source_file="source.md"
            )

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "Line 1"
        assert lines[2] == "Line 3"

    @pytest.mark.asyncio
    async def test_resolve_transclusion_recursive_enabled(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test recursive transclusion (default behavior)."""
        # Target file contains another transclusion
        target_content = "Before {{include: nested.md}} After"
        nested_content = "Nested content"

        async def mock_read(path: Path) -> tuple[str, str]:
            if "target.md" in str(path):
                return (target_content, "hash_target")
            elif "nested.md" in str(path):
                return (nested_content, "hash_nested")
            return ("", "hash_empty")

        mock_fs.read_file = mock_read

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md",
                source_file="source.md",
                options={"recursive": True},
            )

        # Should resolve nested transclusion
        assert "Nested content" in result
        assert "{{include: nested.md}}" not in result

    @pytest.mark.asyncio
    async def test_resolve_transclusion_recursive_disabled(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that recursive can be disabled."""
        target_content = "Before {{include: nested.md}} After"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md",
                source_file="source.md",
                options={"recursive": False},
            )

        # Should NOT resolve nested transclusion
        assert "{{include: nested.md}}" in result

    @pytest.mark.asyncio
    async def test_resolve_transclusion_cleans_resolution_stack(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that resolution stack is cleaned up properly."""
        target_content = "Target content"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        # Stack should be empty initially
        assert len(engine.resolution_stack) == 0
        with patch.object(Path, "exists", return_value=True):
            _ = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md"
            )

        # Stack should be empty after resolution
        assert len(engine.resolution_stack) == 0


class TestExtractSection:
    """Tests for extract_section method."""

    @pytest.fixture
    def engine(self) -> TransclusionEngine:
        """Create transclusion engine."""
        fs = MagicMock()
        fs.memory_bank_dir = Path("/tmp")
        parser = LinkParser()
        return TransclusionEngine(fs, parser)

    def test_extract_section_basic(self, engine: TransclusionEngine) -> None:
        """Test basic section extraction."""
        content = """# Title

## Section One

Content of section one.

## Section Two

Content of section two."""

        result = engine.extract_section(content, "Section One")

        assert "Content of section one." in result
        assert "Section Two" not in result

    def test_extract_section_case_insensitive(self, engine: TransclusionEngine) -> None:
        """Test that section matching is case-insensitive."""
        content = """# Title

## Architecture

Design patterns."""

        result = engine.extract_section(content, "architecture")

        assert "Design patterns." in result

    def test_extract_section_with_different_heading_levels(
        self, engine: TransclusionEngine
    ) -> None:
        """Test extraction with various heading levels."""
        content = """# Top Level

## Second Level

Content here

### Third Level

More content

## Another Second Level"""

        result = engine.extract_section(content, "Second Level")

        assert "Content here" in result
        assert "Third Level" in result
        assert "Another Second Level" not in result

    def test_extract_section_at_end_of_file(self, engine: TransclusionEngine) -> None:
        """Test extracting section at end of file."""
        content = """# Title

## First Section

Content

## Last Section

Last content without following section."""

        result = engine.extract_section(content, "Last Section")

        assert "Last content without following section." in result

    def test_extract_section_with_lines_limit(self, engine: TransclusionEngine) -> None:
        """Test section extraction with line limit."""
        content = """# Title

## Section

Line 1
Line 2
Line 3
Line 4
Line 5"""

        result = engine.extract_section(content, "Section", lines_limit=2)

        # The section content starts with empty line, so lines_limit=2 gets
        # empty line + Line 1
        lines = result.split("\n")
        assert len(lines) <= 2

    def test_extract_section_not_found(self, engine: TransclusionEngine) -> None:
        """Test error when section not found."""
        content = """# Title

## Existing Section

Content"""

        with pytest.raises(ValueError) as exc_info:
            _ = engine.extract_section(content, "Nonexistent Section")

        assert "not found" in str(exc_info.value)
        assert "Nonexistent Section" in str(exc_info.value)

    def test_extract_section_strips_whitespace(
        self, engine: TransclusionEngine
    ) -> None:
        """Test that extracted section is stripped."""
        content = """# Title

## Section


Content with leading and trailing whitespace


## Next"""

        result = engine.extract_section(content, "Section")

        # Should strip leading/trailing whitespace but preserve internal
        assert not result.startswith("\n\n")
        assert not result.endswith("\n\n")
        assert "Content with leading and trailing whitespace" in result


class TestCircularDependencyDetection:
    """Tests for detect_circular_dependency method."""

    @pytest.fixture
    def engine(self) -> TransclusionEngine:
        """Create transclusion engine."""
        fs = MagicMock()
        fs.memory_bank_dir = Path("/tmp")
        parser = LinkParser()
        return TransclusionEngine(fs, parser)

    def test_detect_circular_dependency_empty_stack(
        self, engine: TransclusionEngine
    ) -> None:
        """Test detection with empty resolution stack."""
        assert engine.detect_circular_dependency("file.md") is False

    def test_detect_circular_dependency_file_in_stack(
        self, engine: TransclusionEngine
    ) -> None:
        """Test detection when file is in stack."""
        engine.resolution_stack = [
            "file1.md",
            "file2.md",
            "file3.md",
        ]
        assert engine.detect_circular_dependency("file2.md") is True

    def test_detect_circular_dependency_file_not_in_stack(
        self, engine: TransclusionEngine
    ) -> None:
        """Test detection when file is not in stack."""
        engine.resolution_stack = [
            "file1.md",
            "file2.md",
        ]
        assert engine.detect_circular_dependency("file3.md") is False


class TestCacheManagement:
    """Tests for cache management methods."""

    @pytest.fixture
    def engine(self) -> TransclusionEngine:
        """Create transclusion engine."""
        fs = MagicMock()
        fs.memory_bank_dir = Path("/tmp")
        parser = LinkParser()
        return TransclusionEngine(fs, parser)

    def test_clear_cache(self, engine: TransclusionEngine) -> None:
        """Test clearing the cache."""
        # Add some cache entries
        key1 = engine.make_cache_key("file1.md", None, {})
        key2 = engine.make_cache_key("file2.md", "section", {})
        engine.cache[key1] = "content1"
        engine.cache[key2] = "content2"
        engine.cache_hits = 5
        engine.cache_misses = 3
        engine.clear_cache()

        assert len(engine.cache) == 0
        assert engine.cache_hits == 0
        assert engine.cache_misses == 0

    def test_invalidate_cache_for_file(self, engine: TransclusionEngine) -> None:
        """Test invalidating cache entries for a specific file."""
        # Add cache entries
        key1 = engine.make_cache_key("file1.md", None, {})
        key2 = engine.make_cache_key("file1.md", "section", {})
        key3 = engine.make_cache_key("file2.md", None, {})
        engine.cache[key1] = "content1"
        engine.cache[key2] = "content2"
        engine.cache[key3] = "content3"

        engine.invalidate_cache_for_file("file1.md")

        # Should remove file1 entries but keep file2
        assert len(engine.cache) == 1
        assert key3 in engine.cache

    def test_invalidate_cache_for_file_no_matches(
        self, engine: TransclusionEngine
    ) -> None:
        """Test invalidating cache when file has no entries."""
        key1 = engine.make_cache_key("file1.md", None, {})
        engine.cache[key1] = "content1"

        engine.invalidate_cache_for_file("file2.md")

        # Should not remove any entries
        assert len(engine.cache) == 1

    def test_get_cache_stats_empty(self, engine: TransclusionEngine) -> None:
        """Test getting cache stats when empty."""
        stats = engine.get_cache_stats()

        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_requests"] == 0
        assert stats["hit_rate"] == 0.0

    def test_get_cache_stats_with_activity(self, engine: TransclusionEngine) -> None:
        """Test getting cache stats with activity."""
        engine.cache_hits = 7
        engine.cache_misses = 3
        key1 = engine.make_cache_key("file1.md", None, {})
        key2 = engine.make_cache_key("file2.md", "section", {})
        engine.cache[key1] = "content1"
        engine.cache[key2] = "content2"

        stats = engine.get_cache_stats()

        assert stats["entries"] == 2
        assert stats["hits"] == 7
        assert stats["misses"] == 3
        assert stats["total_requests"] == 10
        assert stats["hit_rate"] == 0.7


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def engine(self) -> TransclusionEngine:
        """Create transclusion engine."""
        fs = MagicMock()
        fs.memory_bank_dir = Path("/tmp")
        parser = LinkParser()
        return TransclusionEngine(fs, parser)

    def test_make_cache_key_without_options(self, engine: TransclusionEngine) -> None:
        """Test creating cache key without options."""
        key = engine.make_cache_key("file.md", None, {})
        assert key == ("file.md", "", ())

    def test_make_cache_key_with_section(self, engine: TransclusionEngine) -> None:
        """Test creating cache key with section."""
        key = engine.make_cache_key("file.md", "Section", {})
        assert key == ("file.md", "Section", ())

    def test_make_cache_key_with_options(self, engine: TransclusionEngine) -> None:
        """Test creating cache key with options."""
        from typing import cast

        from cortex.core.models import ModelDict

        options: dict[str, object] = {"lines": 5, "recursive": True}
        key = engine.make_cache_key("file.md", None, cast(ModelDict, options))
        # Options should be sorted tuple
        assert key[0] == "file.md"
        assert key[1] == ""
        assert isinstance(key[2], tuple)
        assert len(key[2]) == 2

    def test_make_cache_key_options_sorted(self, engine: TransclusionEngine) -> None:
        """Test that options are sorted for consistent keys."""
        from typing import cast

        from cortex.core.models import ModelDict

        options1: dict[str, object] = {"lines": 5, "recursive": True}
        options2: dict[str, object] = {"recursive": True, "lines": 5}

        key1 = engine.make_cache_key("file.md", None, cast(ModelDict, options1))
        key2 = engine.make_cache_key("file.md", None, cast(ModelDict, options2))
        # Should produce same key regardless of order
        assert key1 == key2

    def test_build_directive_pattern_without_section(
        self, engine: TransclusionEngine
    ) -> None:
        """Test building directive pattern without section."""
        from typing import cast

        from cortex.core.models import ModelDict

        trans: dict[str, object] = {"target": "file.md"}

        pattern = engine.build_directive_pattern(cast(ModelDict, trans))
        # Pattern should be a regex that matches the directive
        assert r"\{\{include:" in pattern
        assert r"\}\}" in pattern
        # file.md should be escaped in the pattern (file\.md)
        assert "file" in pattern

    def test_build_directive_pattern_with_section(
        self, engine: TransclusionEngine
    ) -> None:
        """Test building directive pattern with section."""
        from typing import cast

        from cortex.core.models import ModelDict

        trans: dict[str, object] = {"target": "file.md", "section": "Section"}

        pattern = engine.build_directive_pattern(cast(ModelDict, trans))
        # Pattern should contain escaped versions
        assert r"\{\{include:" in pattern
        assert "#" in pattern
        assert "Section" in pattern
        assert r"\}\}" in pattern


class TestTransclusionEngineEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.fixture
    def mock_fs(self) -> MagicMock:
        """Create a mock file system manager."""
        fs = MagicMock()
        fs.memory_bank_dir = Path("/tmp/memory-bank")
        return fs

    @pytest.fixture
    def link_parser(self) -> LinkParser:
        """Create a real link parser."""
        return LinkParser()

    @pytest.fixture
    def engine(self, mock_fs: MagicMock, link_parser: LinkParser) -> TransclusionEngine:
        """Create transclusion engine."""
        return TransclusionEngine(mock_fs, link_parser)

    @pytest.mark.asyncio
    async def test_resolve_content_with_empty_content(
        self, engine: TransclusionEngine
    ) -> None:
        """Test resolving empty content."""
        result = await engine.resolve_content("", "source.md")

        assert result == ""

    @pytest.mark.asyncio
    async def test_resolve_transclusion_depth_at_limit(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test resolution at max depth limit."""
        target_content = "No more transclusions"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            # Should succeed at max depth but not recurse
            result = await engine.resolve_transclusion(
                target_file="target.md",
                source_file="source.md",
                depth=5,
                options={"recursive": True},
            )

        assert result == target_content

    @pytest.mark.asyncio
    async def test_resolve_transclusion_with_none_options(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test resolution with None options."""
        target_content = "Content"
        mock_fs.read_file = AsyncMock(return_value=(target_content, "hash123"))

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_transclusion(
                target_file="target.md", source_file="source.md", options=None
            )

        assert result == target_content

    def test_extract_section_with_zero_lines_limit(
        self, engine: TransclusionEngine
    ) -> None:
        """Test section extraction with zero lines limit."""
        content = """# Title

## Section

Line 1
Line 2"""

        result = engine.extract_section(content, "Section", lines_limit=0)

        # Should return empty string
        assert result == ""

    @pytest.mark.asyncio
    async def test_resolve_content_preserves_order(
        self, engine: TransclusionEngine, mock_fs: MagicMock
    ) -> None:
        """Test that multiple transclusions are resolved in correct order."""
        content = """Start
{{include: file1.md}}
Middle
{{include: file2.md}}
End"""

        async def mock_read(path: Path) -> tuple[str, str]:
            if "file1.md" in str(path):
                return ("Content1", "hash1")
            elif "file2.md" in str(path):
                return ("Content2", "hash2")
            return ("", "hash_empty")

        mock_fs.read_file = mock_read

        with patch.object(Path, "exists", return_value=True):
            result = await engine.resolve_content(content, "source.md")

        # Verify order is maintained
        assert result.index("Content1") < result.index("Middle")
        assert result.index("Middle") < result.index("Content2")
