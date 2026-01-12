"""Token counting using tiktoken library for accurate context management."""

import hashlib
import logging
from pathlib import Path
from typing import TypeAlias, cast

Encoding: TypeAlias = object  # Placeholder for tiktoken.Encoding when unavailable

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    Accurate token counting using tiktoken library with graceful degradation.
    Matches OpenAI's token counting for better context management.
    Falls back to word-based estimation if tiktoken is unavailable.
    """

    model: str
    encoding_impl: object | None
    _cache: dict[str, int]
    _tiktoken_available: bool

    def __init__(self, model: str = "cl100k_base"):
        """
        Initialize with encoding model.

        Args:
            model: Tiktoken model name
                - "cl100k_base": GPT-4, GPT-3.5-turbo, text-embedding-ada-002
                - "p50k_base": Codex models
                - "o200k_base": GPT-4o models
        """
        self.model = model
        self.encoding_impl = None  # Lazy initialization
        self._cache = {}
        self._tiktoken_available = self._check_tiktoken_available()

    def _check_tiktoken_available(self) -> bool:
        """Check if tiktoken is available."""
        import importlib.util

        return importlib.util.find_spec("tiktoken") is not None

    @property
    def encoding(self) -> object:
        """Lazy load encoding to avoid blocking on initialization."""
        if not self._tiktoken_available:
            return None

        if self.encoding_impl is None:
            self.encoding_impl = self._load_tiktoken_with_timeout()
        return self.encoding_impl

    def _load_tiktoken_with_timeout(
        self, timeout_seconds: float = 5.0
    ) -> object | None:
        """Load tiktoken encoding with a timeout to prevent network hangs.

        Args:
            timeout_seconds: Maximum time to wait for tiktoken to load

        Returns:
            Tiktoken encoding object or None if loading fails/times out
        """
        import concurrent.futures

        try:
            import tiktoken

            # Use a thread pool to add timeout to the blocking call
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tiktoken.get_encoding, self.model)
                try:
                    return future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        f"Tiktoken encoding '{self.model}' load timed out after "
                        + f"{timeout_seconds}s. Falling back to word-based estimation."
                    )
                    self._tiktoken_available = False
                    return None
        except Exception as e:
            logger.warning(
                f"Failed to load tiktoken encoding '{self.model}': {e}. "
                + "Falling back to word-based estimation."
            )
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
        if self._tiktoken_available and self.encoding is not None:
            try:
                return len(self.encoding.encode(text))  # type: ignore
            except Exception as e:
                logger.warning(
                    f"tiktoken encoding failed: {e}. Falling back to word-based estimation."
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
        self, content: str, sections: list[dict[str, object]]
    ) -> dict[str, object]:
        """
        Count tokens per section and total.

        Args:
            content: Full file content
            sections: List of section metadata with line ranges
                Format: [{"heading": "## Name", "line_start": 1, "line_end": 10}, ...]

        Returns:
            Dict with per-section and total token counts
            {
                "total_tokens": int,
                "sections": [
                    {
                        "heading": "## Name",
                        "token_count": int,
                        "percentage": float
                    }
                ]
            }
        """
        lines = content.split("\n")
        total_tokens = self.count_tokens(content)

        def _process_section(section: dict[str, object]) -> dict[str, object]:
            """Process a single section and return token count data."""
            start_idx = max(0, cast(int, section["line_start"]) - 1)
            end_idx = min(len(lines), cast(int, section["line_end"]))
            section_text = "\n".join(lines[start_idx:end_idx])
            section_tokens = self.count_tokens(section_text)
            percentage = (
                (section_tokens / total_tokens * 100) if total_tokens > 0 else 0
            )
            return {
                "heading": section["heading"],
                "token_count": section_tokens,
                "percentage": round(percentage, 2),
            }

        sections_list: list[dict[str, object]] = [
            _process_section(section) for section in sections
        ]

        results: dict[str, object] = {
            "total_tokens": total_tokens,
            "sections": sections_list,
        }

        return results

    def estimate_context_size(self, file_tokens: dict[str, int]) -> dict[str, object]:
        """
        Estimate total context size for loading all files.

        Args:
            file_tokens: Dict mapping file names to token counts
                {"file1.md": 500, "file2.md": 800}

        Returns:
            {
                "total_tokens": int,
                "estimated_cost_gpt4": float,
                "warnings": list[str]
            }
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

        return {
            "total_tokens": total,
            "estimated_cost_gpt4": round(estimated_cost, 4),
            "warnings": warnings,
            "breakdown": file_tokens,
        }

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

    def parse_markdown_sections(self, content: str | None) -> list[dict[str, object]]:
        """
        Parse markdown content to extract sections with headings.

        Args:
            content: Markdown content to parse

        Returns:
            List of section dictionaries with:
            - title: Heading text
            - level: Heading level (1-6)
            - start_line: Line number where section starts (1-indexed)

        Raises:
            TypeError: If content is None
        """
        if content is None:
            raise TypeError("content cannot be None")
        if not content:
            return []

        lines = content.split("\n")

        def _parse_section(line_num: int, line: str) -> dict[str, object] | None:
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
            return {
                "title": stripped.lstrip("#").strip(),
                "level": level,
                "start_line": line_num,
            }

        sections: list[dict[str, object]] = [
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
