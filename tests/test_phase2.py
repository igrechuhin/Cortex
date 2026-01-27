"""Tests for Phase 2: DRY Linking and Transclusion modules.

This module tests:
- LinkParser: Markdown link and transclusion parsing
- TransclusionEngine: Content resolution and caching
- LinkValidator: Link integrity checking
- DependencyGraph: Dynamic link-based dependencies

Run with: python test_phase2.py
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast

import pytest

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import (
    CircularDependencyError,
    MaxDepthExceededError,
    TransclusionEngine,
)
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.types import get_list


class TestLinkParser:
    """Tests for LinkParser module."""

    parser: LinkParser

    def __init__(self):
        """Set up test fixtures."""
        self.parser = LinkParser()

    async def test_parse_markdown_links(self):
        """Test parsing standard markdown links."""
        content = """
# Test File

See [projectBrief](projectBrief.md) for details.
Also check [section](file.md#Section) for more info.
External link: [Google](https://google.com)
"""
        result = await self.parser.parse_file(content)

        markdown_links = get_list(result, "markdown_links")
        assert len(markdown_links) == 2  # External link excluded
        link0 = cast(dict[str, object], markdown_links[0])
        link1 = cast(dict[str, object], markdown_links[1])
        assert link0["target"] == "projectBrief.md"
        assert link1["target"] == "file.md"
        assert link1["section"] == "Section"

    @pytest.mark.asyncio
    async def test_parse_transclusion_directives(self):
        """Test parsing transclusion directives."""
        content = """
# Test File

{{include: projectBrief.md}}

More content here.

{{include: systemPatterns.md#Architecture}}

And with options:
{{include: activeContext.md#Changes|lines=10}}
"""
        result = await self.parser.parse_file(content)

        transclusions = get_list(result, "transclusions")
        assert len(transclusions) == 3
        trans0 = cast(dict[str, object], transclusions[0])
        trans1 = cast(dict[str, object], transclusions[1])
        assert trans0["target"] == "projectBrief.md"
        assert trans0["section"] is None

        assert trans1["target"] == "systemPatterns.md"
        assert trans1["section"] == "Architecture"

        assert len(transclusions) > 2
        trans2 = cast(dict[str, object], transclusions[2])
        assert trans2["target"] == "activeContext.md"
        assert trans2["section"] == "Changes"
        options_raw = trans2.get("options")
        assert isinstance(options_raw, dict)
        # Type assertion for dict[str, object] from parse_transclusion_options
        options = cast(dict[str, object], options_raw)
        assert cast(int, options["lines"]) == 10

    def test_parse_link_target(self):
        """Test parsing link targets."""
        # File only
        file, section = self.parser.parse_link_target("file.md")
        assert file == "file.md"
        assert section is None

        # File with section
        file, section = self.parser.parse_link_target("file.md#Section")
        assert file == "file.md"
        assert section == "Section"

    def test_parse_transclusion_options(self):
        """Test parsing transclusion options."""
        # Single option
        options = self.parser.parse_transclusion_options("lines=5")
        assert options["lines"] == 5

        # Multiple options
        options = self.parser.parse_transclusion_options("lines=10|recursive=false")
        assert options["lines"] == 10
        assert options["recursive"] is False

        # Boolean values
        options = self.parser.parse_transclusion_options("recursive=true")
        assert options["recursive"] is True

    @pytest.mark.asyncio
    async def test_count_links(self):
        """Test link counting."""
        content = """
[link1](file1.md)
[link2](file2.md)
{{include: file3.md}}
"""
        result = await self.parser.parse_file(content)
        counts = self.parser.count_links(result)

        assert counts["markdown_links"] == 2
        assert counts["transclusions"] == 1
        assert counts["total"] == 3
        assert counts["unique_files"] == 3


class TestTransclusionEngine:
    """Tests for TransclusionEngine module."""

    temp_dir: Path | None = None
    memory_bank_dir: Path | None = None
    fs_manager: FileSystemManager | None = None
    link_parser: LinkParser | None = None
    engine: TransclusionEngine | None = None

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.memory_bank_dir = ensure_test_cortex_structure(self.temp_dir)

        self.fs_manager = FileSystemManager(self.temp_dir)
        self.link_parser = LinkParser()
        self.engine = TransclusionEngine(
            file_system=self.fs_manager,
            link_parser=self.link_parser,
            max_depth=5,
            cache_enabled=True,
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_simple_transclusion(self):
        """Test simple transclusion without nesting."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.engine is not None
        # Create files
        target_file = self.memory_bank_dir / "target.md"
        target_content = "# Target\n\nThis is target content."
        _ = await self.fs_manager.write_file(target_file, target_content)

        source_content = "# Source\n\n{{include: target.md}}\n\nMore content."

        # Resolve
        resolved = await self.engine.resolve_content(
            content=source_content, source_file="source.md"
        )

        assert "This is target content" in resolved
        assert "{{include:" not in resolved

    @pytest.mark.asyncio
    async def test_section_extraction(self):
        """Test extracting specific sections."""
        assert self.engine is not None
        content = """
# File

## Section 1
Content 1

## Section 2
Content 2

## Section 3
Content 3
"""
        # Extract Section 2
        extracted = self.engine.extract_section(content, "Section 2")
        assert "Content 2" in extracted
        assert "Content 1" not in extracted
        assert "Content 3" not in extracted

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.engine is not None
        # Create circular transclusion
        file_a = self.memory_bank_dir / "a.md"
        file_b = self.memory_bank_dir / "b.md"

        _ = await self.fs_manager.write_file(file_a, "# A\n\n{{include: b.md}}")
        _ = await self.fs_manager.write_file(file_b, "# B\n\n{{include: a.md}}")

        # Should raise CircularDependencyError
        with pytest.raises(CircularDependencyError):
            _ = await self.engine.resolve_content(
                content="{{include: a.md}}", source_file="start.md"
            )

    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self):
        """Test max depth protection."""
        # Create deep nesting
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        for i in range(10):
            file = self.memory_bank_dir / f"file{i}.md"
            if i < 9:
                content = f"# File {i}\n\n{{{{include: file{i + 1}.md}}}}"
            else:
                content = f"# File {i}\n\nEnd of chain."
            _ = await self.fs_manager.write_file(file, content)

        # Set low max depth
        assert self.engine is not None
        self.engine.max_depth = 3

        # Should raise MaxDepthExceededError
        with pytest.raises(MaxDepthExceededError):
            _ = await self.engine.resolve_content(
                content="{{include: file0.md}}", source_file="start.md"
            )

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test content caching."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.engine is not None
        # Create target file
        target_file = self.memory_bank_dir / "target.md"
        _ = await self.fs_manager.write_file(target_file, "# Target\n\nCached content.")

        # First resolution
        result1 = await self.engine.resolve_transclusion(
            target_file="target.md", section=None
        )

        # Check cache stats
        # Library returns Dict[Unknown, Unknown], but we know the structure
        stats_raw = self.engine.get_cache_stats()
        stats: dict[str, int | float] = stats_raw
        assert stats["entries"] > 0

        # Second resolution (should hit cache)
        result2 = await self.engine.resolve_transclusion(
            target_file="target.md", section=None
        )

        assert result1 == result2
        # Get stats again after second call
        stats_raw2 = self.engine.get_cache_stats()
        stats2: dict[str, int | float] = stats_raw2
        assert stats2["hits"] > 0


class TestLinkValidator:
    """Tests for LinkValidator module."""

    temp_dir: Path | None = None
    memory_bank_dir: Path | None = None
    fs_manager: FileSystemManager | None = None
    link_parser: LinkParser | None = None
    validator: LinkValidator | None = None

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.memory_bank_dir = ensure_test_cortex_structure(self.temp_dir)

        self.fs_manager = FileSystemManager(self.temp_dir)
        self.link_parser = LinkParser()
        self.validator = LinkValidator(
            file_system=self.fs_manager, link_parser=self.link_parser
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_valid_file_link(self):
        """Test validation of valid file links."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.validator is not None
        # Create files
        file_a = self.memory_bank_dir / "a.md"
        file_b = self.memory_bank_dir / "b.md"

        _ = await self.fs_manager.write_file(file_b, "# B\n\nTarget content.")
        _ = await self.fs_manager.write_file(
            file_a, "# A\n\nSee [file b](b.md) for more."
        )

        # Validate
        # Library returns dict[str, object], extract lists and cast to avoid type errors
        result = await self.validator.validate_file(file_a)
        valid_links = cast(list[object], result.get("valid_links", []))
        broken_links = cast(list[object], result.get("broken_links", []))

        assert len(valid_links) == 1
        assert len(broken_links) == 0

    @pytest.mark.asyncio
    async def test_broken_file_link(self):
        """Test detection of broken file links."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.validator is not None
        # Create file with broken link
        file_a = self.memory_bank_dir / "a.md"
        _ = await self.fs_manager.write_file(
            file_a, "# A\n\nSee [missing](missing.md) for more."
        )

        # Validate
        # Library returns dict[str, object], extract lists to avoid object in len()
        result = await self.validator.validate_file(file_a)
        valid_links = cast(list[dict[str, object]], result.get("valid_links", []))
        broken_links = cast(list[dict[str, object]], result.get("broken_links", []))

        assert len(valid_links) == 0
        assert len(broken_links) == 1
        assert cast(str, broken_links[0]["target"]) == "missing.md"

    @pytest.mark.asyncio
    async def test_broken_section_link(self):
        """Test detection of broken section links."""
        assert self.memory_bank_dir is not None
        assert self.fs_manager is not None
        assert self.validator is not None
        # Create files
        file_a = self.memory_bank_dir / "a.md"
        file_b = self.memory_bank_dir / "b.md"

        _ = await self.fs_manager.write_file(file_b, "# B\n\n## Section 1\n\nContent.")
        _ = await self.fs_manager.write_file(
            file_a, "# A\n\nSee [section](b.md#Section 2) for more."
        )

        # Validate
        # Library returns dict[str, object], extract list and cast to avoid type errors
        result = await self.validator.validate_file(file_a)
        warnings = cast(list[dict[str, object]], result.get("warnings", []))

        assert len(warnings) == 1
        assert cast(str, warnings[0]["section"]) == "Section 2"


class TestDependencyGraphDynamic:
    """Tests for dynamic link-based dependency graph."""

    temp_dir: Path | None = None
    memory_bank_dir: Path | None = None
    graph: DependencyGraph | None = None
    link_parser: LinkParser | None = None

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.memory_bank_dir = ensure_test_cortex_structure(self.temp_dir)

        self.graph = DependencyGraph()
        self.link_parser = LinkParser()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_build_from_links(self):
        """Test building dependency graph from actual links."""
        assert self.memory_bank_dir is not None
        assert self.graph is not None
        assert self.link_parser is not None
        # Create files with links
        file_a = self.memory_bank_dir / "a.md"
        file_b = self.memory_bank_dir / "b.md"

        with open(file_a, "w") as f:
            _ = f.write("# A\n\nSee [b](b.md) for more.")

        with open(file_b, "w") as f:
            _ = f.write("# B\n\nContent.")

        # Build graph
        await self.graph.build_from_links(self.memory_bank_dir, self.link_parser)  # type: ignore

        # Check dependencies
        deps = self.graph.get_dependencies("a.md")
        assert "b.md" in deps

    def test_add_link_dependency(self):
        """Test adding link dependencies."""
        assert self.graph is not None
        self.graph.add_link_dependency("a.md", "b.md", link_type="reference")
        self.graph.add_link_dependency("a.md", "c.md", link_type="transclusion")

        deps = self.graph.get_dependencies("a.md")
        assert "b.md" in deps
        assert "c.md" in deps

        # Check link types
        assert self.graph.get_link_type("a.md", "b.md") == "reference"
        assert self.graph.get_link_type("a.md", "c.md") == "transclusion"

    def test_detect_cycles(self):
        """Test cycle detection."""
        assert self.graph is not None
        # Create cycle: a -> b -> c -> a
        self.graph.add_link_dependency("a.md", "b.md")
        self.graph.add_link_dependency("b.md", "c.md")
        self.graph.add_link_dependency("c.md", "a.md")

        cycles = self.graph.detect_cycles()
        assert len(cycles) > 0

    def test_transclusion_order(self):
        """Test getting transclusion resolution order."""
        assert self.graph is not None
        # Create transclusion chain: a includes b, b includes c
        self.graph.add_link_dependency("a.md", "b.md", link_type="transclusion")
        self.graph.add_link_dependency("b.md", "c.md", link_type="transclusion")

        order = self.graph.get_transclusion_order("a.md")

        # c should come before b, b before a
        assert order.index("c.md") < order.index("b.md")
        assert order.index("b.md") < order.index("a.md")


async def run_all_tests():
    """Run all Phase 2 tests."""
    print("=" * 70)
    print("Phase 2 Tests: DRY Linking and Transclusion")
    print("=" * 70)

    # Test LinkParser
    print("\n[LinkParser Tests]")
    parser_tests = TestLinkParser()

    try:
        await parser_tests.test_parse_markdown_links()
        print("✓ test_parse_markdown_links passed")
    except Exception as e:
        print(f"✗ test_parse_markdown_links failed: {e}")

    try:
        await parser_tests.test_parse_transclusion_directives()
        print("✓ test_parse_transclusion_directives passed")
    except Exception as e:
        print(f"✗ test_parse_transclusion_directives failed: {e}")

    try:
        parser_tests.test_parse_link_target()
        print("✓ test_parse_link_target passed")
    except Exception as e:
        print(f"✗ test_parse_link_target failed: {e}")

    try:
        parser_tests.test_parse_transclusion_options()
        print("✓ test_parse_transclusion_options passed")
    except Exception as e:
        print(f"✗ test_parse_transclusion_options failed: {e}")

    try:
        await parser_tests.test_count_links()
        print("✓ test_count_links passed")
    except Exception as e:
        print(f"✗ test_count_links failed: {e}")

    print("\n[Phase 2 Basic Tests Complete]")
    print(
        "Note: Full test suite requires pytest. Run: uv add --dev pytest pytest-asyncio"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
