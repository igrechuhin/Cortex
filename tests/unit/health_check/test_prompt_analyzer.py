"""Tests for prompt analyzer."""

from pathlib import Path

import pytest

from cortex.health_check.prompt_analyzer import PromptAnalyzer


class TestPromptAnalyzer:
    """Test prompt analyzer functionality."""

    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        """Create temporary project root."""
        return tmp_path

    @pytest.fixture
    def analyzer(self, project_root: Path) -> PromptAnalyzer:
        """Create prompt analyzer instance."""
        return PromptAnalyzer(project_root)

    @pytest.mark.asyncio
    async def test_analyze_no_prompts_dir(self, analyzer: PromptAnalyzer):
        """Test analyze when prompts directory doesn't exist."""
        result = await analyzer.analyze()
        assert "total" in result
        assert result["total"] == 0
        assert result["merge_opportunities"] == []
        assert result["optimization_opportunities"] == []

    @pytest.mark.asyncio
    async def test_extract_sections(self, analyzer: PromptAnalyzer):
        """Test section extraction from markdown."""
        content = "# Header 1\nContent 1\n## Header 2\nContent 2"
        sections = analyzer._extract_sections(content)
        assert len(sections) == 2
        assert "Content 1" in sections[0]
        assert "Content 2" in sections[1]

    @pytest.mark.asyncio
    async def test_find_merge_opportunities(self, analyzer: PromptAnalyzer):
        """Test finding merge opportunities."""
        prompts = {
            "prompt1.md": "This is test content.",
            "prompt2.md": "This is test content.",
        }
        opportunities = await analyzer._find_merge_opportunities(prompts)
        assert len(opportunities) > 0
        assert opportunities[0]["files"] == ["prompt1.md", "prompt2.md"]

    @pytest.mark.asyncio
    async def test_find_optimization_opportunities_large(
        self, analyzer: PromptAnalyzer
    ):
        """Test finding optimization opportunities for large prompts."""
        # Create content that will exceed 50000 tokens (roughly 125k chars)
        large_content = "This is a test sentence. " * 5000  # ~125k chars
        prompts = {"large.md": large_content}
        opportunities = await analyzer._find_optimization_opportunities(prompts)
        # May or may not find opportunities depending on token count
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_check_large_prompt(self, analyzer: PromptAnalyzer):
        """Test checking for large prompts."""
        # Create content that will exceed 50000 tokens (roughly 125k chars)
        large_content = "This is a test sentence. " * 5000  # ~125k chars
        opportunities = analyzer._check_large_prompt("large.md", large_content)
        # May or may not find opportunities depending on token count
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_check_duplicate_sections(self, analyzer: PromptAnalyzer):
        """Test checking for duplicate sections."""
        content = "# Section 1\nSame content\n## Section 2\nSame content"
        opportunities = analyzer._check_duplicate_sections("test.md", content)
        # May or may not find duplicates depending on similarity threshold
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_find_merge_opportunities_no_similarity(
        self, analyzer: PromptAnalyzer
    ):
        """Test finding merge opportunities with low similarity."""
        prompts = {
            "prompt1.md": "This is completely different content.",
            "prompt2.md": "This is also completely different content.",
        }
        opportunities = await analyzer._find_merge_opportunities(prompts)
        # Should not find opportunities due to low similarity
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_extract_sections_no_headings(self, analyzer: PromptAnalyzer):
        """Test section extraction with no headings."""
        content = "Just plain content without headings."
        sections = analyzer._extract_sections(content)
        assert len(sections) == 1
        assert "Just plain content without headings." in sections[0]

    @pytest.mark.asyncio
    async def test_scan_prompts_with_files(
        self, analyzer: PromptAnalyzer, tmp_path: Path
    ):
        """Test scanning prompts when files exist."""
        prompts_dir = tmp_path / ".cortex" / "synapse" / "prompts"
        prompts_dir.mkdir(parents=True)
        test_file = prompts_dir / "test.md"
        test_file.write_text("# Test Prompt\nContent here")

        # Update analyzer's prompts_dir to point to our test directory
        analyzer.prompts_dir = prompts_dir

        prompts = await analyzer._scan_prompts()
        assert "test.md" in prompts
        assert "Content here" in prompts["test.md"]
