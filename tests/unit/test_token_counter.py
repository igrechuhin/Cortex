"""
Unit tests for token_counter module.

Tests token counting functionality using tiktoken.
"""

from pathlib import Path

import pytest

from cortex.core.token_counter import TokenCounter


class TestTokenCounterInitialization:
    """Tests for TokenCounter initialization."""

    def test_initialization_with_default_model(self):
        """Test TokenCounter initializes with default model."""
        # Arrange & Act
        counter = TokenCounter()

        # Assert
        assert counter is not None
        assert counter.model == "cl100k_base"

    def test_initialization_with_custom_model(self):
        """Test TokenCounter initializes with custom model."""
        # Arrange
        model_name = "gpt2"

        # Act
        counter = TokenCounter(model=model_name)

        # Assert
        assert counter.model == model_name

    def test_encoding_lazy_initialization(self):
        """Test encoding is lazily initialized."""
        # Arrange & Act
        counter = TokenCounter()

        # Assert
        # Encoding should not be loaded until first use
        assert counter.encoding_impl is None


class TestCountTokens:
    """Tests for count_tokens method."""

    def test_count_tokens_empty_string(self):
        """Test counting tokens in empty string returns zero."""
        # Arrange
        counter = TokenCounter()

        # Act
        count = counter.count_tokens("")

        # Assert
        assert count == 0

    def test_count_tokens_simple_text(self):
        """Test counting tokens in simple text."""
        # Arrange
        counter = TokenCounter()
        text = "Hello, world!"

        # Act
        count = counter.count_tokens(text)

        # Assert
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_markdown_content(self):
        """Test counting tokens in markdown content."""
        # Arrange
        counter = TokenCounter()
        markdown = """# Project Brief

## Overview
This is a test project for Memory Bank.

## Goals
- Implement feature A
- Add test coverage
- Update documentation
"""

        # Act
        count = counter.count_tokens(markdown)

        # Assert
        assert count > 20  # Should have significant number of tokens
        assert isinstance(count, int)

    def test_count_tokens_code_block(self):
        """Test counting tokens in code block."""
        # Arrange
        counter = TokenCounter()
        code = """```python
def hello_world():
    print("Hello, world!")
    return True
```"""

        # Act
        count = counter.count_tokens(code)

        # Assert
        assert count >= 10
        assert isinstance(count, int)

    def test_count_tokens_unicode_content(self):
        """Test counting tokens with unicode characters."""
        # Arrange
        counter = TokenCounter()
        unicode_text = "Hello 世界! Привет мир! 🚀"

        # Act
        count = counter.count_tokens(unicode_text)

        # Assert
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_repeating_content(self):
        """Test counting tokens with repeating content."""
        # Arrange
        counter = TokenCounter()
        short_text = "Hello"
        long_text = " ".join([short_text] * 100)

        # Act
        short_count = counter.count_tokens(short_text)
        long_count = counter.count_tokens(long_text)

        # Assert
        assert long_count > short_count
        # Approximately 100x more tokens (accounting for spaces)
        assert long_count >= short_count * 90


class TestCountTokensInFile:
    """Tests for count_tokens_in_file method."""

    @pytest.mark.asyncio
    async def test_count_tokens_in_file_simple(self, temp_project_root: Path):
        """Test counting tokens in a simple file."""
        # Arrange
        counter = TokenCounter()
        file_path: Path = temp_project_root / "test.md"
        content = "# Test File\n\nThis is a test."
        _ = file_path.write_text(content)

        # Act
        count = await counter.count_tokens_in_file(file_path)

        # Assert
        assert count > 0
        # Should match direct count
        direct_count = counter.count_tokens(content)
        assert count == direct_count

    @pytest.mark.asyncio
    async def test_count_tokens_in_file_large_file(self, temp_project_root: Path):
        """Test counting tokens in a large file."""
        # Arrange
        counter = TokenCounter()
        file_path: Path = temp_project_root / "large.md"
        # Create large content (about 1000 words)
        content = " ".join(["word"] * 1000)
        _ = file_path.write_text(content)

        # Act
        count = await counter.count_tokens_in_file(file_path)

        # Assert
        assert count > 500  # Should have many tokens
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_count_tokens_in_file_nonexistent(self, temp_project_root: Path):
        """Test counting tokens in nonexistent file raises error."""
        # Arrange
        counter = TokenCounter()
        file_path: Path = temp_project_root / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            _ = await counter.count_tokens_in_file(file_path)

    @pytest.mark.asyncio
    async def test_count_tokens_in_file_empty(self, temp_project_root: Path):
        """Test counting tokens in empty file returns zero."""
        # Arrange
        counter = TokenCounter()
        file_path: Path = temp_project_root / "empty.md"
        _ = file_path.write_text("")

        # Act
        count = await counter.count_tokens_in_file(file_path)

        # Assert
        assert count == 0


