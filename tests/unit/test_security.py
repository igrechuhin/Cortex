"""Security tests for input validation, integrity checks, and rate limiting."""

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import cast

import pytest

from cortex.core.exceptions import IndexCorruptedError
from cortex.core.security import (
    CommitMessageSanitizer,
    HTMLEscaper,
    InputValidator,
    JSONIntegrity,
    RateLimiter,
    RegexValidator,
)


class TestInputValidator:
    """Test input validation functionality."""

    def test_validate_file_name_valid(self):
        """Test validation of valid file names."""
        assert InputValidator.validate_file_name("test.md") == "test.md"
        assert InputValidator.validate_file_name("test-file_2.md") == "test-file_2.md"

    def test_validate_file_name_empty(self):
        """Test validation rejects empty file names."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _ = InputValidator.validate_file_name("")

    def test_validate_file_name_path_traversal(self):
        """Test validation rejects path traversal attempts."""
        with pytest.raises(ValueError, match="path traversal"):
            _ = InputValidator.validate_file_name("../etc/passwd")

        with pytest.raises(ValueError, match="path traversal"):
            _ = InputValidator.validate_file_name("..\\windows\\system32")

        with pytest.raises(ValueError, match="path traversal"):
            _ = InputValidator.validate_file_name("/etc/passwd")

        with pytest.raises(ValueError, match="path traversal"):
            _ = InputValidator.validate_file_name("\\windows\\system32")

    def test_validate_file_name_invalid_characters(self):
        """Test validation rejects invalid characters."""
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*", "\0"]

        for char in invalid_chars:
            with pytest.raises(ValueError, match="invalid characters"):
                _ = InputValidator.validate_file_name(f"test{char}file.md")

    def test_validate_file_name_reserved_names(self):
        """Test validation rejects Windows reserved names."""
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]

        for name in reserved:
            with pytest.raises(ValueError, match="reserved"):
                _ = InputValidator.validate_file_name(name)

            # Case insensitive
            with pytest.raises(ValueError, match="reserved"):
                _ = InputValidator.validate_file_name(name.lower())

    def test_validate_file_name_ending(self):
        """Test validation rejects files ending with period or space."""
        with pytest.raises(ValueError, match="cannot end"):
            _ = InputValidator.validate_file_name("test.")

        with pytest.raises(ValueError, match="cannot end"):
            _ = InputValidator.validate_file_name("test ")

    def test_validate_file_name_length(self):
        """Test validation rejects files that are too long."""
        long_name = "a" * 300
        with pytest.raises(ValueError, match="too long"):
            _ = InputValidator.validate_file_name(long_name)

    def test_validate_path_valid(self):
        """Test path validation for valid paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            test_path = base / "subdir" / "file.md"

            assert InputValidator.validate_path(test_path, base)

    def test_validate_path_traversal(self):
        """Test path validation rejects directory traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            parent_path = base.parent / "outside.md"

            with pytest.raises(ValueError, match="outside base directory"):
                _ = InputValidator.validate_path(parent_path, base)

    def test_validate_string_input_valid(self):
        """Test string input validation for valid strings."""
        assert InputValidator.validate_string_input("test") == "test"
        assert (
            InputValidator.validate_string_input("test\n", allow_newlines=True)
            == "test\n"
        )

    def test_validate_string_input_too_long(self):
        """Test string validation rejects strings that are too long."""
        with pytest.raises(ValueError, match="too long"):
            _ = InputValidator.validate_string_input("a" * 20000, max_length=10000)

    def test_validate_string_input_newlines(self):
        """Test string validation can reject newlines."""
        with pytest.raises(ValueError, match="Newlines not allowed"):
            _ = InputValidator.validate_string_input("test\n", allow_newlines=False)

    def test_validate_string_input_pattern(self):
        """Test string validation with regex pattern."""
        # Valid pattern
        assert (
            InputValidator.validate_string_input("test123", pattern=r"^[a-z0-9]+$")
            == "test123"
        )

        # Invalid pattern
        with pytest.raises(ValueError, match="does not match"):
            _ = InputValidator.validate_string_input("Test_123", pattern=r"^[a-z0-9]+$")


class TestJSONIntegrity:
    """Test JSON integrity checks."""

    @pytest.mark.asyncio
    async def test_save_and_load_with_integrity(self):
        """Test saving and loading JSON with integrity checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_data: dict[str, object] = {"key": "value", "number": 42}

            # Save with integrity
            await JSONIntegrity.save_with_integrity(test_file, test_data)

            # Load and verify
            loaded_data = await JSONIntegrity.load_with_integrity(test_file)
            assert loaded_data == test_data

    @pytest.mark.asyncio
    async def test_load_with_integrity_tampered(self):
        """Test loading detects tampered data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_data: dict[str, object] = {"key": "value"}

            # Save with integrity
            await JSONIntegrity.save_with_integrity(test_file, test_data)

            # Tamper with the file
            async with __import__("aiofiles").open(test_file, "r") as f:
                content = await f.read()
            wrapper = json.loads(content)
            wrapper["data"]["key"] = "modified"

            async with __import__("aiofiles").open(test_file, "w") as f:
                await f.write(json.dumps(wrapper))

            # Should detect tampering
            with pytest.raises(IndexCorruptedError, match="Integrity check failed"):
                _ = await JSONIntegrity.load_with_integrity(test_file)

    @pytest.mark.asyncio
    async def test_load_legacy_format(self):
        """Test loading JSON without integrity wrapper (legacy format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_data = {"key": "value"}

            # Write legacy format (no integrity wrapper)
            async with __import__("aiofiles").open(test_file, "w") as f:
                await f.write(json.dumps(test_data))

            # Should still load successfully
            loaded_data = await JSONIntegrity.load_with_integrity(test_file)
            assert loaded_data == test_data


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_within_limit(self):
        """Test operations within rate limit proceed immediately."""
        limiter = RateLimiter(max_ops=10, window_seconds=1.0)

        # Should complete quickly (all within limit)
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 0.1  # Should be nearly instant
        assert limiter.get_current_count() == 5

    @pytest.mark.asyncio
    async def test_rate_limiter_exceeds_limit(self):
        """Test operations beyond rate limit are throttled."""
        limiter = RateLimiter(max_ops=5, window_seconds=0.5)

        # Fill up the limit
        for _ in range(5):
            await limiter.acquire()

        # Next operation should wait
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        # Should have waited approximately window_seconds
        assert elapsed >= 0.4  # Allow some timing variance

    @pytest.mark.asyncio
    async def test_rate_limiter_reset(self):
        """Test rate limiter reset."""
        limiter = RateLimiter(max_ops=5, window_seconds=1.0)

        # Fill up the limit
        for _ in range(5):
            await limiter.acquire()
        assert limiter.get_current_count() == 5

        # Reset
        limiter.reset()
        assert limiter.get_current_count() == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent(self):
        """Test rate limiter with concurrent operations."""
        limiter = RateLimiter(max_ops=10, window_seconds=1.0)

        async def worker():
            await limiter.acquire()
            return True

        # Run 10 concurrent operations
        results = await asyncio.gather(*[worker() for _ in range(10)])
        assert all(results)
        assert limiter.get_current_count() == 10

    @pytest.mark.asyncio
    async def test_rate_limiter_window_expiry(self):
        """Test operations expire after window."""
        limiter = RateLimiter(max_ops=5, window_seconds=0.2)

        # Fill up the limit
        for _ in range(5):
            await limiter.acquire()
        assert limiter.get_current_count() == 5

        # Wait for window to expire
        await asyncio.sleep(0.3)

        # Old operations should have expired
        assert limiter.get_current_count() == 0

        # Should be able to perform new operations immediately
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1

    def test_validate_file_name_windows_drive_letter(self):
        """Test validation rejects Windows drive letter paths."""
        with pytest.raises(ValueError, match="absolute path"):
            _ = InputValidator.validate_file_name("C:\\Users\\test.md")

    def test_validate_path_symlink_escape(self):
        """Test path validation with symlink that escapes base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"
            base.mkdir()

            outside = Path(tmpdir) / "outside"
            outside.mkdir()

            # Create symlink inside base pointing to outside
            symlink_path = base / "link"
            symlink_path.symlink_to(outside)

            # Validation should reject symlink pointing outside base
            with pytest.raises(ValueError, match="outside base directory"):
                _ = InputValidator.validate_path(symlink_path / "file.txt", base)

    @pytest.mark.asyncio
    async def test_json_integrity_empty_data(self):
        """Test saving and loading empty JSON data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "empty.json"
            test_data: dict[str, object] = {}

            # Save empty data with integrity
            await JSONIntegrity.save_with_integrity(test_file, test_data)

            # Load and verify
            loaded_data = await JSONIntegrity.load_with_integrity(test_file)
            assert loaded_data == test_data

    def test_validate_string_input_null_bytes(self):
        """Test string validation rejects null bytes."""
        with pytest.raises(ValueError):
            # Null bytes could be used for injection attacks
            _ = InputValidator.validate_string_input("test\0file", allow_newlines=False)

    def test_validate_git_url_case_insensitive_localhost(self):
        """Test that localhost check is case insensitive."""
        with pytest.raises(ValueError, match="cannot reference localhost"):
            _ = InputValidator.validate_git_url("https://LocalHost/repo.git")

    def test_validate_git_url_ipv6_loopback(self):
        """Test that IPv6 loopback address is blocked."""
        with pytest.raises(ValueError, match="cannot reference localhost"):
            _ = InputValidator.validate_git_url("https://[::1]/repo.git")


class TestCommitMessageSanitizer:
    """Test commit message sanitization for command injection prevention."""

    def test_sanitize_valid_message(self):
        """Test sanitization of a valid commit message."""
        # Arrange
        message = "Add new feature for user authentication"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert result == "Add new feature for user authentication"

    def test_sanitize_removes_null_bytes(self):
        """Test that null bytes are removed from commit messages."""
        # Arrange
        message = "Fix bug\0 with injection"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert "\0" not in result
        assert result == "Fix bug with injection"

    def test_sanitize_removes_control_characters(self):
        """Test that control characters (except newline/tab) are removed."""
        # Arrange - includes bell character (0x07) and form feed (0x0C)
        message = "Fix\x07bug\x0cwith control chars"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert "\x07" not in result
        assert "\x0c" not in result

    def test_sanitize_removes_shell_metacharacters(self):
        """Test that shell metacharacters are removed."""
        # Arrange
        message = "Fix bug; rm -rf /; echo $(whoami)"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert ";" not in result
        assert "$" not in result
        assert "(" not in result
        assert ")" not in result
        # Should contain sanitized content
        assert "Fix bug" in result

    def test_sanitize_removes_backticks(self):
        """Test that backticks for command substitution are removed."""
        # Arrange
        message = "Fix `id` injection"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert "`" not in result

    def test_sanitize_removes_pipes_and_redirects(self):
        """Test that pipes and redirects are removed."""
        # Arrange
        message = "Fix bug | cat /etc/passwd > /tmp/out"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert "|" not in result
        assert ">" not in result
        assert "<" not in result

    def test_sanitize_truncates_long_messages(self):
        """Test that long messages are truncated."""
        # Arrange
        long_message = "A" * 20000

        # Act
        result = CommitMessageSanitizer.sanitize(long_message)

        # Assert
        assert len(result) <= CommitMessageSanitizer.MAX_MESSAGE_LENGTH

    def test_sanitize_custom_max_length(self):
        """Test truncation with custom max length."""
        # Arrange
        message = "A" * 200

        # Act
        result = CommitMessageSanitizer.sanitize(message, max_length=100)

        # Assert
        assert len(result) == 100

    def test_sanitize_normalizes_whitespace(self):
        """Test that multiple spaces are collapsed."""
        # Arrange
        message = "Fix   multiple    spaces"

        # Act
        result = CommitMessageSanitizer.sanitize(message)

        # Assert
        assert result == "Fix multiple spaces"

    def test_sanitize_empty_after_sanitization_raises(self):
        """Test that empty message after sanitization raises ValueError."""
        # Arrange - message with only control characters
        message = "; | < > $ () {} []"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot be empty after sanitization"):
            _ = CommitMessageSanitizer.sanitize(message)

    def test_validate_valid_message(self):
        """Test validation returns True for valid messages."""
        # Arrange
        message = "Add new feature"

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is True
        assert error is None

    def test_validate_empty_message(self):
        """Test validation returns error for empty messages."""
        # Arrange
        message = ""

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "empty" in error.lower()

    def test_validate_null_bytes(self):
        """Test validation returns error for null bytes."""
        # Arrange
        message = "Message\0with null"

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "null" in error.lower()

    def test_validate_control_characters(self):
        """Test validation returns error for control characters."""
        # Arrange
        message = "Message\x07with bell"

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "control character" in error.lower()

    def test_validate_shell_metacharacters(self):
        """Test validation returns error for shell metacharacters."""
        # Arrange
        message = "Message with $(command)"

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "metacharacter" in error.lower()

    def test_validate_too_long_message(self):
        """Test validation returns error for overly long messages."""
        # Arrange
        message = "A" * 20000

        # Act
        is_valid, error = CommitMessageSanitizer.validate(message)

        # Assert
        assert is_valid is False
        assert error is not None
        assert "too long" in error.lower()


class TestHTMLEscaper:
    """Test HTML escaping for XSS prevention."""

    def test_escape_basic_html_chars(self):
        """Test escaping of basic HTML special characters."""
        # Arrange
        content = "<script>alert('XSS')</script>"

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_escape_ampersand(self):
        """Test escaping of ampersand character."""
        # Arrange
        content = "Tom & Jerry"

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert "&amp;" in result
        assert result == "Tom &amp; Jerry"

    def test_escape_quotes(self):
        """Test escaping of quote characters."""
        # Arrange
        content = "onclick=\"alert(1)\" data-value='test'"

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert '"' not in result
        assert "'" not in result
        assert "&quot;" in result
        assert "&#x27;" in result

    def test_escape_preserves_safe_content(self):
        """Test that safe content is preserved."""
        # Arrange
        content = "Hello, World! 123"

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert result == content

    def test_escape_empty_string(self):
        """Test escaping of empty string."""
        # Arrange
        content = ""

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert result == ""

    def test_escape_unicode(self):
        """Test that unicode characters are preserved."""
        # Arrange
        content = "Hello 世界 🌍"

        # Act
        result = HTMLEscaper.escape(content)

        # Assert
        assert "世界" in result
        assert "🌍" in result

    def test_escape_dict_simple(self):
        """Test recursive escaping of dictionary values."""
        # Arrange
        data: dict[str, object] = {
            "title": "<script>alert('XSS')</script>",
            "count": 42,
        }

        # Act
        result = HTMLEscaper.escape_dict(data)

        # Assert
        title = result.get("title")
        assert isinstance(title, str)
        assert "<" not in title
        assert result["count"] == 42

    def test_escape_dict_nested(self):
        """Test recursive escaping of nested dictionaries."""
        # Arrange
        data: dict[str, object] = {
            "user": {
                "name": "<b>John</b>",
                "email": "john@example.com",
            },
        }

        # Act
        result = HTMLEscaper.escape_dict(data)

        # Assert
        user_raw = result.get("user")
        assert isinstance(user_raw, dict)
        user = cast(dict[str, object], user_raw)
        name = str(user.get("name", ""))
        assert isinstance(name, str)
        assert "<" not in name
        assert "&lt;b&gt;" in name

    def test_escape_dict_with_list(self):
        """Test recursive escaping of lists in dictionaries."""
        # Arrange
        data: dict[str, object] = {
            "items": ["<script>", "safe", "<img onerror='alert(1)'>"],
        }

        # Act
        result = HTMLEscaper.escape_dict(data)

        # Assert
        items = result.get("items")
        assert isinstance(items, list)
        assert "<" not in items[0]
        assert items[1] == "safe"

    def test_escape_dict_preserves_types(self):
        """Test that non-string types are preserved."""
        # Arrange
        data: dict[str, object] = {
            "string": "<tag>",
            "number": 123,
            "float": 3.14,
            "boolean": True,
            "none": None,
        }

        # Act
        result = HTMLEscaper.escape_dict(data)

        # Assert
        assert result["number"] == 123
        assert result["float"] == 3.14
        assert result["boolean"] is True
        assert result["none"] is None


class TestRegexValidator:
    """Test regex pattern validation for ReDoS prevention."""

    def test_validate_simple_pattern(self):
        """Test validation of simple, safe regex patterns."""
        # Arrange
        pattern = r"^[a-z]+$"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is True
        assert error is None

    def test_validate_complex_safe_pattern(self):
        """Test validation of complex but safe patterns."""
        # Arrange
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is True
        assert error is None

    def test_validate_too_long_pattern(self):
        """Test rejection of overly long patterns."""
        # Arrange
        pattern = "a" * 1500

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "too long" in error.lower()

    def test_validate_null_bytes(self):
        """Test rejection of patterns with actual null bytes (not escaped \\0)."""
        # Arrange - actual null byte character, not the escaped string "\0"
        pattern = "test\x00pattern"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "null" in error.lower()

    def test_validate_deep_nesting(self):
        """Test rejection of deeply nested patterns."""
        # Arrange - 7 levels of nesting (exceeds MAX_NESTING_DEPTH of 5)
        pattern = r"(((((((.)))))))"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "nesting" in error.lower()

    def test_validate_nested_quantifiers(self):
        """Test rejection of nested quantifiers (ReDoS indicator)."""
        # Arrange - classic ReDoS pattern
        pattern = r"(a+)+"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "nested quantifiers" in error.lower() or "ReDoS" in error

    def test_validate_nested_star_quantifiers(self):
        """Test rejection of nested star quantifiers."""
        # Arrange
        pattern = r"(a*)*"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None

    def test_validate_large_quantifier(self):
        """Test rejection of large quantifier values."""
        # Arrange - quantifier exceeds MAX_QUANTIFIER_LIMIT
        pattern = r"a{500}"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "too large" in error.lower()

    def test_validate_large_quantifier_range(self):
        """Test rejection of large quantifier range."""
        # Arrange
        pattern = r"a{1,500}"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "too large" in error.lower()

    def test_validate_invalid_regex_syntax(self):
        """Test rejection of invalid regex syntax."""
        # Arrange
        pattern = r"[unclosed"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is False
        assert error is not None
        assert "Invalid regex" in error

    def test_validate_safe_quantifiers_within_limit(self):
        """Test acceptance of quantifiers within limit."""
        # Arrange
        pattern = r"a{1,50}"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is True
        assert error is None

    def test_compile_safe_valid_pattern(self):
        """Test compile_safe with valid pattern."""
        # Arrange
        pattern = r"^[a-z]+$"

        # Act
        compiled = RegexValidator.compile_safe(pattern)

        # Assert
        assert isinstance(compiled, re.Pattern)
        assert compiled.match("hello") is not None

    def test_compile_safe_with_flags(self):
        """Test compile_safe with regex flags."""
        # Arrange
        pattern = r"hello"

        # Act
        compiled = RegexValidator.compile_safe(pattern, flags=re.IGNORECASE)

        # Assert
        assert compiled.match("HELLO") is not None

    def test_compile_safe_unsafe_pattern_raises(self):
        """Test compile_safe raises ValueError for unsafe patterns."""
        # Arrange
        pattern = r"(a+)+"

        # Act & Assert
        with pytest.raises(ValueError, match="Unsafe regex"):
            _ = RegexValidator.compile_safe(pattern)

    def test_compile_safe_invalid_syntax_raises(self):
        """Test compile_safe raises error for invalid syntax."""
        # Arrange
        pattern = r"[unclosed"

        # Act & Assert
        with pytest.raises(ValueError, match="Unsafe regex"):
            _ = RegexValidator.compile_safe(pattern)

    def test_validate_acceptable_nesting(self):
        """Test that acceptable nesting depth is allowed."""
        # Arrange - 4 levels of nesting (within MAX_NESTING_DEPTH of 5)
        pattern = r"((((test))))"

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert
        assert is_safe is True
        assert error is None

    def test_validate_empty_pattern(self):
        """Test validation of empty pattern."""
        # Arrange
        pattern = ""

        # Act
        is_safe, error = RegexValidator.validate(pattern)

        # Assert - empty pattern is valid regex
        assert is_safe is True
        assert error is None
