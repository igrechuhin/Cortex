"""
Unit tests for token_counter module.

Tests token counting functionality using tiktoken.
"""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

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

    def test_parse_markdown_sections_with_invalid_levels(self):
        """Test parse_markdown_sections ignores headers with invalid levels."""
        # Arrange
        counter = TokenCounter()
        content = """####### Invalid level 7
# Valid level 1
######## Invalid level 8
## Valid level 2
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        # Should only find valid headers (levels 1-6)
        assert len(sections) == 2
        assert sections[0]["level"] == 1
        assert sections[1]["level"] == 2

    def test_parse_markdown_sections_with_hash_not_at_start(self):
        """Test parse_markdown_sections handles indented headers and hashes in content."""
        # Arrange
        counter = TokenCounter()
        content = """   # Indented header (still detected)
# Real header
Text with # hash in middle (not detected)
"""

        # Act
        sections = counter.parse_markdown_sections(content)

        # Assert
        # Indented headers are still detected (lstrip removes leading whitespace)
        # Hashes in middle of line are not detected
        assert len(sections) == 2
        assert sections[0]["title"] == "Indented header (still detected)"
        assert sections[1]["title"] == "Real header"


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


class TestCountTokensWithCache:
    """Tests for count_tokens_with_cache method."""

    def test_count_tokens_with_cache_caches_result(self):
        """Test that count_tokens_with_cache caches results."""
        # Arrange
        counter = TokenCounter()
        text = "Test content for caching"
        content_hash = counter.content_hash(text)

        # Act
        count1 = counter.count_tokens_with_cache(text, content_hash)
        count2 = counter.count_tokens_with_cache(text, content_hash)

        # Assert
        assert count1 == count2
        assert count1 > 0

    def test_count_tokens_with_cache_different_hashes(self):
        """Test that different hashes produce different cached results."""
        # Arrange
        counter = TokenCounter()
        text1 = "This is a much longer text that should have significantly more tokens than a short one."
        text2 = "Short."
        hash1 = counter.content_hash(text1)
        hash2 = counter.content_hash(text2)

        # Act
        count1 = counter.count_tokens_with_cache(text1, hash1)
        count2 = counter.count_tokens_with_cache(text2, hash2)

        # Assert
        # Different texts should produce different token counts
        assert count1 > count2
        # Verify cache is working
        assert counter.get_cache_size() == 2


class TestCountTokensSections:
    """Tests for count_tokens_sections method."""

    def test_count_tokens_sections_simple(self):
        """Test counting tokens per section."""
        # Arrange
        counter = TokenCounter()
        content = """# Section 1
Content for section 1.