class TestParseMarkdownSections:
    """Tests for parse_markdown_sections method."""

    def test_parse_markdown_sections_simple(self):
        """Test parsing simple markdown sections."""
        # Arrange
        counter = TokenCounter()
        content = """# Main Title

## Section 1
Content for section 1.

## Section 2
Content for section 2.
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        assert len(sections) == 3  # Main Title, Section 1, Section 2
        assert sections[0]["title"] == "Main Title"
        assert sections[0]["level"] == 1
        assert sections[1]["title"] == "Section 1"
        assert sections[1]["level"] == 2

    def test_parse_markdown_sections_nested(self):
        """Test parsing nested markdown sections."""
        # Arrange
        counter = TokenCounter()
        content = """# Level 1

## Level 2

### Level 3

Content here.

## Another Level 2
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        assert len(sections) == 4
        assert sections[0]["level"] == 1
        assert sections[1]["level"] == 2
        assert sections[2]["level"] == 3
        assert sections[3]["level"] == 2

    def test_parse_markdown_sections_with_line_numbers(self):
        """Test parsing sections includes line numbers."""
        # Arrange
        counter = TokenCounter()
        content = """# First
Line 2
Line 3
## Second
Line 5
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        assert len(sections) == 2
        assert sections[0]["start_line"] == 1
        assert sections[1]["start_line"] == 4

    def test_parse_markdown_sections_empty_content(self):
        """Test parsing empty content returns empty list."""
        # Arrange
        counter = TokenCounter()

        # Act
        sections = counter.parse_markdown_sections("")

        # Assert
        assert sections == []

    def test_parse_markdown_sections_no_headers(self):
        """Test parsing content without headers returns empty list."""
        # Arrange
        counter = TokenCounter()
        content = "Just regular text without any headers."

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        assert sections == []

    def test_parse_markdown_sections_with_hash_in_content(self):
        """Test parsing sections with hash symbols in content."""
        # Arrange
        counter = TokenCounter()
        content = """# Real Header

This is not a header: # Hash in middle of line
And this is code: `#define MACRO`

## Another Real Header
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        # Should only find real headers (at start of line)
        assert len(sections) == 2
        assert sections[0]["title"] == "Real Header"
        assert sections[1]["title"] == "Another Real Header"


class TestContentHashing:
    """Tests for content_hash method."""

    def test_content_hash_simple(self):
        """Test generating hash for simple content."""
        # Arrange
        counter = TokenCounter()
        content = "Test content"

        # Act
        hash_value = counter.content_hash(content)

        # Assert
        assert hash_value is not None
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex digest length

    def test_content_hash_deterministic(self):
        """Test that same content produces same hash."""
        # Arrange
        counter = TokenCounter()
        content = "Test content for hashing"

        # Act
        hash1 = counter.content_hash(content)
        hash2 = counter.content_hash(content)

        # Assert
        assert hash1 == hash2

    def test_content_hash_different_content(self):
        """Test that different content produces different hashes."""
        # Arrange
        counter = TokenCounter()
        content1 = "Content A"
        content2 = "Content B"

        # Act
        hash1 = counter.content_hash(content1)
        hash2 = counter.content_hash(content2)

        # Assert
        assert hash1 != hash2

    def test_content_hash_empty_string(self):
        """Test hashing empty string."""
        # Arrange
        counter = TokenCounter()

        # Act
        hash_value = counter.content_hash("")

        # Assert
        assert hash_value is not None
        assert len(hash_value) == 64

    def test_content_hash_unicode(self):
        """Test hashing unicode content."""
        # Arrange
        counter = TokenCounter()
        content = "Hello 世界 🌍"

        # Act
        hash_value = counter.content_hash(content)

        # Assert
        assert hash_value is not None
        assert len(hash_value) == 64


class TestTokenCounterCaching:
    """Tests for token counting caching behavior."""

    def test_encoding_cached_after_first_use(self):
        """Test that encoding is cached after first use."""
        # Arrange
        counter = TokenCounter()
        assert counter.encoding_impl is None

        # Act
        _ = counter.count_tokens("test")

        # Assert
        assert counter.encoding_impl is not None

    def test_multiple_counts_use_cached_encoding(self):
        """Test that multiple counts reuse cached encoding."""
        # Arrange
        counter = TokenCounter()

        # Act
        count1 = counter.count_tokens("first text")
        encoding_after_first = counter.encoding_impl
        count2 = counter.count_tokens("second text")
        encoding_after_second = counter.encoding_impl

        # Assert
        assert encoding_after_first is encoding_after_second
        assert count1 > 0
        assert count2 > 0


class TestTokenCounterEdgeCases:
    """Tests for edge cases and error handling."""

    def test_count_tokens_with_None_raises_error(self):
        """Test counting tokens with None raises TypeError."""
        # Arrange
        counter = TokenCounter()

        # Act & Assert
        with pytest.raises(TypeError):
            counter.count_tokens(None)  # type: ignore[arg-type]

    def test_parse_sections_with_None_raises_error(self):
        """Test parsing sections with None raises TypeError."""
        # Arrange
        counter = TokenCounter()

        # Act & Assert
        with pytest.raises(TypeError):
            counter.parse_markdown_sections(None)  # type: ignore[arg-type]

    def test_content_hash_with_None_raises_error(self):
        """Test hashing None raises TypeError."""
        # Arrange
        counter = TokenCounter()

        # Act & Assert
        with pytest.raises(TypeError):
            counter.content_hash(None)  # type: ignore[arg-type]
