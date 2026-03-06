"""Input and path validation helpers.

Extracted from ``security.py`` as part of Phase 81
(oversized module reduction wave 1).
"""

from __future__ import annotations

import re
from pathlib import Path


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
            msg = (
                f"Pattern too long: {len(pattern)} > "
                f"{RegexValidator.MAX_PATTERN_LENGTH}"
            )
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
            msg = (
                f"Pattern nesting too deep: {max_depth} > "
                f"{RegexValidator.MAX_NESTING_DEPTH}"
            )
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
                msg = (
                    f"Quantifier minimum too large: {min_val} > "
                    f"{RegexValidator.MAX_QUANTIFIER_LIMIT}"
                )
                return False, msg
            if (
                max_val
                and max_val.isdigit()
                and int(max_val) > RegexValidator.MAX_QUANTIFIER_LIMIT
            ):
                msg = (
                    f"Quantifier maximum too large: {max_val} > "
                    f"{RegexValidator.MAX_QUANTIFIER_LIMIT}"
                )
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
            msg = f"Invalid file name: {name} (contains path traversal)"
            raise ValueError(msg)

    @staticmethod
    def _check_absolute_path(name: str) -> None:
        """Check for absolute path indicators."""
        if ":" in name and len(name) > 2 and name[1] == ":":
            msg = f"Invalid file name: {name} (absolute path not allowed)"
            raise ValueError(msg)

    @staticmethod
    def _check_invalid_chars(name: str) -> None:
        """Check for invalid characters."""
        invalid_chars = [c for c in name if c in InputValidator.INVALID_CHARS]
        if invalid_chars:
            msg = (
                "File name contains invalid characters: "
                + f"{', '.join(repr(c) for c in invalid_chars)}"
            )
            raise ValueError(msg)

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
        except (ValueError, OSError) as exc:
            msg = f"Invalid path: {exc}"
            raise ValueError(msg) from exc

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
            msg = f"String too long: {len(value)} > {max_length} characters"
            raise ValueError(msg)

        # Check for null bytes (security risk)
        if "\0" in value:
            raise ValueError("Null bytes not allowed in input")

        if not allow_newlines and ("\n" in value or "\r" in value):
            raise ValueError("Newlines not allowed in this field")

        if pattern is not None and not re.match(pattern, value):
            msg = f"String does not match required pattern: {pattern}"
            raise ValueError(msg)

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
            msg = (
                f"Invalid git URL protocol: {url}. Only HTTPS and SSH "
                + "protocols allowed."
            )
            raise ValueError(msg)

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
