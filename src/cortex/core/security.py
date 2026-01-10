"""Security utilities for input validation, integrity checks, and rate limiting."""

import asyncio
import hashlib
import json
import re
import time
from collections import deque
from pathlib import Path
from typing import cast

from cortex.core.constants import RATE_LIMIT_OPS_PER_SECOND

from .async_file_utils import open_async_text_file
from .exceptions import IndexCorruptedError


class InputValidator:
    """Validates and sanitizes user inputs for security."""

    # Invalid characters for file names (cross-platform)
    INVALID_CHARS = set('<>:"|?*\0')

    # Reserved file names on Windows
    RESERVED_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    @staticmethod
    def validate_file_name(name: str) -> str:
        """Validate and sanitize file name.

        Args:
            name: File name to validate

        Returns:
            Sanitized file name

        Raises:
            ValueError: If file name is invalid
        """
        # Early validation and sanitization
        name = InputValidator._check_empty_name(name)
        _ = InputValidator._check_trailing_chars(name)
        name = name.strip()
        _ = InputValidator._check_empty_name(name)

        # Security checks
        InputValidator._check_path_traversal(name)
        InputValidator._check_absolute_path(name)
        InputValidator._check_invalid_chars(name)
        InputValidator._check_reserved_names(name)
        InputValidator._check_length(name)

        return name

    @staticmethod
    def _check_empty_name(name: str) -> str:
        """Check if name is empty."""
        if not name:
            raise ValueError("File name cannot be empty")
        return name

    @staticmethod
    def _check_trailing_chars(name: str) -> None:
        """Check for invalid trailing characters (Windows compatibility)."""
        if name.endswith(".") or name.endswith(" "):
            raise ValueError(f"File name cannot end with period or space: {name}")

    @staticmethod
    def _check_path_traversal(name: str) -> None:
        """Check for path traversal attempts."""
        if ".." in name or name.startswith("/") or name.startswith("\\"):
            raise ValueError(f"Invalid file name: {name} (contains path traversal)")

    @staticmethod
    def _check_absolute_path(name: str) -> None:
        """Check for absolute path indicators."""
        if ":" in name and len(name) > 2 and name[1] == ":":
            raise ValueError(f"Invalid file name: {name} (absolute path not allowed)")

    @staticmethod
    def _check_invalid_chars(name: str) -> None:
        """Check for invalid characters."""
        invalid_chars = [c for c in name if c in InputValidator.INVALID_CHARS]
        if invalid_chars:
            raise ValueError(
                f"File name contains invalid characters: {', '.join(repr(c) for c in invalid_chars)}"
            )

    @staticmethod
    def _check_reserved_names(name: str) -> None:
        """Check for reserved Windows file names."""
        if name.upper() in InputValidator.RESERVED_NAMES:
            raise ValueError(f"File name is reserved: {name}")

    @staticmethod
    def _check_length(name: str) -> None:
        """Check file name length."""
        if len(name) > 255:
            raise ValueError(f"File name too long: {len(name)} > 255 characters")

    @staticmethod
    def validate_path(path: Path, base_dir: Path) -> bool:
        """Validate that path is within base directory.

        Args:
            path: Path to validate
            base_dir: Base directory to check against

        Returns:
            True if path is valid and within base directory

        Raises:
            ValueError: If path validation fails
        """
        try:
            resolved_path = Path(path).resolve()
            resolved_base = Path(base_dir).resolve()

            # Check if path is relative to base directory
            if not resolved_path.is_relative_to(resolved_base):
                raise ValueError(f"Path {path} is outside base directory {base_dir}")

            return True
        except (ValueError, OSError) as e:
            raise ValueError(f"Invalid path: {e}") from e

    @staticmethod
    def validate_string_input(
        value: str,
        max_length: int = 10000,
        allow_newlines: bool = True,
        pattern: str | None = None,
    ) -> str:
        """Validate and sanitize string input.

        Args:
            value: String to validate
            max_length: Maximum allowed length
            allow_newlines: Whether to allow newline characters
            pattern: Optional regex pattern to match

        Returns:
            Validated string

        Raises:
            ValueError: If validation fails
        """
        if len(value) > max_length:
            raise ValueError(f"String too long: {len(value)} > {max_length} characters")

        # Check for null bytes (security risk)
        if "\0" in value:
            raise ValueError("Null bytes not allowed in input")

        if not allow_newlines and ("\n" in value or "\r" in value):
            raise ValueError("Newlines not allowed in this field")

        if pattern is not None:
            if not re.match(pattern, value):
                raise ValueError(f"String does not match required pattern: {pattern}")

        return value

    @staticmethod
    def validate_git_url(url: str) -> str:
        """Validate git repository URL for security.

        Args:
            url: Git URL to validate

        Returns:
            Validated URL

        Raises:
            ValueError: If URL is invalid or potentially malicious
        """
        # Early validation and sanitization
        url = InputValidator._check_empty_git_url(url)
        url = url.strip()
        _ = InputValidator._check_empty_git_url(url)

        # Protocol and security checks
        InputValidator._check_git_protocol(url)
        InputValidator._check_localhost_access(url)
        InputValidator._check_private_ip_access(url)
        InputValidator._check_file_protocol(url)
        InputValidator._check_git_url_length(url)

        return url

    @staticmethod
    def _check_empty_git_url(url: str) -> str:
        """Check if git URL is empty."""
        if not url:
            raise ValueError("Git URL cannot be empty")
        return url

    @staticmethod
    def _check_git_protocol(url: str) -> None:
        """Check for allowed git protocols (HTTPS and SSH only)."""
        if not (url.startswith("https://") or url.startswith("git@")):
            raise ValueError(
                f"Invalid git URL protocol: {url}. Only HTTPS and SSH protocols allowed."
            )

    @staticmethod
    def _check_localhost_access(url: str) -> None:
        """Block localhost references in git URLs (case-insensitive)."""
        url_lower = url.lower()
        if "localhost" in url_lower or "127.0.0.1" in url or "[::1]" in url:
            raise ValueError("Git URL cannot reference localhost")

    @staticmethod
    def _check_private_ip_access(url: str) -> None:
        """Block private IP ranges in git URLs."""
        if "192.168." in url or "10." in url or "172.16." in url:
            raise ValueError("Git URL cannot reference private IP addresses")

    @staticmethod
    def _check_file_protocol(url: str) -> None:
        """Block file:// protocol in git URLs."""
        if url.lower().startswith("file://"):
            raise ValueError("File protocol not allowed for git URLs")

    @staticmethod
    def _check_git_url_length(url: str) -> None:
        """Check git URL length."""
        if len(url) > 2048:
            raise ValueError(f"Git URL too long: {len(url)} > 2048 characters")