## Section 2
Content for section 2.
"""
        sections: list[dict[str, object]] = [
            {"heading": "# Section 1", "line_start": 1, "line_end": 3},
            {"heading": "## Section 2", "line_start": 4, "line_end": 6},
        ]

        # Act
        result = counter.count_tokens_sections(content, sections)

        # Assert
        assert "total_tokens" in result
        assert "sections" in result
        total_tokens = cast(int, result["total_tokens"])
        sections_list = cast(list[dict[str, object]], result["sections"])
        assert len(sections_list) == 2
        assert total_tokens > 0
        assert isinstance(sections_list[0], dict)
        assert isinstance(sections_list[1], dict)
        assert "token_count" in sections_list[0]
        assert "token_count" in sections_list[1]
        token_count_0 = cast(int, sections_list[0]["token_count"])
        token_count_1 = cast(int, sections_list[1]["token_count"])
        assert token_count_0 > 0
        assert token_count_1 > 0

    def test_count_tokens_sections_with_percentages(self):
        """Test that sections include percentage calculations."""
        # Arrange
        counter = TokenCounter()
        content = "Line 1\nLine 2\nLine 3"
        sections: list[dict[str, object]] = [
            {"heading": "Test", "line_start": 1, "line_end": 3}
        ]

        # Act
        result = counter.count_tokens_sections(content, sections)

        # Assert
        sections_list = cast(list[dict[str, object]], result["sections"])
        assert len(sections_list) > 0
        assert "percentage" in sections_list[0]
        percentage = cast(float, sections_list[0]["percentage"])
        assert isinstance(percentage, float)
        assert 0 <= percentage <= 100

    def test_count_tokens_sections_with_empty_sections(self):
        """Test count_tokens_sections with empty sections list."""
        # Arrange
        counter = TokenCounter()
        content = "Some content here"

        # Act
        result = counter.count_tokens_sections(content, [])

        # Assert
        total_tokens = cast(int, result["total_tokens"])
        sections_list = cast(list[dict[str, object]], result["sections"])
        assert total_tokens > 0
        assert sections_list == []


class TestEstimateContextSize:
    """Tests for estimate_context_size method."""

    def test_estimate_context_size_simple(self):
        """Test estimating context size for multiple files."""
        # Arrange
        counter = TokenCounter()
        file_tokens = {"file1.md": 500, "file2.md": 800, "file3.md": 300}

        # Act
        result = counter.estimate_context_size(file_tokens)

        # Assert
        total_tokens = cast(int, result["total_tokens"])
        breakdown = cast(dict[str, int], result["breakdown"])
        assert total_tokens == 1600
        assert "estimated_cost_gpt4" in result
        assert "warnings" in result
        assert "breakdown" in result
        assert breakdown == file_tokens

    def test_estimate_context_size_with_warnings(self):
        """Test that warnings are generated for large token counts."""
        # Arrange
        counter = TokenCounter()
        file_tokens = {"large.md": 150000}

        # Act
        result = counter.estimate_context_size(file_tokens)

        # Assert
        total_tokens = cast(int, result["total_tokens"])
        warnings = cast(list[str], result["warnings"])
        assert total_tokens == 150000
        assert len(warnings) > 0
        assert any("100K" in warning or "100000" in warning for warning in warnings)

    def test_estimate_context_size_very_large(self):
        """Test warnings for very large token counts."""
        # Arrange
        counter = TokenCounter()
        file_tokens = {"huge.md": 250000}

        # Act
        result = counter.estimate_context_size(file_tokens)

        # Assert
        total_tokens = cast(int, result["total_tokens"])
        warnings = cast(list[str], result["warnings"])
        assert total_tokens == 250000
        assert len(warnings) >= 2
        # Check for warnings about exceeding limits
        warning_text = " ".join(warnings)
        assert (
            "200000" in warning_text
            or "200K" in warning_text
            or "exceeds most model" in warning_text.lower()
        )

    def test_estimate_context_size_medium_size(self):
        """Test estimate_context_size with medium token count (50K-100K)."""
        # Arrange
        counter = TokenCounter()
        file_tokens = {"medium.md": 75000}

        # Act
        result = counter.estimate_context_size(file_tokens)

        # Assert
        total_tokens = cast(int, result["total_tokens"])
        warnings = cast(list[str], result["warnings"])
        assert total_tokens == 75000
        # Should trigger the 50K-100K warning
        assert len(warnings) > 0
        assert any(
            "50K" in warning or "progressive" in warning.lower() for warning in warnings
        )


class TestCacheManagement:
    """Tests for cache management methods."""

    def test_clear_cache(self):
        """Test clearing the cache."""
        # Arrange
        counter = TokenCounter()
        text = "Test content"
        content_hash = counter.content_hash(text)
        _ = counter.count_tokens_with_cache(text, content_hash)

        # Act
        counter.clear_cache()

        # Assert
        assert counter.get_cache_size() == 0

    def test_get_cache_size(self):
        """Test getting cache size."""
        # Arrange
        counter = TokenCounter()
        text1 = "First content"
        text2 = "Second content"
        hash1 = counter.content_hash(text1)
        hash2 = counter.content_hash(text2)

        # Act
        _ = counter.count_tokens_with_cache(text1, hash1)
        size1 = counter.get_cache_size()
        _ = counter.count_tokens_with_cache(text2, hash2)
        size2 = counter.get_cache_size()

        # Assert
        assert size1 == 1
        assert size2 == 2


class TestTiktokenTimeoutAndRetry:
    """Tests for tiktoken loading timeout and retry mechanism."""

    def test_load_tiktoken_with_timeout_success(self):
        """Test successful tiktoken loading within timeout."""
        # Arrange
        counter = TokenCounter()
        mock_encoding = MagicMock()

        # Patch the import inside the method by patching sys.modules
        import sys

        mock_tiktoken = MagicMock()
        mock_tiktoken.get_encoding.return_value = mock_encoding
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                mock_future = MagicMock()
                mock_future.result.return_value = mock_encoding
                mock_executor.return_value.__enter__.return_value.submit.return_value = (
                    mock_future
                )

                # Act
                result = counter._load_tiktoken_with_timeout(
                    timeout_seconds=30.0, max_retries=2
                )

                # Assert
                assert result is mock_encoding
                assert counter._tiktoken_available is True
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_with_timeout_retry_success(self):
        """Test tiktoken loading succeeds after retry."""
        # Arrange
        counter = TokenCounter()
        mock_encoding = MagicMock()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                with patch("time.sleep"):
                    # First attempt times out, second succeeds
                    mock_future = MagicMock()
                    mock_future.result.side_effect = [
                        TimeoutError("Timeout"),
                        mock_encoding,
                    ]
                    mock_executor.return_value.__enter__.return_value.submit.return_value = (
                        mock_future
                    )

                    # Act
                    result = counter._load_tiktoken_with_timeout(
                        timeout_seconds=0.1, max_retries=1
                    )

                    # Assert
                    assert result is mock_encoding
                    assert counter._tiktoken_available is True
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_with_timeout_all_retries_fail(self):
        """Test tiktoken loading fails after all retries."""
        # Arrange
        counter = TokenCounter()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                with patch("time.sleep"):
                    # All attempts timeout
                    mock_future = MagicMock()
                    mock_future.result.side_effect = TimeoutError("Timeout")
                    mock_executor.return_value.__enter__.return_value.submit.return_value = (
                        mock_future
                    )

                    # Act
                    result = counter._load_tiktoken_with_timeout(
                        timeout_seconds=0.1, max_retries=2
                    )

                    # Assert
                    assert result is None
                    assert counter._tiktoken_available is False
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_with_exception_retry_success(self):
        """Test tiktoken loading succeeds after exception retry."""
        # Arrange
        counter = TokenCounter()
        mock_encoding = MagicMock()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                with patch("time.sleep"):
                    # First attempt raises exception, second succeeds
                    mock_future = MagicMock()
                    mock_future.result.side_effect = [
                        ValueError("Network error"),
                        mock_encoding,
                    ]
                    mock_executor.return_value.__enter__.return_value.submit.return_value = (
                        mock_future
                    )

                    # Act
                    result = counter._load_tiktoken_with_timeout(
                        timeout_seconds=30.0, max_retries=1
                    )

                    # Assert
                    assert result is mock_encoding
                    assert counter._tiktoken_available is True
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_with_exception_all_retries_fail(self):
        """Test tiktoken loading fails after all exception retries."""
        # Arrange
        counter = TokenCounter()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                with patch("time.sleep"):
                    # All attempts raise exceptions
                    mock_future = MagicMock()
                    mock_future.result.side_effect = ValueError("Network error")
                    mock_executor.return_value.__enter__.return_value.submit.return_value = (
                        mock_future
                    )

                    # Act
                    result = counter._load_tiktoken_with_timeout(
                        timeout_seconds=30.0, max_retries=2
                    )

                    # Assert
                    assert result is None
                    assert counter._tiktoken_available is False
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_with_import_error(self):
        """Test tiktoken loading handles ImportError gracefully."""
        # Arrange
        counter = TokenCounter()

        import sys

        original_tiktoken = sys.modules.get("tiktoken")
        if "tiktoken" in sys.modules:
            del sys.modules["tiktoken"]

        try:
            # Create a mock that raises ImportError for tiktoken
            import builtins

            original_import = builtins.__import__

            def import_side_effect(
                name, globals=None, locals=None, fromlist=(), level=0
            ):
                if name == "tiktoken":
                    raise ImportError("No module named 'tiktoken'")
                return original_import(name, globals, locals, fromlist, level)

            builtins.__import__ = import_side_effect

            try:
                # Act
                result = counter._load_tiktoken_with_timeout(
                    timeout_seconds=30.0, max_retries=2
                )

                # Assert
                assert result is None
                assert counter._tiktoken_available is False
            finally:
                builtins.__import__ = original_import
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken

    def test_load_tiktoken_exponential_backoff_timing(self):
        """Test that retry delays use exponential backoff."""
        # Arrange
        counter = TokenCounter()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                with patch("time.sleep") as mock_sleep:
                    with patch("time.time", side_effect=[0.0, 0.1, 2.1, 2.2, 6.2, 6.3]):
                        # All attempts timeout
                        mock_future = MagicMock()
                        mock_future.result.side_effect = TimeoutError("Timeout")
                        mock_executor.return_value.__enter__.return_value.submit.return_value = (
                            mock_future
                        )

                        # Act
                        _ = counter._load_tiktoken_with_timeout(
                            timeout_seconds=0.1, max_retries=2
                        )

                        # Assert
                        # Should sleep with exponential backoff: 2.0s, 4.0s
                        assert mock_sleep.call_count == 2
                        assert (
                            mock_sleep.call_args_list[0][0][0] == 2.0
                        )  # First retry: 2s
                        assert (
                            mock_sleep.call_args_list[1][0][0] == 4.0
                        )  # Second retry: 4s
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_count_tokens_fallback_to_word_estimation_on_timeout(self):
        """Test that count_tokens falls back to word estimation when tiktoken times out."""
        # Arrange
        counter = TokenCounter()
        text = "This is a test text with multiple words"

        # Simulate timeout by setting encoding_impl to None and disabling tiktoken
        counter._tiktoken_available = False  # Disable tiktoken to force fallback
        counter.encoding_impl = None

        # Act
        count = counter.count_tokens(text)

        # Assert
        assert count > 0
        # Word-based estimation: ~1 token per 4 characters
        expected_min = len(text) // 4
        assert count >= expected_min
        # Verify fallback was used (tiktoken is disabled)
        assert counter._tiktoken_available is False

    def test_is_network_error_detection(self):
        """Test network error detection logic."""
        # Arrange
        counter = TokenCounter()

        # Act & Assert - Network errors
        assert counter._is_network_error(TimeoutError("Connection timeout"))
        assert counter._is_network_error(ConnectionError("Connection refused"))
        assert counter._is_network_error(Exception("DNS resolution failed"))
        assert counter._is_network_error(Exception("Network unreachable"))
        assert counter._is_network_error(Exception("SSL certificate error"))

        # Act & Assert - Non-network errors
        assert not counter._is_network_error(ValueError("Invalid model name"))
        assert not counter._is_network_error(KeyError("Missing key"))
        assert not counter._is_network_error(Exception("Generic error"))

    def test_load_tiktoken_handles_network_unavailable_gracefully(self):
        """Test that network unavailability is handled gracefully."""
        # Arrange
        counter = TokenCounter()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                # Simulate network error (connection refused)
                mock_future = MagicMock()
                mock_future.result.side_effect = ConnectionError("Connection refused")
                mock_executor.return_value.__enter__.return_value.submit.return_value = (
                    mock_future
                )

                # Act
                result = counter._load_tiktoken_with_timeout(
                    timeout_seconds=30.0, max_retries=1
                )

                # Assert
                assert result is None
                assert counter._tiktoken_available is False
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]

    def test_load_tiktoken_handles_non_network_errors_differently(self):
        """Test that non-network errors are handled without retries."""
        # Arrange
        counter = TokenCounter()

        import sys

        mock_tiktoken = MagicMock()
        original_tiktoken = sys.modules.get("tiktoken")
        sys.modules["tiktoken"] = mock_tiktoken

        try:
            with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
                # Simulate non-network error (invalid model)
                mock_future = MagicMock()
                mock_future.result.side_effect = ValueError("Invalid encoding name")
                mock_executor.return_value.__enter__.return_value.submit.return_value = (
                    mock_future
                )

                # Act
                result = counter._load_tiktoken_with_timeout(
                    timeout_seconds=30.0, max_retries=2
                )

                # Assert
                assert result is None
                assert counter._tiktoken_available is False
                # Should not retry non-network errors
                assert mock_future.result.call_count == 1
        finally:
            if original_tiktoken is not None:
                sys.modules["tiktoken"] = original_tiktoken
            elif "tiktoken" in sys.modules:
                del sys.modules["tiktoken"]
