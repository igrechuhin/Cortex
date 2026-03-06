"""Git and configuration security helpers.

Extracted from ``security.py`` as part of Phase 81
(oversized module reduction wave 1).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque
from pathlib import Path
from typing import cast

from cortex.core.constants import (
    GIT_RATE_LIMIT_OPS_PER_SECOND,
    RATE_LIMIT_OPS_PER_SECOND,
)
from cortex.core.models import JsonDict, JsonValue, ModelDict

from .async_file_utils import open_async_text_file
from .exceptions import IndexCorruptedError


class CommitMessageSanitizer:
    """Sanitize commit messages to prevent command injection.

    This class provides security functions to sanitize commit messages
    before passing them to git operations, preventing shell injection attacks.
    """

    # Control characters that should be removed (except newline, tab)
    _CONTROL_CHARS = {chr(i) for i in range(32) if i not in (9, 10)}  # Keep \t, \n

    # Shell metacharacters that could enable command injection
    _SHELL_METACHARACTERS = set("`$(){}[]|;&<>\\")

    # Maximum commit message length (git allows up to 100KB, we limit to 10KB)
    MAX_MESSAGE_LENGTH = 10000

    @staticmethod
    def sanitize(message: str, max_length: int | None = None) -> str:
        """Sanitize a commit message for safe use in git operations.

        Removes control characters, escapes shell metacharacters, and validates
        length to prevent command injection attacks.

        Args:
            message: The commit message to sanitize
            max_length: Maximum allowed length (default: MAX_MESSAGE_LENGTH)

        Returns:
            Sanitized commit message safe for git operations

        Raises:
            ValueError: If message is empty after sanitization
        """
        if max_length is None:
            max_length = CommitMessageSanitizer.MAX_MESSAGE_LENGTH

        # Remove null bytes first (most critical)
        message = message.replace("\0", "")

        # Remove control characters (keep newlines and tabs)
        message = "".join(
            char
            for char in message
            if char not in CommitMessageSanitizer._CONTROL_CHARS
        )

        # Remove shell metacharacters
        message = "".join(
            char if char not in CommitMessageSanitizer._SHELL_METACHARACTERS else ""
            for char in message
        )

        # Normalize whitespace (collapse multiple spaces, trim)
        message = " ".join(message.split())

        # Validate length
        if len(message) > max_length:
            message = message[:max_length]

        # Validate non-empty after sanitization
        if not message.strip():
            raise ValueError("Commit message cannot be empty after sanitization")

        return message

    @staticmethod
    def validate(message: str) -> tuple[bool, str | None]:
        """Validate a commit message without modifying it.

        Args:
            message: The commit message to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not message:
            return False, "Commit message cannot be empty"

        if "\0" in message:
            return False, "Commit message contains null bytes"

        for char in CommitMessageSanitizer._CONTROL_CHARS:
            if char in message:
                msg = f"Commit message contains control character: {repr(char)}"
                return False, msg

        for char in CommitMessageSanitizer._SHELL_METACHARACTERS:
            if char in message:
                msg = f"Commit message contains shell metacharacter: {repr(char)}"
                return False, msg

        if len(message) > CommitMessageSanitizer.MAX_MESSAGE_LENGTH:
            msg = (
                f"Commit message too long: {len(message)} > "
                f"{CommitMessageSanitizer.MAX_MESSAGE_LENGTH}"
            )
            return False, msg

        return True, None


class JSONIntegrity:
    """Provides integrity checks for JSON configuration files."""

    @staticmethod
    async def save_with_integrity(path: Path, data: JsonDict | ModelDict) -> None:
        """Save JSON with integrity hash.

        Args:
            path: Path to JSON file
            data: JsonDict data to save

        Raises:
            OSError: If file cannot be written
        """
        # Convert to dict for serialization
        data_dict = data.to_dict() if isinstance(data, JsonDict) else dict(data)
        # Serialize data
        content = json.dumps(data_dict, indent=2, sort_keys=True)

        # Compute integrity hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Create wrapper with integrity info
        wrapper = {
            "_integrity": content_hash,
            "_version": "1.0",
            "data": data_dict,
        }

        # Write to file atomically
        async with open_async_text_file(path, "w", "utf-8") as file:
            _ = await file.write(json.dumps(wrapper, indent=2))

    @staticmethod
    async def load_with_integrity(path: Path) -> ModelDict:
        """Load JSON and verify integrity.

        Args:
            path: Path to JSON file

        Returns:
            Loaded dict data

        Raises:
            FileNotFoundError: If file doesn't exist
            IndexCorruptedError: If integrity check fails
            json.JSONDecodeError: If JSON is invalid
        """
        async with open_async_text_file(path, "r", "utf-8") as file:
            content = await file.read()

        wrapper_raw: JsonValue = json.loads(content)

        # Check if this is an integrity-protected file
        if isinstance(wrapper_raw, dict) and "_integrity" in wrapper_raw:
            wrapper = wrapper_raw
            # Extract data and verify integrity
            data_raw = wrapper.get("data", {})
            data_dict = data_raw if isinstance(data_raw, dict) else {}
            expected_hash_raw = wrapper["_integrity"]
            expected_hash = (
                str(expected_hash_raw) if expected_hash_raw is not None else ""
            )

            # Recompute hash of data
            data_content = json.dumps(data_dict, indent=2, sort_keys=True)
            actual_hash = hashlib.sha256(
                data_content.encode("utf-8"),
            ).hexdigest()

            if actual_hash != expected_hash:
                msg = (
                    f"Integrity check failed for {path}: "
                    + f"expected {expected_hash[:8]}..., got {actual_hash[:8]}..."
                )
                raise IndexCorruptedError(msg)

            return cast(ModelDict, data_dict)

        # Legacy format without integrity check
        if isinstance(wrapper_raw, dict):
            return cast(ModelDict, wrapper_raw)
        return {}


class RateLimiter:
    """Rate limiter for file operations to prevent abuse."""

    def __init__(
        self,
        max_ops: int = RATE_LIMIT_OPS_PER_SECOND,
        window_seconds: float = 1.0,
    ):
        """
        Initialize rate limiter.

        Design Decision: Sliding window rate limiting
        Context: Need to prevent abuse of file operations without blocking
        legitimate use
        Decision: Sliding window rate limiter with async support
        Alternatives Considered: Fixed window, token bucket
        Rationale: Sliding window provides smooth rate limiting without
        burst allowance issues

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


# Module-level git rate limiter (Phase 9.4)
_git_rate_limiter = RateLimiter(
    max_ops=GIT_RATE_LIMIT_OPS_PER_SECOND,
    window_seconds=1.0,
)


async def acquire_git_operation_slot() -> None:
    """Acquire permission to run a git operation (Phase 9.4 rate limiting)."""
    await _git_rate_limiter.acquire()
