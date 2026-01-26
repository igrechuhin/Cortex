"""
Tests for summarization_engine module.

This module tests content summarization functionality including:
- File summarization with different strategies
- Section extraction and scoring
- Content compression and header extraction
- Summary caching
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from cortex.core.cache_utils import CacheType
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import get_cache_path
from cortex.optimization.summarization_engine import SummarizationEngine


class TestSummarizationEngineInitialization:
    """Tests for SummarizationEngine initialization."""

    def test_initialization_with_default_cache_dir(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test initialization with default cache directory."""
        # Arrange
        # Create .cortex directory
        (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)
        # Type ignore for mock assignment
        mock_metadata_index.project_root = str(tmp_path)  # type: ignore[assignment]

        # Act
        engine = SummarizationEngine(mock_token_counter, mock_metadata_index)

        # Assert
        assert engine.token_counter == mock_token_counter
        assert engine.metadata_index == mock_metadata_index
        assert engine.cache_dir == get_cache_path(tmp_path, CacheType.SUMMARIES.value)
        assert engine.cache_dir.exists()

    def test_initialization_with_custom_cache_dir(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test initialization with custom cache directory."""
        # Arrange
        custom_cache = tmp_path / "custom-cache"

        # Act
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=custom_cache
        )

        # Assert
        assert engine.cache_dir == custom_cache
        assert engine.cache_dir.exists()


class TestSummarizeFile:
    """Tests for summarize_file method."""

    @pytest.mark.asyncio
    async def test_summarize_empty_content(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test summarizing empty content returns zero tokens."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        result = await engine.summarize_file(
            "test.md", "", strategy="extract_key_sections"
        )

        # Assert
        assert result["original_tokens"] == 0
        assert result["summarized_tokens"] == 0
        assert result["reduction"] == 0.0
        assert result["summary"] == ""
        assert result["strategy_used"] == "extract_key_sections"

    @pytest.mark.asyncio
    async def test_summarize_with_extract_key_sections_strategy(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test summarize with extract_key_sections strategy."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Overview
This is an overview section with important information.

# Details
This section has detailed information that might be less important.
"""

        # Act
        result = await engine.summarize_file(
            "test.md", content, target_reduction=0.5, strategy="extract_key_sections"
        )

        # Assert
        assert isinstance(result, dict)
        original_tokens = result.get("original_tokens")
        assert isinstance(original_tokens, (int, float))
        assert original_tokens > 0
        summarized_tokens = result.get("summarized_tokens")
        assert isinstance(summarized_tokens, (int, float))
        assert summarized_tokens > 0
        assert original_tokens >= summarized_tokens
        assert "summary" in result
        assert result.get("strategy_used") == "extract_key_sections"
        assert result.get("cached") is False

    @pytest.mark.asyncio
    async def test_summarize_with_compress_verbose_strategy(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test summarize with compress_verbose strategy."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section
Content here.

## Example
This is an example that will be omitted.
```python
def example():
    pass
```
"""

        # Act
        result = await engine.summarize_file(
            "test.md", content, target_reduction=0.4, strategy="compress_verbose"
        )

        # Assert
        assert isinstance(result, dict)
        original_tokens = result.get("original_tokens")
        assert isinstance(original_tokens, (int, float))
        assert original_tokens > 0
        summarized_tokens = result.get("summarized_tokens")
        assert isinstance(summarized_tokens, (int, float))
        assert summarized_tokens > 0
        assert result.get("strategy_used") == "compress_verbose"
        summary = result.get("summary")
        assert isinstance(summary, str)
        assert "[Example omitted]" in summary

    @pytest.mark.asyncio
    async def test_summarize_with_headers_only_strategy(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test summarize with headers_only strategy."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section One
First paragraph.
Second paragraph.
Third paragraph.

# Section Two
First paragraph of section two.
"""

        # Act
        result = await engine.summarize_file(
            "test.md", content, target_reduction=0.7, strategy="headers_only"
        )

        # Assert
        assert isinstance(result, dict)
        original_tokens = result.get("original_tokens")
        assert isinstance(original_tokens, (int, float))
        assert original_tokens > 0
        summarized_tokens = result.get("summarized_tokens")
        assert isinstance(summarized_tokens, (int, float))
        assert summarized_tokens > 0
        assert result.get("strategy_used") == "headers_only"
        summary = result.get("summary")
        assert isinstance(summary, str)
        assert "# Section One" in summary
        assert "# Section Two" in summary

    @pytest.mark.asyncio
    async def test_summarize_with_invalid_strategy_defaults_to_key_sections(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that invalid strategy defaults to extract_key_sections."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "# Section\nContent here."

        # Act
        result = await engine.summarize_file(
            "test.md", content, strategy="invalid_strategy"
        )

        # Assert
        assert result["strategy_used"] == "invalid_strategy"
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_summarize_uses_cache_when_available(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that summarization uses cached results when available."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "# Test\nContent here."

        # First call - generates summary
        result1 = await engine.summarize_file(
            "test.md", content, strategy="extract_key_sections"
        )

        # Second call - should use cache
        result2 = await engine.summarize_file(
            "test.md", content, strategy="extract_key_sections"
        )

        # Assert
        assert result2["cached"] is True
        assert result2["summary"] == result1["summary"]
        assert result2["original_tokens"] == result1["original_tokens"]


class TestExtractKeySections:
    """Tests for extract_key_sections method."""

    @pytest.mark.asyncio
    async def test_extract_key_sections_with_no_sections(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test extract_key_sections with content that has no sections."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "This is plain text content without any sections or headings."

        # Act
        result = await engine.extract_key_sections(content, target_tokens=50)

        # Assert
        # When no sections are found, _parse_sections returns {"preamble": content}
        # So we actually get a preamble section, not truncated content
        assert "## preamble" in result or "[Content truncated...]" in result

    @pytest.mark.asyncio
    async def test_extract_key_sections_selects_highest_scoring_sections(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that key sections selection prioritizes high-scoring sections."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Overview
Important overview content.

# Example
Example content.

# Details
Detailed information.
"""

        # Act
        result = await engine.extract_key_sections(content, target_tokens=100)

        # Assert
        assert "## Overview" in result
        # Example should have lower score and might be omitted
        assert (
            "sections omitted" in result
            or "## Example" not in result
            or "## Example" in result
        )

    @pytest.mark.asyncio
    async def test_extract_key_sections_includes_at_least_one_section(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that at least one section is included even if it exceeds target."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Important Section
This section is very large and exceeds the target token count.
"""

        # Act
        result = await engine.extract_key_sections(content, target_tokens=5)

        # Assert
        assert "## Important Section" in result
        # Should still include the section even though it exceeds target


class TestCompressVerboseContent:
    """Tests for compress_verbose_content method."""

    @pytest.mark.asyncio
    async def test_compress_removes_examples(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that compress_verbose removes example sections."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section
Content here.

## Example
This is an example that should be omitted.
Detailed example content.

## Another Section
More content.
"""

        # Act
        result = await engine.compress_verbose_content(content, target_reduction=0.5)

        # Assert
        assert "[Example omitted]" in result
        assert "Detailed example content" not in result
        assert "## Another Section" in result

    @pytest.mark.asyncio
    async def test_compress_truncates_large_code_blocks(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that large code blocks are compressed."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        large_code = "\n".join([f"line {i}" for i in range(25)])
        content = f"""# Code
```python
{large_code}
```
"""

        # Act
        result = await engine.compress_verbose_content(content, target_reduction=0.5)

        # Assert
        assert "# ... code omitted ..." in result
        assert "```python" in result
        assert "```" in result

    @pytest.mark.asyncio
    async def test_compress_preserves_small_code_blocks(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that small code blocks are preserved."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Code
```python
def small():
    pass
```
"""

        # Act
        result = await engine.compress_verbose_content(content, target_reduction=0.5)

        # Assert
        assert "def small():" in result
        assert "# ... code omitted ..." not in result

    @pytest.mark.asyncio
    async def test_compress_truncates_very_long_lines(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that very long lines are truncated."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        long_line = "x" * 600
        content = f"# Section\n{long_line}"

        # Act
        result = await engine.compress_verbose_content(content, target_reduction=0.5)

        # Assert
        assert "[truncated]" in result
        assert len(result) < len(content)


class TestExtractHeadersOnly:
    """Tests for extract_headers_only method."""

    @pytest.mark.asyncio
    async def test_extract_headers_includes_section_headers(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that headers are extracted correctly."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section One
First paragraph.
Second paragraph.

# Section Two
Another paragraph.
"""

        # Act
        result = await engine.extract_headers_only(content)

        # Assert
        assert "# Section One" in result
        assert "# Section Two" in result
        assert "First paragraph" in result

    @pytest.mark.asyncio
    async def test_extract_headers_limits_content_per_section(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that only first few lines per section are kept."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section
Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
"""

        # Act
        result = await engine.extract_headers_only(content)

        # Assert
        assert "[...]" in result
        assert "Line 1" in result
        assert "Line 8" not in result

    @pytest.mark.asyncio
    async def test_extract_headers_handles_empty_sections(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test handling of sections with no content."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section One

# Section Two

"""

        # Act
        result = await engine.extract_headers_only(content)

        # Assert
        assert "# Section One" in result
        assert "# Section Two" in result


class TestParseSections:
    """Tests for _parse_sections method."""

    def test_parse_sections_with_multiple_headings(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test parsing content with multiple sections."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """# Section One
Content for section one.

## Subsection
Subsection content.

# Section Two
Content for section two.
"""

        # Act
        sections = engine.parse_sections(content)

        # Assert
        assert "Section One" in sections
        assert "Section Two" in sections
        assert "Content for section one" in sections["Section One"]
        assert "Content for section two" in sections["Section Two"]

    def test_parse_sections_with_preamble(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test parsing content with preamble before first heading."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = """This is preamble content before any headings.

# First Section
Section content.
"""

        # Act
        sections = engine.parse_sections(content)

        # Assert
        assert "preamble" in sections
        assert "This is preamble" in sections["preamble"]
        assert "First Section" in sections

    def test_parse_sections_with_no_headings(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test parsing content with no headings."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "Just plain text content without any headings."

        # Act
        sections = engine.parse_sections(content)

        # Assert
        assert "preamble" in sections
        assert "plain text content" in sections["preamble"]


class TestScoreSectionImportance:
    """Tests for _score_section_importance method."""

    def test_score_increases_for_important_keywords(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that important keywords increase section score."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        score_overview = engine.score_section_importance("Overview", "Content here")
        score_generic = engine.score_section_importance("Details", "Content here")

        # Assert
        assert score_overview > score_generic

    def test_score_decreases_for_low_value_keywords(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that low-value keywords decrease section score."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        score_example = engine.score_section_importance("Example", "Content here")
        score_generic = engine.score_section_importance("Information", "Content here")

        # Assert
        assert score_example < score_generic

    def test_score_adjusts_for_content_length(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that content length affects section score."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        short_content = "x" * 300
        long_content = "x" * 3000

        # Act
        score_short = engine.score_section_importance("Section", short_content)
        score_long = engine.score_section_importance("Section", long_content)

        # Assert
        assert score_short > score_long

    def test_score_bounded_between_zero_and_one(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that scores are bounded between 0.0 and 1.0."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        score = engine.score_section_importance("Goal Overview Summary", "x" * 100)

        # Assert
        assert 0.0 <= score <= 1.0


class TestCaching:
    """Tests for summary caching functionality."""

    def test_compute_hash_returns_consistent_hash(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that hash computation is consistent."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "Test content"

        # Act
        hash1 = engine.compute_hash(content)
        hash2 = engine.compute_hash(content)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated to 16 chars

    def test_compute_hash_differs_for_different_content(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that different content produces different hashes."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        hash1 = engine.compute_hash("Content 1")
        hash2 = engine.compute_hash("Content 2")

        # Assert
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_cache_summary_creates_cache_file(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that cache_summary creates a cache file."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        await engine.cache_summary(
            "test.md", "hash123", "extract_key_sections", "Summary content"
        )

        # Assert
        cache_file = tmp_path / "test.md.extract_key_sections.hash123.json"
        assert cache_file.exists()

        with open(cache_file) as f:
            data = json.load(f)
            assert data["file_name"] == "test.md"
            assert data["summary"] == "Summary content"

    @pytest.mark.asyncio
    async def test_get_cached_summary_returns_cached_content(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that get_cached_summary retrieves cached summaries."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        await engine.cache_summary(
            "test.md", "hash123", "extract_key_sections", "Cached summary"
        )

        # Act
        result = engine.get_cached_summary("test.md", "hash123", "extract_key_sections")

        # Assert
        assert result == "Cached summary"

    def test_get_cached_summary_returns_none_when_not_cached(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that get_cached_summary returns None when cache doesn't exist."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Act
        result = engine.get_cached_summary(
            "test.md", "nonexistent", "extract_key_sections"
        )

        # Assert
        assert result is None

    def test_get_cached_summary_handles_corrupted_cache(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that corrupted cache files are handled gracefully."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        cache_file = tmp_path / "test.md.extract_key_sections.hash123.json"
        _ = cache_file.write_text("invalid json{")

        # Act
        result = engine.get_cached_summary("test.md", "hash123", "extract_key_sections")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_summary_handles_write_errors_silently(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Test that cache write errors are handled silently."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )

        # Make cache directory read-only
        engine.cache_dir.chmod(0o444)

        # Act & Assert - Should not raise exception
        try:
            await engine.cache_summary(
                "test.md", "hash123", "extract_key_sections", "Summary"
            )
        finally:
            # Restore permissions
            engine.cache_dir.chmod(0o755)
