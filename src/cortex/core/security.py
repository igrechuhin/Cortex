"""Security utilities for input validation, integrity checks, and rate limiting."""

import asyncio
import hashlib
import html
import json
import re
import time
from collections import deque
from pathlib import Path
from typing import cast

from cortex.core.constants import RATE_LIMIT_OPS_PER_SECOND
from cortex.core.models import JsonDict, JsonList, JsonValue, ModelDict

from .async_file_utils import open_async_text_file
from .exceptions import IndexCorruptedError


class CommitMessageSanitizer:
    """Sanitize commit messages to prevent command injection.

    This class provides security functions to sanitize commit messages
    before passing them to git operations, preventing shell injection attacks.
    """

    # Control characters that should be removed (except newline, tab)
    _CONTROL_CHARS = set(chr(i) for i in range(32) if i not in (9, 10))  # Keep \t, \n

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
            c for c in message if c not in CommitMessageSanitizer._CONTROL_CHARS
        )

        # Escape shell metacharacters by removing them
        # Git commit -m already handles quoting, but we remove dangerous chars
        message = "".join(
            c if c not in CommitMessageSanitizer._SHELL_METACHARACTERS else ""
            for c in message
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
                return False, f"Commit message contains control character: {repr(char)}"

        for char in CommitMessageSanitizer._SHELL_METACHARACTERS:
            if char in message:
                return (
                    False,
                    f"Commit message contains shell metacharacter: {repr(char)}",
                )

        if len(message) > CommitMessageSanitizer.MAX_MESSAGE_LENGTH:
            msg = (
                f"Commit message too long: {len(message)} > "
                f"{CommitMessageSanitizer.MAX_MESSAGE_LENGTH}"
            )
            return False, msg

        return True, None


class HTMLEscaper:
    """Escape HTML content to prevent XSS attacks in exported content.

    Provides HTML escaping for content that may be rendered in web contexts,
    preventing cross-site scripting (XSS) vulnerabilities.
    """

    @staticmethod
    def escape(content: str) -> str:
        """Escape HTML special characters in content.

        Escapes: < > & " '

        Args:
            content: The content to escape

        Returns:
            HTML-escaped content safe for web display
        """
        # Use standard library html.escape for reliable escaping
        # quote=True escapes both " and '
        return html.escape(content, quote=True)

    @staticmethod
    def escape_dict(data: JsonDict | ModelDict) -> ModelDict:
        """Recursively escape all string values in a dictionary.

        Args:
            data: JsonDict or dict with potentially unsafe string values

        Returns:
            New dict with all string values HTML-escaped
        """
        data_dict = data.to_dict() if isinstance(data, JsonDict) else data
        return HTMLEscaper._escape_dict_recursive(dict(data_dict))

    @staticmethod
    def _escape_dict_recursive(data: ModelDict) -> ModelDict:
        """Recursively escape string values in a dictionary."""
        result_dict: ModelDict = {}
        for key, value in data.items():
            if isinstance(value, str):
                result_dict[key] = HTMLEscaper.escape(value)
            elif isinstance(value, dict):
                escaped = HTMLEscaper._escape_dict_recursive(cast(ModelDict, value))
                result_dict[key] = escaped
            elif isinstance(value, list):
                nested_list = JsonList.from_list(value)
                escaped = HTMLEscaper._escape_list_recursive(nested_list)
                result_dict[key] = escaped.to_list()
            else:
                # int, float, bool, None - pass through unchanged
                result_dict[key] = value
        return result_dict

    @staticmethod
    def _escape_list_recursive(data: JsonList) -> JsonList:
        """Recursively escape string values in a list."""
        result_list: list[JsonValue] = []
        data_list = data.to_list()
        for item in data_list:
            if isinstance(item, str):
                result_list.append(HTMLEscaper.escape(item))
            elif isinstance(item, dict):
                escaped = HTMLEscaper._escape_dict_recursive(cast(ModelDict, item))
                result_list.append(escaped)
            elif isinstance(item, list):
                nested_list = JsonList.from_list(item)
                escaped = HTMLEscaper._escape_list_recursive(nested_list)
                result_list.append(escaped.to_list())
            else:
                result_list.append(item)
        return JsonList.from_list(result_list)


class RegexValidator:
    """Validate regex patterns to prevent ReDoS (Regular Expression DoS) attacks.

    Checks regex patterns for potentially dangerous constructs that could
    cause catastrophic backtracking and denial of service.
    """

    # Maximum allowed pattern length
    MAX_PATTERN_LENGTH = 1000

    # Maximum allowed nesting depth for groups
    MAX_NESTING_DEPTH = 5

    # Maximum allowed quantifier repetitions
    MAX_QUANTIFIER_LIMIT = 100

    # Patterns that indicate potential ReDoS vulnerabilities
    # Nested quantifiers like (a+)+ or (a*)*
    # Pattern parts: (x+)+ or (x*)* | (x+)? | [x+]+ character class quantifiers
    _NESTED_QUANTIFIER_PATTERN = re.compile(
        r"(?:\([^)]*[+*][^)]*\)[+*?]|\([^)]*\)[+*]\?|\[[^\]]*[+*][^\]]*\][+*])"
    )

    # Overlapping alternations like (a|a|a) or (ab|ab)
    _OVERLAPPING_ALTERNATION_PATTERN = re.compile(
        r"\(([^|)]+)\|(\1)\)"  # Same pattern repeated in alternation
    )

    @staticmethod
    def _check_basic_constraints(pattern: str) -> tuple[bool, str | None]:
        """Check basic pattern constraints (length, null bytes, nesting)."""
        if len(pattern) > RegexValidator.MAX_PATTERN_LENGTH:
            msg = f"Pattern too long: {len(pattern)} > {RegexValidator.MAX_PATTERN_LENGTH}"
            return False, msg
        if "\0" in pattern:
            return False, "Pattern contains null bytes"
        return RegexValidator._check_nesting_depth(pattern)

    @staticmethod
    def _check_nesting_depth(pattern: str) -> tuple[bool, str | None]:
        """Check pattern nesting depth."""
        depth = 0
        max_depth = 0
        for char in pattern:
            if char == "(":
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == ")":
                depth -= 1
        if max_depth > RegexValidator.MAX_NESTING_DEPTH:
            msg = f"Pattern nesting too deep: {max_depth} > {RegexValidator.MAX_NESTING_DEPTH}"
            return False, msg
        return True, None

    @staticmethod
    def _check_quantifiers(pattern: str) -> tuple[bool, str | None]:
        """Check for nested or large quantifiers."""
        if RegexValidator._NESTED_QUANTIFIER_PATTERN.search(pattern):
            return False, "Pattern contains nested quantifiers (potential ReDoS)"
        quantifier_pattern = re.compile(r"\{(\d+)(?:,(\d*))?\}")
        for match in quantifier_pattern.finditer(pattern):
            min_val = int(match.group(1))
            max_val = match.group(2)
            if min_val > RegexValidator.MAX_QUANTIFIER_LIMIT:
                msg = f"Quantifier minimum too large: {min_val} > {RegexValidator.MAX_QUANTIFIER_LIMIT}"
                return False, msg
            if (
                max_val
                and max_val.isdigit()
                and int(max_val) > RegexValidator.MAX_QUANTIFIER_LIMIT
            ):
                msg = f"Quantifier maximum too large: {max_val} > {RegexValidator.MAX_QUANTIFIER_LIMIT}"
                return False, msg
        return True, None

    @staticmethod
    def validate(pattern: str) -> tuple[bool, str | None]:
        """Validate a regex pattern for potential ReDoS vulnerabilities.

        Args:
            pattern: The regex pattern to validate

        Returns:
            Tuple of (is_safe, error_message)
        """
        is_valid, error = RegexValidator._check_basic_constraints(pattern)
        if not is_valid:
            return is_valid, error
        is_valid, error = RegexValidator._check_quantifiers(pattern)
        if not is_valid:
            return is_valid, error
        try:
            _ = re.compile(pattern)
        except re.error as e:
            return False, f"Invalid regex pattern: {e}"
        return True, None

    @staticmethod
    def compile_safe(
        pattern: str, flags: int = 0, timeout_hint: bool = True
    ) -> re.Pattern[str]:
        """Compile a regex pattern after validating it for safety.

        Args:
            pattern: The regex pattern to compile
            flags: Optional regex flags
            timeout_hint: If True, includes a hint about using timeout

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If pattern fails validation
            re.error: If pattern has syntax errors
        """
        is_safe, error = RegexValidator.validate(pattern)
        if not is_safe:
            raise ValueError(f"Unsafe regex pattern: {error}")

        return re.compile(pattern, flags)


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
        async with open_async_text_file(path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(wrapper, indent=2))

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
        async with open_async_text_file(path, "r", "utf-8") as f:
            content = await f.read()

        wrapper_raw: JsonValue = json.loads(content)

        # Check if this is an integrity-protected file
        if isinstance(wrapper_raw, dict) and "_integrity" in wrapper_raw:
            # Type narrowing: we know it's a dict with string keys
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
            actual_hash = hashlib.sha256(data_content.encode("utf-8")).hexdigest()

            if actual_hash != expected_hash:
                raise IndexCorruptedError(
                    f"Integrity check failed for {path}: "
                    + f"expected {expected_hash[:8]}..., got {actual_hash[:8]}..."
                )

            return cast(ModelDict, data_dict)

        # Legacy format without integrity check
        if isinstance(wrapper_raw, dict):
            return cast(ModelDict, wrapper_raw)
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