class JSONIntegrity:
    """Provides integrity checks for JSON configuration files."""

    @staticmethod
    async def save_with_integrity(path: Path, data: dict[str, object]) -> None:
        """Save JSON with integrity hash.

        Args:
            path: Path to JSON file
            data: Data to save

        Raises:
            OSError: If file cannot be written
        """
        # Serialize data
        content = json.dumps(data, indent=2, sort_keys=True)

        # Compute integrity hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Create wrapper with integrity info
        wrapper = {
            "_integrity": content_hash,
            "_version": "1.0",
            "data": data,
        }

        # Write to file atomically
        async with open_async_text_file(path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(wrapper, indent=2))

    @staticmethod
    async def load_with_integrity(path: Path) -> dict[str, object]:
        """Load JSON and verify integrity.

        Args:
            path: Path to JSON file

        Returns:
            Loaded data

        Raises:
            FileNotFoundError: If file doesn't exist
            IndexCorruptedError: If integrity check fails
            json.JSONDecodeError: If JSON is invalid
        """
        async with open_async_text_file(path, "r", "utf-8") as f:
            content = await f.read()

        wrapper_raw: object = json.loads(content)

        # Check if this is an integrity-protected file
        if isinstance(wrapper_raw, dict) and "_integrity" in wrapper_raw:
            # Type narrowing: we know it's a dict with string keys
            wrapper = cast(dict[str, object], wrapper_raw)
            # Extract data and verify integrity
            data_raw: object = wrapper.get("data", {})
            data: dict[str, object] = (
                cast(dict[str, object], data_raw) if isinstance(data_raw, dict) else {}
            )
            expected_hash_raw: object = wrapper["_integrity"]
            expected_hash: str = (
                str(expected_hash_raw) if expected_hash_raw is not None else ""
            )

            # Recompute hash of data
            data_content = json.dumps(data, indent=2, sort_keys=True)
            actual_hash = hashlib.sha256(data_content.encode("utf-8")).hexdigest()

            if actual_hash != expected_hash:
                raise IndexCorruptedError(
                    f"Integrity check failed for {path}: "
                    + f"expected {expected_hash[:8]}..., got {actual_hash[:8]}..."
                )

            return data

        # Legacy format without integrity check
        if isinstance(wrapper_raw, dict):
            return cast(dict[str, object], wrapper_raw)
        return {}


class RateLimiter:
    """Rate limiter for file operations to prevent abuse."""

    def __init__(
        self, max_ops: int = RATE_LIMIT_OPS_PER_SECOND, window_seconds: float = 1.0
    ):
        """
        Initialize rate limiter.

        Design Decision: Sliding window rate limiting
        Context: Need to prevent abuse of file operations without blocking legitimate use
        Decision: Sliding window rate limiter with async support
        Alternatives Considered: Fixed window, token bucket
        Rationale: Sliding window provides smooth rate limiting without burst allowance issues

        Args:
            max_ops: Maximum operations per window
            window_seconds: Time window in seconds
        """
        self.max_ops = max_ops
        self.window = window_seconds
        self.operations: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to perform an operation.

        Blocks if rate limit is exceeded until operation is allowed.
        """
        async with self._lock:
            now = time.time()

            # Remove operations outside current window
            while self.operations and (now - self.operations[0]) > self.window:
                _ = self.operations.popleft()

            # If at limit, wait until oldest operation expires
            if len(self.operations) >= self.max_ops:
                wait_time = self.operations[0] + self.window - now
                if wait_time > 0:
                    _ = await asyncio.sleep(wait_time)
                    # Remove expired operation
                    _ = self.operations.popleft()

            # Record this operation
            self.operations.append(now)

    def get_current_count(self) -> int:
        """Get current operation count in window.

        Returns:
            Number of operations in current window
        """
        now = time.time()
        # Remove expired operations
        while self.operations and (now - self.operations[0]) > self.window:
            _ = self.operations.popleft()
        return len(self.operations)

    def reset(self) -> None:
        """Reset the rate limiter."""
        self.operations.clear()
