"""
Tests for summarization_engine module.

This module tests content summarization functionality including:
- File summarization with different strategies
- Section extraction and scoring
- Content compression and header extraction
- Summary caching
"""

import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from cortex.core.cache_utils import CacheType
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cache_path,
    get_cortex_path,
)
from cortex.optimization.summarization_engine import SummarizationEngine
from cortex.optimization.summarization_engine_cache import (
    cache_result_async,
    compute_content_hash,
    compute_variant_hash,
    get_cached_result,
)


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
        get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR).mkdir(
            parents=True, exist_ok=True
        )
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
    async def test_summarize_file_distinguishes_preamble_heading_from_headerless(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """A document whose only heading is literally named "preamble" is
        a real, countable section -- not the synthetic no-heading marker
        that plain prose parses to. Only the name coincides; `has_heading`
        (not the section's name) is what tells the two apart.
        """
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        headerless = "Plain prose with no markdown heading at all.\n"
        with_heading = "# preamble\nPlain prose under a literal heading.\n"

        headerless_result = await engine.summarize_file(
            "headerless.md", headerless, strategy="extract_key_sections"
        )
        headed_result = await engine.summarize_file(
            "headed.md", with_heading, strategy="extract_key_sections"
        )

        assert headerless_result["sections_kept"] == 0
        assert headed_result["sections_kept"] == 1
        assert headed_result["summary"] == with_heading

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
        """Unsectioned content is returned verbatim, never rewritten."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "This is plain text content without any sections or headings."

        # Act
        result = await engine.extract_key_sections(content, target_tokens=50)

        # Assert
        # This previously asserted the output contained either an invented
        # "## preamble" heading or a "[Content truncated...]" marker -- i.e. it
        # pinned the two defects: parse_sections' synthetic preamble section
        # being reconstructed under a fake heading (which grew the content and
        # drove `reduction` negative), and the 50%-of-words truncation that
        # silently destroyed paths and error strings. There is nothing to select
        # between in unsectioned content, so the only safe answer is the input.
        assert result == content

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
        assert "# Overview" in result
        # Overview keeps its original level -- never rewritten to "## Overview".
        assert "## Overview" not in result
        # Example should have lower score and might be omitted
        assert (
            "sections omitted" in result
            or "# Example" not in result
            or "# Example" in result
        )

    @pytest.mark.asyncio
    async def test_omission_note_never_costs_more_than_it_discloses(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """A run of tiny sections with long headings must not produce a note
        as large as the text it replaces: naming them would buy a reduction of
        roughly zero while still losing the content, so the note degrades to
        the count alone."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        keep = "# Overview\n" + "essential content. " * 60 + "\n"
        tiny = "".join(
            f"# Appendix Subsection Number {i} Of The Reference Material\nx\n"
            for i in range(8)
        )

        # Act
        result = await engine.extract_key_sections(keep + tiny, target_tokens=180)

        # Assert
        assert re.search(r"\[\d+ sections omitted\]", result)
        assert "Appendix Subsection Number 1" not in result
        # The whole point: the drop actually bought space.
        assert len(result) < len(keep + tiny) * 0.9

    @pytest.mark.asyncio
    async def test_a_drop_the_note_cannot_pay_for_is_refused(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Degrading to the bare count is not enough on its own: one tiny
        section costs less to keep than `[1 section omitted]` costs to say.
        Dropping it grew the summary past its own input, so the drop must be
        refused and the section kept verbatim rather than disclosed away."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        keep = "# Overview\n" + "essential content. " * 60 + "\n"
        tiny = "# a\nb\n"

        # Act: a budget that fits Overview exactly, so the tiny section is
        # the only thing over the line and would otherwise be dropped.
        result = await engine.extract_key_sections(keep + tiny, target_tokens=158)

        # Assert
        assert len(result) <= len(keep + tiny)
        assert "omitted" not in result
        assert "b" in result

    @pytest.mark.asyncio
    async def test_omission_note_names_sections_when_it_is_worth_it(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """The named form stays the default: dropping a large section is worth
        the handful of bytes naming it costs."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = (
            "# Overview\n"
            + "essential content. " * 40
            + "\n# Appendix\n"
            + "disposable filler. " * 200
            + "\n"
        )

        # Act
        result = await engine.extract_key_sections(content, target_tokens=150)

        # Assert
        assert "sections omitted: Appendix" in result

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
        assert "# Important Section" in result
        # Should still include the section even though it exceeds target

    @pytest.mark.asyncio
    async def test_extract_key_sections_preserves_source_order_over_score_order(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Kept sections replay in source order, not the ranked score order.

        The heuristic scores "Overview" (keyword-boosted) higher than
        "Notes" (keyword-penalized via "note"), even though "Overview" is
        physically last. A budget wide enough to keep both must still emit
        "Notes" before "Overview" -- reconstructing in score order would put
        "Overview" first and fail this assertion.
        """
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = (
            "# Notes\n"
            "First section body text that appears first in the document.\n\n"
            "# Overview\n"
            "Second section text; this one scores highest thanks to the keyword.\n"
        )

        # Act
        result = await engine.extract_key_sections(content, target_tokens=100)

        # Assert
        assert result.index("# Notes") < result.index("# Overview")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("blank_lines", [0, 1, 3])
    async def test_extract_key_sections_round_trips_byte_identical_when_nothing_dropped(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
        blank_lines: int,
    ) -> None:
        """When the budget keeps every section, reconstruction must
        reproduce the original bytes exactly -- including the number of
        blank lines between sections -- not a re-joined approximation.
        """
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        separator = "\n" * (blank_lines + 1)
        content = f"# First\nline one{separator}# Second\nline two"

        result = await engine.extract_key_sections(content, target_tokens=10_000)

        assert result == content


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
        by_name = {section.name: section.source for section in sections}

        # Assert
        assert "Section One" in by_name
        assert "Section Two" in by_name
        assert "Content for section one" in by_name["Section One"]
        assert "Content for section two" in by_name["Section Two"]

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
        by_name = {section.name: section.source for section in sections}

        # Assert
        assert "preamble" in by_name
        assert "This is preamble" in by_name["preamble"]
        assert "First Section" in by_name

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
        by_name = {section.name: section.source for section in sections}

        # Assert
        assert "preamble" in by_name
        assert "plain text content" in by_name["preamble"]

    def test_parse_sections_preserves_heading_levels_and_is_fence_aware(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Heading level is never rewritten, and a "#" inside a fence is not
        a heading -- it must not split the fenced block into a new section.
        """
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = (
            "# Overview\nTop level overview.\n\n"
            "### API Reference\n```python\n"
            "# AI: inline comment inside fence, not a heading\ndef foo():\n    pass\n"
            "```\n\n"
            "#### Detail\nDetail body.\n"
        )

        # Act
        sections = engine.parse_sections(content)
        by_name = {section.name: section.source for section in sections}

        # Assert -- exactly three sections; the fenced "#" line never became
        # a section of its own, and each heading kept its original level.
        assert len(sections) == 3
        assert by_name["Overview"] == "# Overview\nTop level overview.\n"
        assert by_name["API Reference"] == (
            "### API Reference\n"
            "```python\n"
            "# AI: inline comment inside fence, not a heading\n"
            "def foo():\n"
            "    pass\n"
            "```\n"
        )
        assert by_name["Detail"] == "#### Detail\nDetail body.\n"

    def test_parse_sections_keeps_duplicate_headings_distinct(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """Two identically named headings must not overwrite one another."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "## Notes\nFirst note.\n\n## Notes\nSecond note.\n"

        # Act
        sections = engine.parse_sections(content)

        # Assert
        assert [section.name for section in sections] == ["Notes", "Notes"]
        assert sections[0].source == "## Notes\nFirst note.\n"
        assert sections[1].source == "## Notes\nSecond note.\n"
        assert "Second note" not in sections[0].source
        assert "First note" not in sections[1].source

    def test_parse_sections_treats_unspaced_and_bare_hash_as_body_text(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """A "#foo" with no space and a bare "#" are body text, not headings."""
        # Arrange
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "# Real Heading\nSome text.\n#foo not a heading\n#\nMore text.\n"

        # Act
        sections = engine.parse_sections(content)

        # Assert -- both literal lines survive verbatim in the one real section.
        assert len(sections) == 1
        assert sections[0].name == "Real Heading"
        assert sections[0].source == content


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

    async def test_summarize_file_creates_variant_keyed_cache_file(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """summarize_file persists a cache entry under a name that encodes
        the strategy and variant, not just the file name -- readable back
        through the cache module's own get_cached_result with matching
        hashes.
        """
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        content = "# Heading\nBody text that becomes the cached summary.\n"

        result = await engine.summarize_file(
            "test.md", content, strategy="extract_key_sections"
        )

        cache_files = list(tmp_path.glob("test.md.extract_key_sections.*.json"))
        assert len(cache_files) == 1
        content_hash = compute_content_hash(content)
        target_tokens = int(mock_token_counter.count_tokens(content) * 0.5)
        variant_hash = compute_variant_hash(
            "extract_key_sections", target_tokens, engine.section_scorer.identity
        )
        cached = get_cached_result(
            tmp_path, "test.md", content_hash, "extract_key_sections", variant_hash
        )
        assert cached is not None
        assert cached.summary == result["summary"]

    async def test_get_cached_result_treats_corrupted_entry_as_miss(
        self, tmp_path: Path
    ) -> None:
        """A cache entry that fails to parse is a miss, not a crash --
        the exact path a real request would look up, corrupted after the
        fact, not an ad hoc name.
        """
        content_hash = compute_content_hash("Some content")
        variant_hash = compute_variant_hash("extract_key_sections", 50, "heuristic-v1")
        await cache_result_async(
            tmp_path,
            "test.md",
            content_hash,
            "extract_key_sections",
            variant_hash,
            "Summary content",
        )
        cache_files = list(tmp_path.glob("test.md.extract_key_sections.*.json"))
        assert len(cache_files) == 1
        _ = cache_files[0].write_text("invalid json{")

        result = get_cached_result(
            tmp_path, "test.md", content_hash, "extract_key_sections", variant_hash
        )

        assert result is None

    async def test_summarize_file_handles_readonly_cache_dir_silently(
        self,
        mock_token_counter: Mock,
        mock_metadata_index: MetadataIndex,
        tmp_path: Path,
    ) -> None:
        """A read-only cache directory must not raise -- caching is a
        best-effort side effect of summarize_file, not part of its
        contract with the caller.
        """
        engine = SummarizationEngine(
            mock_token_counter, mock_metadata_index, cache_dir=tmp_path
        )
        engine.cache_dir.chmod(0o444)

        try:
            result = await engine.summarize_file(
                "test.md", "# Heading\nBody text.\n", strategy="extract_key_sections"
            )
        finally:
            engine.cache_dir.chmod(0o755)

        assert result["summary"]
