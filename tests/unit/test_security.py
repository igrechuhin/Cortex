"""Security tests for input validation, integrity checks, and rate limiting."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from cortex.core.exceptions import IndexCorruptedError
from cortex.core.security import InputValidator, JSONIntegrity, RateLimiter


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
