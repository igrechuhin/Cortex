"""Token counting using tiktoken library for accurate context management."""

import hashlib
import logging
from pathlib import Path
from typing import Protocol, cast

from cortex.core.models import (
    ContextSizeEstimate,
    ModelDict,
    ParsedMarkdownSection,
    SectionMetadata,
    SectionTokenCount,
    TokenCountSectionsResult,
)
from cortex.core.tiktoken_cache import setup_tiktoken_cache

logger = logging.getLogger(__name__)


class _Encoding(Protocol):
    def encode(self, text: str) -> list[int]: ...


class _TiktokenModule(Protocol):
    def get_encoding(self, name: str) -> _Encoding: ...


class TokenCounter:
    """
    Accurate token counting using tiktoken library with graceful degradation.
    Matches OpenAI's token counting for better context management.
    Falls back to word-based estimation if tiktoken is unavailable.
    """

    model: str
    encoding_impl: _Encoding | None
    _cache: dict[str, int]
    _tiktoken_available: bool

    def __init__(self, model: str = "cl100k_base", use_bundled_cache: bool = True):
        """
        Initialize with encoding model.

        Args:
            model: Tiktoken model name
                - "cl100k_base": GPT-4, GPT-3.5-turbo, text-embedding-ada-002
                - "p50k_base": Codex models
                - "o200k_base": GPT-4o models
            use_bundled_cache: Whether to use bundled tiktoken cache if
                available (default: True). This allows offline operation
                when network is unavailable.
        """
        self.model = model
        self.encoding_impl = None  # Lazy initialization
        self._cache = {}
        self._tiktoken_available = self._check_tiktoken_available()

        # Configure bundled cache if available and requested
        if self._tiktoken_available and use_bundled_cache:
            cache_configured = setup_tiktoken_cache(use_bundled=True)
            if cache_configured:
                logger.debug(
                    "Using bundled tiktoken cache for offline operation support"
                )

    def _check_tiktoken_available(self) -> bool:
        """Check if tiktoken is available."""
        import importlib.util

        return importlib.util.find_spec("tiktoken") is not None

    @property
    def encoding(self) -> _Encoding | None:
        """Lazy load encoding to avoid blocking on initialization."""
        if not self._tiktoken_available:
            return None

        if self.encoding_impl is None:
            self.encoding_impl = self._load_tiktoken_with_timeout()
        return self.encoding_impl

    def _is_network_error(self, error: Exception) -> bool:
        """Check if error is network-related (timeout, connection, DNS, etc.)."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Network-related error patterns
        network_patterns = [
            "timeout",
            "connection",
            "network",
            "dns",
            "unreachable",
            "refused",
            "reset",
            "ssl",
            "certificate",
            "http",
            "urllib",
            "requests",
        ]

        return any(
            pattern in error_str or pattern in error_type
            for pattern in network_patterns
        )

    def _try_load_encoding_with_timeout(
        self, tiktoken: _TiktokenModule, timeout_seconds: float
    ) -> _Encoding | None:
        """Attempt to load encoding with timeout.

        Args:
            tiktoken: Tiktoken module
            timeout_seconds: Timeout in seconds

        Returns:
            Encoding object or None if timeout
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tiktoken.get_encoding, self.model)
            try:
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                return None

    def _handle_timeout_retry(
        self,
        attempt: int,
        max_retries: int,
        load_time: float,
        timeout_seconds: float,
    ) -> tuple[bool, float]:
        """Handle timeout retry logic.

        Args:
            attempt: Current attempt number
            max_retries: Maximum retries
            load_time: Time taken for this attempt
            timeout_seconds: Timeout in seconds

        Returns:
            Tuple of (should_retry, retry_delay)
        """
        import time

        if attempt < max_retries:
            retry_delay = 2.0 * (2**attempt)  # Exponential backoff: 2s, 4s
            logger.info(
                f"Tiktoken encoding '{self.model}' load timed out after "
                + f"{load_time:.2f}s (attempt {attempt + 1}/{max_retries + 1}). "
                + f"Retrying in {retry_delay:.1f}s..."
            )
            time.sleep(retry_delay)
            return True, retry_delay
        else:
            logger.warning(
                f"Tiktoken encoding '{self.model}' load timed out after "
                + f"{max_retries + 1} attempts (final timeout: {load_time:.2f}s). "
                + "Network may be unavailable. Falling back to word-based estimation."
            )
            self._tiktoken_available = False
            return False, 0.0

    def _handle_network_error_retry(
        self,
        e: Exception,
        attempt: int,
        max_retries: int,
        load_time: float,
    ) -> tuple[bool, float]:
        """Handle network error retry logic.

        Args:
            e: Exception that occurred
            attempt: Current attempt number
            max_retries: Maximum retries
            load_time: Time taken for this attempt

        Returns:
            Tuple of (should_retry, retry_delay)
        """
        import time

        if attempt < max_retries:
            retry_delay = 2.0 * (2**attempt)
            logger.info(
                f"Tiktoken encoding '{self.model}' network error after "
                + f"{load_time:.2f}s (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                + f"Retrying in {retry_delay:.1f}s..."
            )
            time.sleep(retry_delay)
            return True, retry_delay
        else:
            logger.warning(
                (
                    f"Tiktoken encoding '{self.model}' network unavailable after "
                    f"{max_retries + 1} attempts (final error after "
                    f"{load_time:.2f}s): {e}. Cache may be used if available. "
                    "Falling back to word-based estimation."
                )
            )
            self._tiktoken_available = False
            return False, 0.0

    def _log_encoding_success(self, attempt: int, load_time: float) -> None:
        """Log successful encoding load.

        Args:
            attempt: Attempt number (0 for first attempt)
            load_time: Time taken to load
        """
        if attempt > 0:
            logger.info(
                f"Tiktoken encoding '{self.model}' loaded successfully "
                + f"after {attempt} retries in {load_time:.2f}s"
            )
        else:
            logger.debug(f"Tiktoken encoding '{self.model}' loaded in {load_time:.2f}s")

    def _handle_non_network_error(self, e: Exception, load_time: float) -> None:
        """Handle non-network errors during encoding load.

        Args:
            e: Exception that occurred
            load_time: Time taken for this attempt
        """
        logger.warning(
            f"Failed to load tiktoken encoding '{self.model}' after "
            + f"{load_time:.2f}s: {e}. Falling back to word-based estimation."
        )
        self._tiktoken_available = False

    def _handle_encoding_attempt(
        self,
        tiktoken: _TiktokenModule,
        attempt: int,
        max_retries: int,
        timeout_seconds: float,
    ) -> tuple[_Encoding | None, bool]:
        """Handle a single encoding load attempt.

        Args:
            tiktoken: Tiktoken module
            attempt: Current attempt number
            max_retries: Maximum retries
            timeout_seconds: Timeout in seconds

        Returns:
            Tuple of (encoding or None, should_continue)
        """
        import time

        start_time = time.time()
        try:
            encoding = self._try_load_encoding_with_timeout(tiktoken, timeout_seconds)
            if encoding is not None:
                load_time = time.time() - start_time
                self._log_encoding_success(attempt, load_time)
                return encoding, False

            load_time = time.time() - start_time
            should_retry, _ = self._handle_timeout_retry(
                attempt, max_retries, load_time, timeout_seconds
            )
            return None, should_retry
        except Exception as e:
            load_time = time.time() - start_time
            is_network_error = self._is_network_error(e)

            if is_network_error:
                should_retry, _ = self._handle_network_error_retry(
                    e, attempt, max_retries, load_time
                )
                return None, should_retry

            self._handle_non_network_error(e, load_time)
            return None, False

    def _load_tiktoken_with_timeout(
        self, timeout_seconds: float = 30.0, max_retries: int = 2
    ) -> _Encoding | None:
        """Load tiktoken encoding with cache-first strategy and graceful fallback.

        Tiktoken automatically uses cached encoding files if available.
        This method handles network unavailability gracefully:
        - Uses cache if available (tiktoken does this automatically)
        - Retries network requests with exponential backoff
        - Falls back to word-based estimation if network unavailable and no cache

        Args:
            timeout_seconds: Maximum time to wait per attempt (default: 30s)
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            Tiktoken encoding object or None if loading fails/times out
        """
        try:
            import tiktoken
        except ImportError:
            logger.warning(
                "Tiktoken library not available. Falling back to word-based estimation."
            )
            self._tiktoken_available = False
            return None

        tiktoken_mod = cast(_TiktokenModule, tiktoken)
        for attempt in range(max_retries + 1):
            encoding, should_continue = self._handle_encoding_attempt(
                tiktoken_mod, attempt, max_retries, timeout_seconds
            )
            if encoding is not None:
                return encoding
            if not should_continue:
                self._tiktoken_available = False
                return None
        self._tiktoken_available = False
        return None

    def _estimate_tokens_by_words(self, text: str) -> int:
        """
        Estimate token count using word-based heuristic.

        Uses approximation: ~1 token per 4 characters (0.75 tokens per word on average).
        This is less accurate than tiktoken but provides a reasonable fallback.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        if not text:
            return 0
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4

    def count_tokens(self, text: str | None) -> int:
        """
        Count tokens in text with graceful degradation.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens (exact if tiktoken available, estimated otherwise)

        Raises:
            TypeError: If text is None
        """
        if text is None:
            raise TypeError("text cannot be None")
        if not text:
            return 0

        # Try tiktoken first
        encoding = self.encoding if self._tiktoken_available else None
        if encoding is not None:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(
                    (
                        f"tiktoken encoding failed: {e}. Falling back to "
                        "word-based estimation."
                    )
                )
                self._tiktoken_available = False

        # Fallback to word-based estimation
        return self._estimate_tokens_by_words(text)

    def count_tokens_with_cache(self, text: str, content_hash: str) -> int:
        """
        Count tokens with caching by content hash.

        Args:
            text: Text to count tokens for
            content_hash: SHA-256 hash of content for caching

        Returns:
            Number of tokens
        """
        if content_hash in self._cache:
            return self._cache[content_hash]

        token_count = self.count_tokens(text)
        self._cache[content_hash] = token_count
        return token_count

    def count_tokens_sections(
        self, content: str, sections: list[SectionMetadata | ModelDict]
    ) -> TokenCountSectionsResult:
        """
        Count tokens per section and total.

        Args:
            content: Full file content
            sections: List of section metadata with line ranges

        Returns:
            TokenCountSectionsResult with per-section and total token counts
        """
        lines = content.split("\n")
        total_tokens = self.count_tokens(content)

        def _normalize_section(section: SectionMetadata | ModelDict) -> SectionMetadata:
            if isinstance(section, SectionMetadata):
                return section
            return SectionMetadata.model_validate(section)

        def _process_section(section: SectionMetadata | ModelDict) -> SectionTokenCount:
            """Process a single section and return token count data."""
            normalized = _normalize_section(section)
            start_idx = max(0, normalized.line_start - 1)
            end_idx = min(len(lines), normalized.line_end)
            section_text = "\n".join(lines[start_idx:end_idx])
            section_tokens = self.count_tokens(section_text)
            percentage = (
                (section_tokens / total_tokens * 100) if total_tokens > 0 else 0
            )
            return SectionTokenCount(
                heading=normalized.title,
                token_count=section_tokens,
                percentage=round(percentage, 2),
            )

        sections_list: list[SectionTokenCount] = [
            _process_section(section) for section in sections
        ]

        return TokenCountSectionsResult(
            total_tokens=total_tokens,
            sections=sections_list,
        )

    def estimate_context_size(self, file_tokens: dict[str, int]) -> ContextSizeEstimate:
        """
        Estimate total context size for loading all files.

        Args:
            file_tokens: Dict mapping file names to token counts
                {"file1.md": 500, "file2.md": 800}

        Returns:
            ContextSizeEstimate with total tokens, cost estimate, and warnings
        """
        total = sum(file_tokens.values())

        # Rough cost estimates (as of 2025)
        # These are approximate and should be updated
        cost_per_1k_tokens = 0.03  # GPT-4 input pricing
        estimated_cost = (total / 1000) * cost_per_1k_tokens

        warnings: list[str] = []
        if total > 100000:
            warnings.append(
                "Total context exceeds 100K tokens - consider archival strategy"
            )
        elif total > 50000:
            warnings.append("High token count (>50K) - progressive loading recommended")

        if total > 200000:
            warnings.append(
                "Exceeds most model context windows - immediate action required"
            )

        return ContextSizeEstimate(
            total_tokens=total,
            estimated_cost_gpt4=round(estimated_cost, 4),
            warnings=warnings,
            breakdown=file_tokens,
        )

    def clear_cache(self):
        """Clear the token count cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)

    async def count_tokens_in_file(self, file_path: Path) -> int:
        """
        Count tokens in a file.

        Args:
            file_path: Path to the file

        Returns:
            Number of tokens in the file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return self.count_tokens(content)

    def parse_markdown_sections(
        self, content: str | None
    ) -> list[ParsedMarkdownSection]:
        """
        Parse markdown content to extract sections with headings.

        Args:
            content: Markdown content to parse

        Returns:
            List of ParsedMarkdownSection with title, level, and start_line

        Raises:
            TypeError: If content is None
        """
        if content is None:
            raise TypeError("content cannot be None")
        if not content:
            return []

        lines = content.split("\n")

        def _parse_section(line_num: int, line: str) -> ParsedMarkdownSection | None:
            """Parse a single line to extract section info if it's a header."""
            stripped = line.lstrip()
            if not stripped.startswith("#"):
                return None
            hash_start = line.find("#")
            if hash_start < 0:
                return None
            hash_section = line[hash_start:]
            level = len(hash_section) - len(hash_section.lstrip("#"))
            if not (1 <= level <= 6):
                return None
            return ParsedMarkdownSection(
                title=stripped.lstrip("#").strip(),
                level=level,
                start_line=line_num,
            )

        sections: list[ParsedMarkdownSection] = [
            section
            for line_num, line in enumerate(lines, start=1)
            if (section := _parse_section(line_num, line)) is not None
        ]

        return sections

    def content_hash(self, content: str | None) -> str:
        """
        Generate SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hexadecimal hash string

        Raises:
            TypeError: If content is None
        """
        if content is None:
            raise TypeError("content cannot be None")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
